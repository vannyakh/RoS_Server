/**
 * READ-ONLY RE hook: when the client resolves a server->client entity method
 * (libclient+0x9d46f8, same hook as dump_client_methods.js), scan the surrounding entity
 * description for every method table (stride 0x68 descriptors with a name) and every
 * int32 index vector, and print them. The base (client->server) exposed table is one of
 * them. Observes only; prints once per entity description.
 *
 * LDPlayer: python scripts/run_frida.py frida/dump_base_methods.js --attach --realm emulated
 */
const lib = Process.findModuleByName("libclient.so");
const seen = new Set();

function readStdString(p) {
    try {
        const b0 = p.readU8();
        if ((b0 & 1) === 0) {
            const n = b0 >> 1;
            return n > 0 && n < 23 ? p.add(1).readUtf8String(n) : null;
        }
        const n = p.add(8).readU64().toNumber();
        if (n <= 0 || n > 200) return null;
        return p.add(16).readPointer().readUtf8String(n);
    } catch (e) { return null; }
}

const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]{2,}$/;
function nameAt(m) {
    const s = readStdString(m.add(8));
    return s && NAME_RE.test(s) ? s : null;
}

function vec(p) {
    try {
        const b = p.readPointer(), e = p.add(8).readPointer();
        const d = e.sub(b).toInt32();
        if (b.isNull() || d <= 0 || d > 0x200000) return null;
        return { b: b, bytes: d };
    } catch (e) { return null; }
}

function scan(c) {
    const tables = [];
    for (let off = -0x800; off <= 0x800; off += 8) {
        const v = vec(c.add(off));
        if (!v) continue;
        if (v.bytes % 0x68 === 0) {
            const n = v.bytes / 0x68;
            const first = nameAt(v.b);
            if (n >= 10 && first) {
                tables.push({ off: off, n: n, b: v.b });
                console.log("[table] off=" + off.toString(16) + " n=" + n + " first=" + first + " second=" + nameAt(v.b.add(0x68)));
            }
        }
    }
    for (let off = -0x800; off <= 0x800; off += 8) {
        const v = vec(c.add(off));
        if (!v || v.bytes % 4 !== 0) continue;
        const n = v.bytes / 4;
        if (n < 10 || n > 5000) continue;
        let ok = true;
        const head = [];
        for (let i = 0; i < n; i++) {
            const x = v.b.add(i * 4).readS32();
            if (x < 0 || x > 5000) { ok = false; break; }
            if (i < 8) head.push(x);
        }
        if (!ok) continue;
        console.log("[ivec] off=" + off.toString(16) + " n=" + n + " head=" + JSON.stringify(head));
        // resolve against each table whose size can hold the indices
        for (const t of tables) {
            let max = 0;
            for (let i = 0; i < n; i++) max = Math.max(max, v.b.add(i * 4).readS32());
            if (max >= t.n) continue;
            const lines = [];
            for (let i = 0; i < n; i++) {
                const ix = v.b.add(i * 4).readS32();
                lines.push(i + " " + ix + " " + nameAt(t.b.add(ix * 0x68)));
            }
            console.log("[map] ivec=" + off.toString(16) + " table=" + t.off.toString(16) + "\n" + lines.join("\n") + "\n[endmap]");
        }
    }
}

// Found with scan(): +0x160 = base method descriptors (std::vector, stride 0x68, name
// std::string at +0), +0x178 = exposed base index vector (int32). Client methods sit at
// +0x1b8 / +0x1d0 (name at +8).
const SCAN = false;
function dumpBase(c) {
    const tb = c.add(0x160).readPointer(), te = c.add(0x168).readPointer();
    const vb = c.add(0x178).readPointer(), ve = c.add(0x180).readPointer();
    const n = ve.sub(vb).toInt32() / 4;
    console.log("[base] methods=" + te.sub(tb).toInt32() / 0x68 + " exposed=" + n);
    const lines = [];
    for (let i = 0; i < n; i++) {
        const ix = vb.add(i * 4).readS32();
        lines.push(i + " " + ix + " " + readStdString(tb.add(ix * 0x68)));
    }
    console.log("[map]\n" + lines.join("\n") + "\n[endmap]");
}

if (!lib) {
    console.log("[-] libclient.so not found (use --realm emulated)");
} else {
    Interceptor.attach(lib.base.add(0x9d46f8), {
        onEnter(args) {
            const c = args[0];
            const key = c.toString();
            if (seen.has(key)) return;
            seen.add(key);
            console.log("[desc] container=" + c);
            try { dumpBase(c); } catch (e) { console.log("[base error] " + e); }
            if (SCAN) { try { scan(c); } catch (e) { console.log("[scan error] " + e); } }
            console.log("[done] " + key);
        }
    });
    console.log("[+] hooked method lookup @ " + lib.base.add(0x9d46f8));
}
