import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import ssl
import struct
import threading
import time

import athlete_requests  # client->server Athlete calls by name (server/athlete_requests.py)
import account_link  # RoS_Server account link (/api/v1/gateway); off when GATEWAY_API_KEY is empty
import bwdefs   # BigWorld .def parser (server/bwdefs.py)
import profile_screens  # My Page / Stats / Credit replies (server/profile_screens.py)

CERT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")
HTTPS_PORT = 443

HOST_IP = "0.0.0.0"          # Listen on all interfaces
LOCAL_SERVER_IP = os.environ.get("ROS_PC_IP", "192.168.1.18")  # match real/server_list_ad.local.txt
HTTP_PORT = 80
GATE_TCP_PORT = 20001
CURRENT_BF_KEY = None
CURRENT_SESSION_U32 = None

# Hosts still alive at NetEase: requests are passed through to the real server (resolved via 8.8.8.8).
PASSTHROUGH_HOSTS = {
    "whoami.nie.easebar.com", "who.nie.easebar.com",
}
_real_ip_cache = {}

# The host-patched APK (decompile/tools/patch_hosts.py, hosts_map.example.json) swaps the TLD
# of NetEase hosts with a same-length one. Map them back for forging rules and passthrough.
_TLD_SWAP = (("easebar.lan", "easebar.com"), ("netease.lan", "netease.com"),
             ("rulesofsurvivalgame.lan", "rulesofsurvivalgame.com"))


def canonical_host(host):
    host = (host or "").split(":")[0].lower()
    # public build (vokdev.com): "<label>e.vokdev.com" = "<label>.easebar.com", "<label>n.vokdev.com" = "<label>.netease.com"
    if host.endswith(".vokdev.com"):
        lab = host[: -len(".vokdev.com")]
        if lab == "wwwrulesofsurviv":
            return "www.rulesofsurvivalgame.com"
        if len(lab) > 1 and lab[-1] == "e" and "." in host[:-1]:
            return lab[:-1] + ".easebar.com"
        if len(lab) > 1 and lab[-1] == "n":
            return lab[:-1] + ".netease.com"
        return host
    for patched, real in _TLD_SWAP:
        if host.endswith(patched):
            return host[: -len(patched)] + real
    return host


def resolve_real(host):
    """Resolve host via public DNS (our own DNS server would answer with the PC IP)."""
    if host in _real_ip_cache:
        return _real_ip_cache[host]
    import socket as s, struct, random
    q = struct.pack(">HHHHHH", random.randint(0, 65535), 0x0100, 1, 0, 0, 0)
    q += b"".join(bytes([len(p)]) + p.encode() for p in host.split(".")) + b"\x00" + struct.pack(">HH", 1, 1)
    sock = s.socket(s.AF_INET, s.SOCK_DGRAM); sock.settimeout(3)
    sock.sendto(q, ("8.8.8.8", 53)); resp = sock.recv(4096); sock.close()
    # take the last A record in the answer section
    ip = None
    i = len(resp) - 1
    for off in range(12, len(resp) - 10):
        if resp[off:off + 4] == b"\x00\x01\x00\x01" and resp[off + 8:off + 10] == b"\x00\x04":
            ip = ".".join(str(b) for b in resp[off + 10:off + 14])
    _real_ip_cache[host] = ip
    return ip


def passthrough(handler, body=None):
    import http.client, socket as s
    host = canonical_host(handler.headers.get("Host"))
    ip = resolve_real(host)
    https = isinstance(handler.connection, ssl.SSLSocket)
    if https:
        conn = http.client.HTTPSConnection(host, 443, timeout=15, context=ssl._create_unverified_context())
        raw = s.create_connection((ip, 443), timeout=15)
        conn.sock = conn._context.wrap_socket(raw, server_hostname=host)
    else:
        conn = http.client.HTTPConnection(ip, 80, timeout=15)
    headers = {k: v for k, v in handler.headers.items() if k.lower() not in ("connection", "accept-encoding", "host")}
    headers["Host"] = host
    conn.request(handler.command, handler.path, body=body, headers=headers)
    r = conn.getresponse()
    data = r.read()
    print(f"  -> PASSTHROUGH {host} ({ip}) {r.status} {data[:300]!r}")
    handler.send_response(r.status)
    for k, v in r.getheaders():
        if k.lower() not in ("transfer-encoding", "connection", "content-length"):
            handler.send_header(k, v)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class RoSHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean console logging of every incoming request from the game
        print(f"[HTTP {self.command}] Host: {self.headers.get('Host')} | Path: {self.path}")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        ua = self.headers.get("User-Agent", "")
        print(f"[GET] https?={isinstance(self.connection, ssl.SSLSocket)} Host={self.headers.get('Host')} Path={self.path} UA={ua[:80]}")
        account_link.note_device(self.path, ua)  # model, OS, version, time zone for the next login
        path_lower = self.path.lower()
        host_only = canonical_host(self.headers.get("Host"))
        if host_only.endswith("mpsdk.easebar.com") and path_lower.startswith("/api/games/config"):
            fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real", "games_config.json")
            with open(fpath, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "game_config" in cfg and "account_type" in cfg["game_config"]:
                if "guest" in cfg["game_config"]["account_type"]:
                    cfg["game_config"]["account_type"]["guest"]["enable"] = True
            body = json.dumps(cfg).encode()
            print(f"[FORGE games/config] -> {len(body)} bytes")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # Cached-guest re-validation: NetEase answers 2003 "User does not exist", which the
        # client shows as "Slow connection". Forge the same user record as /users/login/.
        if host_only.endswith("mpsdk.easebar.com") and path_lower.startswith("/api/games/user/info"):
            import time as _t
            uid = account_link.device_uid(self.path)
            body = json.dumps({
                "code": 0, "alert_type": 0, "msg": "ok",
                "user": {"id": uid, "token": "localguesttoken0001", "username": "GuestLocal",
                         "nickname": "GuestLocal", "login_channel": "guest", "login_type": 7,
                         "is_guest": True, "is_bind": False, "avatar": "", "pc_ext_info": "",
                         "create_time": int(_t.time())},
            }).encode()
            print(f"[FORGE user/info] -> {body[:160]!r}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if host_only.endswith("mpsdk.easebar.com"):
            body = json.dumps({"code": 0, "alert_type": 0, "msg": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if host_only in PASSTHROUGH_HOSTS:
            print(f"  headers: {dict(self.headers)}")
            return passthrough(self)

        # 0. Static files captured from the real update server (real/ folder)
        if "query_product" in path_lower:
            qp_resp = {
                "code": 200,
                "res_code": 200,
                "status": 0,
                "msg": "ok",
                "product_list": [],
                "products": [],
            }
            body = json.dumps(qp_resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        static_map = {
            "/pl/h45na_hc": ("h45na_hc", "application/octet-stream"),
            "/pl/npk_version_na_android.plist": ("npk_version_na_android.patched.plist", "text/plain"),
            "/server_list_ad.txt": (os.environ.get("SERVER_LIST_FILE", "server_list_ad.local.txt"), "text/plain"),
            "/notice_pc_hw.txt": ("notice_pc_hw.txt", "text/plain"),
        }
        route = static_map.get(self.path.split("?")[0])
        if route:
            fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real", route[0])
            with open(fpath, "rb") as f:
                body = f.read()
            print(f"  -> Serving real/{route[0]} ({len(body)} bytes)")
            self.send_response(200)
            self.send_header("Content-Type", route[1])
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 1. Catch Patch List / Version Check Requests
        if "patch" in path_lower or "version" in path_lower or "update" in path_lower:
            print(f"  -> Serving Patch Manifest (Up-to-date) for {self.path}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            # Standard NeoX / NetEase patcher up-to-date response structure
            patch_response = {
                "code": 200,
                "status": 0,
                "need_update": False,
                "latest_version": "1.610637.617289",
                "engine_version": "1.610637",
                "res_version": "617289",
                "patch_list": [],
                "filelist": []
            }
            self.wfile.write(json.dumps(patch_response).encode("utf-8"))
            return

        # 2. Catch Server List Requests (Loaded right after patch check finishes)
        if "server" in path_lower or "list" in path_lower:
            print(f"  -> Serving Server List pointing to {LOCAL_SERVER_IP}:{GATE_TCP_PORT}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            server_list = {
                "code": 200,
                "servers": [
                    {
                        "id": 1,
                        "name": "Local Emulator Server",
                        "ip": LOCAL_SERVER_IP,
                        "port": GATE_TCP_PORT,
                        "status": 1,       # 1 = Online / Green
                        "recommend": 1
                    }
                ]
            }
            self.wfile.write(json.dumps(server_list).encode("utf-8"))
            return

        # 3. Default Catch-All (UniSDK / Announcements / Notices)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"code": 200, "status": 1, "msg": "OK"}).encode("utf-8"))

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)
        host = canonical_host(self.headers.get("Host"))
        account_link.note_device(self.path, self.headers.get("User-Agent", ""))

        # Forge login success: NetEase's live server returns 1003 "service stopped" (guest)
        # or 2003 "User does not exist" (auto-login sdk_token re-validation).
        if host.endswith("mpsdk.easebar.com"):
            import time as _t
            uid = account_link.device_uid(self.path)
            forged = {
                "code": 0, "alert_type": 0, "msg": "ok",
                "user": {
                    "id": uid, "token": "localguesttoken0001",
                    "username": "GuestLocal", "nickname": "GuestLocal",
                    "login_channel": "guest", "login_type": 7, "is_guest": True,
                    "is_bind": False, "avatar": "", "pc_ext_info": "",
                    "create_time": int(_t.time()),
                },
                "config": {},
            }
            if "/api/devices/init" in self.path.lower():
                # mpay DeviceRequest parses response["device"]["id"]; without it the SDK shows "Slow connection".
                forged["device"] = {"id": f"{uid}-local-device"}
            body = json.dumps(forged).encode()
            print(f"[FORGE mpsdk-post] uid={uid} {self.path} -> {body[:200]!r}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if "query_product" in self.path.lower():
            qp_resp = {
                "code": 200,
                "res_code": 200,
                "status": 0,
                "msg": "ok",
                "product_list": [],
                "products": [],
            }
            body = json.dumps(qp_resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if host in PASSTHROUGH_HOSTS:
            print(f"[POST passthrough] {self.headers.get('Host')}{self.path} body={post_body[:300]!r}")
            return passthrough(self, post_body)
        print(f"[HTTP POST] Host: {self.headers.get('Host')} | Path: {self.path} | Body: {post_body[:200]}")

        # UniSDK Token / Login Verification
        auth_response = {
            "code": 200,
            "status": 1,
            "uid": "100001",
            "token": "local_token_123456",
            "username": "LocalPlayer",
            "msg": "ok",
            "data": {},
            "product_list": [],
        }
        body = json.dumps(auth_response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# Asyncio Raw TCP Listener for the NeoX Gate/Lobby Connection
async def handle_gate_client(reader, writer):
    addr = writer.get_extra_info('peername')
    port = writer.get_extra_info('sockname')[1]
    print(f"\n[TCP GATE:{port}] Connection from {addr}")
    root = os.path.dirname(os.path.abspath(__file__))
    tcp_log = os.path.join(root, "tcp_gate_capture.bin")
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            print(f"[TCP GATE:{port}] {len(data)}B: {data[:128].hex()}{'...' if len(data)>128 else ''}")
            with open(tcp_log, "ab") as f:
                f.write(struct.pack("<H", len(data)))
                f.write(data)
            # Stay open; real gate handshake TBD (see tcp_gate_capture.bin). Optional no-op ack:
            if os.environ.get("TCP_GATE_ECHO", "off") == "on":
                writer.write(data)
                await writer.drain()
    except Exception as e:
        print(f"[TCP GATE:{port}] error: {e}")
    finally:
        print(f"[TCP GATE:{port}] closed {addr}")
        writer.close()

def _bw_blob(b):
    """BigWorld STRING/BLOB: packed length (u8, or 0xFF + u24 LE) + bytes."""
    if isinstance(b, str):
        b = b.encode()
    if len(b) < 255:
        return bytes([len(b)]) + b
    return b"\xff" + struct.pack("<I", len(b))[:3] + b


def build_base_player_props(kind):
    """BASE_AND_CLIENT property stream for createBasePlayer, in .def order
    (Implements first, then own Properties). Derived from extract/entities_out defs:
      iProxy (269): playerUUID BLOB, playerName BLOB, bindedPlayerName BLOB,
                    identifierName BLOB, baseNickname BLOB, gid UINT64
      Account (158): isMobileAccount BOOL
    Override with CBP_PROPS_HEX for experiments."""
    hx = os.environ.get("CBP_PROPS_HEX")
    if hx is not None:
        return bytes.fromhex(hx)
    name = os.environ.get("CBP_NAME", "GuestLocal")
    gid = account_link.current_gid()
    iproxy = (_bw_blob(bytes(range(16))) + _bw_blob(name) + _bw_blob(b"") +
              _bw_blob(name) + _bw_blob(name) + struct.pack("<Q", gid))
    if kind == "account":
        return iproxy + b"\x00"                     # isMobileAccount = False
    if kind == "iproxy":
        return iproxy
    return b""


# BaseAppExtInterface (client->server) message sizes: id -> fixed length, or None = var16.
# 0xC0+n are exposed base-method calls (var16), e.g. 0xC5 = Account.handshake.
_BASEAPP_EXT_MSGS = {
    0x00: None, 0x01: 4, 0x02: 24, 0x03: 32, 0x04: 24, 0x05: 32,
    0x06: 0, 0x07: None, 0x08: 8, 0x09: 8, 0x0A: 8, 0x0B: 4,
    0x0C: None, 0x0D: None, 0x0E: None, 0x0F: 1, 0x10: 1, 0x11: None,
}
_BASEAPP_EXT_MSGS.update({i: None for i in range(0x80, 0x100)})   # 0x80-0xBF: cell-method calls (var16)


def client_method_ex(index, n_methods, entity_id, args):
    """Like client_method, for entity types with many client methods. The client's exposed
    lookup (libclient+0x9d46f8) uses efficient = 62 - (n+192)//255; indices beyond it are
    sent as msg 0xC0 + efficient + (k >> 8) plus one sub-index byte (k & 0xff) after the
    entity id, where k = index - efficient. (Athlete: n = 1438 -> efficient 56.)"""
    if os.environ.get("METHOD_EXT", "subindex") == "bits":
        # Decoder libclient+0x9a4600: idx <= 60 is used directly; idx 61 (msg 0xFD, var16)
        # is followed by a bit stream (MSB first): the method index in ceil(log2(n)) bits,
        # then a 1-bit "nested" flag (0). Args start at the next whole byte.
        if index <= 60:
            return client_method(index, entity_id, args)
        nbits = max(1, (n_methods - 1).bit_length())
        val = (index << 1) | 0                      # index bits + 1 stop bit
        total = nbits + 1
        nbytes = (total + 7) // 8
        packed = (val << (nbytes * 8 - total)).to_bytes(nbytes, "big")
        return _entity_msg(int(os.environ.get("METHOD_BASE", "0x80"), 0) | 61, struct.pack("<I", entity_id) + packed + args)
    eff = 62 - (n_methods + 192) // 255
    if index < eff:
        return client_method(index, entity_id, args)
    k = index - eff
    payload = struct.pack("<I", entity_id) + bytes([k & 0xFF]) + args
    return _entity_msg(int(os.environ.get("METHOD_BASE", "0x80"), 0) | (eff + (k >> 8)), payload)


def _entity_msg(msgid, payload):
    """Length width per id (registration loop @+0x93d150): 0xC0-0xFC use the
    shortEntityMessage template (var8); 0x80-0xBF and 0xFD-0xFF use longEntityMessage (var16)."""
    if 0xC0 <= msgid <= 0xFC:
        if len(payload) > 255:
            raise ValueError("entity message too long for var8")
        return bytes([msgid, len(payload)]) + payload
    return bytes([msgid]) + struct.pack("<H", len(payload)) + payload


_ATHLETE_METHODS = None


def athlete_method(name, args, quiet=False):
    """Athlete client-method call by name (index from the raw .def parse order, 1438 entries
    = the client's own 'client method count')."""
    global _ATHLETE_METHODS
    if _ATHLETE_METHODS is None:
        tab = bwdefs.Defs().methods("Athlete", "ClientMethods")
        _ATHLETE_METHODS = ({m[0]: i for i, m in reversed(list(enumerate(tab)))}, len(tab))
    idx, n = _ATHLETE_METHODS
    eid = int(os.environ.get("ATHLETE_ID", "10002"))
    if not quiet:
        print(f"      [BASEAPP] -> Athlete.{name} (client idx {idx[name]}/{n})")
    return client_method_ex(idx[name], n, eid, args)


def client_method(index, entity_id, args):
    """Server->client entity method call (EntityMessageHandler, libclient+0x94bbf0):
    msg id 0xC0 | index (index < 0x3f), **var8** length (confirmed: a var16 length desyncs the
    bundle), then entity id u32 (no entity pre-selected), then args."""
    payload = struct.pack("<I", entity_id) + args
    return _entity_msg(int(os.environ.get("METHOD_BASE", "0x80"), 0) | index, payload)


def parse_client_bundle(pkt):
    """Split a decrypted client packet into [(msg_id, payload)] (stops at unknown ids).
    Footer layout: [seq u32 if 0x40][acks u32 * n][nAcks u8 if 0x04]."""
    if len(pkt) < 2:
        return []
    flags = struct.unpack("<H", pkt[:2])[0]
    end = len(pkt)
    if flags & 0x0004:
        end -= 1 + 4 * pkt[-1]
    if flags & 0x0040:
        end -= 4
    i, out = 2, []
    while i < end:
        mid = pkt[i]
        i += 1
        if mid not in _BASEAPP_EXT_MSGS:
            out.append((mid, pkt[i:end]))
            break
        ln = _BASEAPP_EXT_MSGS[mid]
        if ln is None:
            ln = struct.unpack_from("<H", pkt, i)[0]
            i += 2
        out.append((mid, pkt[i:i + ln]))
        i += ln
    return out


def avatar_create_messages(map_id=None, char_type=None, name=None, entity=None):
    """Tutorial route: hand the client to a battle Avatar (client type 43).
    PlayerAvatar.onBecomePlayer -> MapLoader.onHandshake -> loadMap(currentMapID) loads the map
    itself (const.DTS_TUTORIAL_MAP = 701); PlayerAvatar.prerequisites only needs a scene, so the
    player can enter once the map is up. Returns createBasePlayer + createCellPlayer messages."""
    import pickle as _pk
    D = bwdefs.Defs()
    name = (name or os.environ.get("CBP_NAME", "GuestLocal")).encode()
    gid = account_link.current_gid()
    map_id = int(map_id or os.environ.get("AVATAR_MAP", "701"))
    char_type = int(char_type or os.environ.get("AVATAR_CHAR", "30001"))
    ov = {
        "playerUUID": bwdefs.blob(bytes(range(16))),
        "playerName": bwdefs.blob(name), "identifierName": bwdefs.blob(name),
        "baseNickname": bwdefs.blob(name), "gid": struct.pack("<Q", gid),
        "currentMapID": struct.pack("<i", map_id),
        # characterType: 0 -> characterInfo None (GENDER); 10001 has no dts_model_path on BG maps;
        # 20001 (dataosha_male) loads 35-80s on LDPlayer > 40s inactivity; 30001 bot_base loads in 1.4s
        "baseCharacterType": struct.pack("<I", char_type),
        "msHttpAP": bwdefs.blob(_pk.dumps((LOCAL_SERVER_IP, 443, 80), protocol=2)),
    }
    log_b, log_c = [], []
    ent = entity or os.environ.get("AVATAR_ENTITY", "Avatar")
    import json as _json
    types_ = _json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "extract", "client_entity_types.json")))
    base = bwdefs.stream_for(D, ent, ov, log_b)
    # campType FIXED_DICT(camp u8, legionGID u64, teamID u64, campWarID u8); camp 0 is invalid
    # (camp_utils.isEnemy KeyError 0). CampType.AvatarSolo = 30.
    camp = int(os.environ.get("AVATAR_CAMP", "30"))
    cell_ov = {"mapID": struct.pack("<i", map_id), "characterType": struct.pack("<I", char_type),
               "campType": struct.pack("<BQQB", camp, 0, int(os.environ.get("AVATAR_TEAM", "1")), 0)}
    # iAirWar equipment: the client tests `x is not None` then indexes ['itemID'] / ['active'],
    # so "nothing equipped" must be None, not the PYTHON fallback {} (UIPanelAirWar KeyErrors).
    # NOTE: currEquipDtsParagliding uses len(), so it stays {} (the default).
    _none = bwdefs.blob(_pk.dumps(None, protocol=2))
    for _p in ("curJetBag", "curJetBagCooler", "curJetBagStabilizer", "curRocketShose",
               "jumpRobotCombinationInfo"):
        cell_ov.setdefault(_p, _none)
    # Default bare-hands/cold weapon: 1301 = DEFAULT_COLD_WEAPON (fist).
    # dtsWeapon5 = HAND_WEAPON_SLOT (5), dtsCurWeapon = 5.
    cell_ov.setdefault("dtsWeapon3", struct.pack("<i", 1301))
    cell_ov.setdefault("dtsWeapon5", struct.pack("<i", 1301))
    cell_ov.setdefault("dtsCurWeapon", struct.pack("<i", 5))
    cell = bwdefs.stream_for(D, ent, cell_ov, log_c, props=D.cell_own_client_props(ent))
    eid = int(os.environ.get("AVATAR_ID", "10003"))
    cbp = struct.pack("<IH", eid, types_.index(ent)) + base
    x, y, z = (float(v) for v in os.environ.get("AVATAR_POS", "0,0,0").split(","))
    ccp = struct.pack("<II", int(os.environ.get("CCP_SPACE", "1")), 0) + struct.pack("<3f", x, y, z) \
        + struct.pack("<3f", 0.0, 0.0, 0.0) + cell
    print(f"[*] {ent} (type {types_.index(ent)}) streams: base {len(log_b)} props {len(base)}B, cell {len(log_c)} props {len(cell)}B, map {map_id}")
    return (b"\x05" + struct.pack("<H", len(cbp)) + cbp,
            b"\x06" + struct.pack("<H", len(ccp)) + ccp)


_ATHLETE_STREAM = None


def _encode_pkg_items(bwdefs, items, capacity, with_weight=False):
    """Wire-encode DTS_ROS2_*_PACKAGE3 / appearance package itemList FIXED_DICT."""
    import pickle as _pk
    def _item(it):
        uid = it.get("uuid") or bytes([it["itemID"] & 0xFF]) + os.urandom(15)
        info = it.get("info", {})
        return (bwdefs.blob(uid) + struct.pack("<ii", int(it["itemID"]), int(it.get("number", 1)))
                + bwdefs.blob(_pk.dumps(info, protocol=2)))
    body = struct.pack("<I", len(items)) + b"".join(_item(i) for i in items)
    body += bwdefs.blob(_pk.dumps({}, protocol=2))  # layoutInfo
    body += struct.pack("<I", int(capacity))
    if with_weight:
        body += struct.pack("<I", 0)
    return body


def _all_appearance_ids():
    """Every appearance/skin prop id of the client's hall-prop table (extract/hall_props.json)."""
    try:
        d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "extract", "hall_props.json")))
        return list(d.get("appearance_ids", []))
    except Exception as e:
        print(f"[*] hall_props.json unavailable: {e}")
        return []


def _all_emoji_ids():
    try:
        d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "extract", "hall_props.json")))
        return list(d.get("by_type", {}).get("EmojiType", []))
    except Exception:
        return []


def _all_action_ids():
    try:
        d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "extract", "hall_props.json")))
        by_type = d.get("by_type", {})
        return list(by_type.get("InGameActionAppearanceType", [])), list(by_type.get("InGameActionSuitAppearanceType", []))
    except Exception:
        return [], []


def _encode_appearance_pkg(bwdefs, ids, capacity):
    """DTS_APPEARANCE_PACKAGE3: itemList, itemsList(PYTHON array), layoutInfo, _packageCapacity."""
    import pickle as _pk
    items = b"".join(
        bwdefs.blob(os.urandom(16)) + struct.pack("<ii", int(i), 1) + bwdefs.blob(_pk.dumps({"ex_tm": 0}, protocol=2))
        for i in ids)
    return (struct.pack("<I", len(ids)) + items + struct.pack("<I", 0)
            + bwdefs.blob(_pk.dumps({}, protocol=2)) + struct.pack("<I", int(capacity)))


def _parse_seed_items(env_key):
    """ATHLETE_SEED_ITEMS=itemId[:count][,itemId[:count]...] -> [{itemID, number}, ...]"""
    raw = os.environ.get(env_key, "").strip()
    if not raw:
        return []
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            iid, n = part.split(":", 1)
            out.append({"itemID": int(iid), "number": int(n)})
        else:
            out.append({"itemID": int(part), "number": 1})
    return out


ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_accounts.json")


def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ACC] load_accounts error: {e}")
            return {}
    return {}


def save_account(key, data):
    accs = load_accounts()
    accs[str(key)] = data
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accs, f, indent=2)
    except Exception as e:
        print(f"[ACC] save_account error: {e}")


def is_new_account():
    if os.environ.get("FORCE_NEW_ACCOUNT", "0") == "1":
        return True
    linked = account_link.current()
    if linked:                                     # RoS_Server account is the source of truth
        return bool(linked["is_new"])
    if os.environ.get("TEST_ACCOUNT_NAME"):        # fixed test account: always existing
        return False
    accs = load_accounts()
    acc = accs.get("default")
    if not acc or not acc.get("name"):
        return True
    return False


def _portrait_key():
    return "portrait:" + str(account_link.current_gid())


def get_account_portrait():
    """FilePicker file id of the player's uploaded avatar ("" = built-in by character type)."""
    linked = account_link.current()
    if linked and linked.get("portrait") is not None:
        return linked["portrait"]
    v = load_accounts().get(_portrait_key())
    return v if isinstance(v, str) else ""


def _inventory_key():
    return "inventory:" + str(account_link.current_gid())


def local_state():
    """Owned appearance items, equipped outfit (all lists + lobby theme) and diamonds saved on
    this server (saved_accounts.json), same shape as account_link.get_state():
    {"yuanbao", "items": [{"prop_id"}], "outfit": {body, wear, weapon, vehicle, theme}}."""
    v = load_accounts().get(_inventory_key()) or {}
    return {"yuanbao": int(v.get("yuanbao", int(os.environ.get("ATHLETE_FREE_YUANBAO", "50000"))
                                     + int(os.environ.get("ATHLETE_PAY_YUANBAO", "50000")))),
            "items": [{"prop_id": int(i)} for i in v.get("items", [])],
            "outfit": dict(v.get("outfit") or {})}


def save_local_state(yuanbao=None, add_items=(), outfit=None):
    v = load_accounts().get(_inventory_key()) or {}
    if yuanbao is not None:
        v["yuanbao"] = int(yuanbao)
    if add_items:
        owned = [int(i) for i in v.get("items", [])]
        for i in add_items:
            if int(i) not in owned:
                owned.append(int(i))
        v["items"] = owned
    if outfit is not None:
        v["outfit"] = outfit
    save_account(_inventory_key(), v)


def _gender_key():
    return "gender:" + str(account_link.current_gid())


def get_account_gender():
    """Hall appearance gender (dtsAppearanceGender: 1 male, 2 female) and the body parts
    (face/hair...) remembered for each gender: (gender, {"1": [...], "2": [...]})."""
    v = load_accounts().get(_gender_key()) or {}
    g = int(v.get("gender", os.environ.get("ATHLETE_GENDER", "1")))
    return (g if g in (1, 2) else 1), dict(v.get("body") or {})


def set_account_gender(gender, body_by_gender):
    save_account(_gender_key(), {"gender": int(gender), "body": body_by_gender})


def set_account_portrait(file_id):
    save_account(_portrait_key(), file_id)         # local copy (works without RoS_Server)
    if account_link.current() and not account_link.set_portrait(file_id):
        print(f"      [ACC-LINK] portrait '{file_id}' not saved to RoS_Server")


def _child_props_with_portrait(D, portrait):
    """childBaseClientPropertyList (ARRAY of one FIXED_DICT): defaults + portrait + game-clock
    times. signAwardTime = now means "signed in today": iDtsSignin.onCheckEnterSignInUI opens
    the sign-in popup (UIDtsSign) when checkDtsSigninNotSameDay() and signAwardLevel < max,
    and with no sign-in data served that popup is an empty mask that blocks the lobby."""
    now = int(athlete_requests.game_now())
    times = {"signAwardTime": struct.pack("<q", now), "signAwardRefreshTime": struct.pack("<q", now + 86400),
             "luckySeasonEndTime": struct.pack("<i", now + 30 * 86400),
             "luckyRoundRefreshTime": struct.pack("<i", now + 21600),
             "luckyRoundCloseTime": struct.pack("<i", now + 172800)}
    for prop, ttext, _flags, _owner in D.base_client_props("Athlete"):
        if prop == "childBaseClientPropertyList":
            fields = D.resolve(ttext)[1][1]
            elem = b"".join(bwdefs.blob(portrait.encode()) if name == "portrait"
                            else times.get(name) or bwdefs.encode_default(sub, fdef) for name, sub, fdef in fields)
            return struct.pack("<I", 1) + elem
    return None


# Daily sign-in rewards by day (client legacyProperties.iterDtsSigninData, days 1-5).
SIGNIN_AWARDS = [200027, 203011, 200012, 203012, 291210]


def _first_login_today():
    """enterHall(BOOL firstLoginToday): True makes UIMgr.enterHallUI run the login popups
    (daily sign-in UIDtsSign, recruit/recall, weekly supply push, ...). The sign-in popup needs
    childBaseClientPropertyList, which cannot be sent yet, and then blocks the lobby as an
    empty mask. HALL_POPUPS: off (default) / daily (first login per game day) / on."""
    mode = os.environ.get("HALL_POPUPS", "off")
    if mode == "on":
        return b"\x01"
    if mode == "daily":
        import time as _t
        day = _t.strftime("%Y-%m-%d", _t.gmtime(athlete_requests.game_now()))
        if (load_accounts().get("login_day") or {}).get("day") != day:
            save_account("login_day", {"day": day})
            return b"\x01"
    return b"\x00"

PROFILE_REQUESTS = {"requireRecordData", "requireBaseInfo", "queryPersonalInfo", "queryPersonalSpaceLikeCnt",
                    "queryCreditStatus", "queryCreditScore", "requireCreditReward"}


def get_account_name():
    linked = account_link.current()
    if linked and not linked["is_new"]:
        return linked["nickname"]
    if os.environ.get("TEST_ACCOUNT_NAME"):
        return os.environ["TEST_ACCOUNT_NAME"]
    accs = load_accounts()
    acc = accs.get("default", {})
    return acc.get("name", os.environ.get("CBP_NAME", "GuestLocal"))


def link_login(username, ip_address):
    """Resolve the RoS_Server account for a Mercury login. Returns False if the account may not play."""
    uid = account_link.note_login(username)
    if not account_link.enabled():
        return True
    linked = account_link.resolve(uid, ip_address)
    if not linked:
        return True                                # API down: keep playing on local accounts
    if not linked["can_play"]:
        print(f"[ACC-LINK] {linked['username']} is {linked['status']}: login refused")
        return False
    account_link.touch(uid)
    test_name = os.environ.get("TEST_ACCOUNT_NAME")
    if linked["is_new"] and test_name:
        # Fixed test account: skip the in-game character screen, as before the link existed.
        char = int(os.environ.get("ATHLETE_CHAR", "20001"))      # 30001 is the robot placeholder
        if not account_link.set_character(test_name, char):
            account_link.set_character(f"{test_name}_{uid[-4:]}", char)
    return True


def get_account_char():
    linked = account_link.current()
    if linked and linked.get("char_type") is not None:
        char = int(linked["char_type"])
    else:
        acc = load_accounts().get("default", {})
        char = int(acc.get("char_type", int(os.environ.get("ATHLETE_CHAR", "20001"))))
    # 30001 = bot_base, the robot placeholder (its table GENDER is 2, so the ♀ switch used to
    # keep it): never a player body; use the human of the saved gender instead.
    if char in ROBOT_CHARS:
        char = GENDER_CHAR[get_account_gender()[0] if get_account_gender()[0] in GENDER_CHAR else 1]
    return char


# Character type GENDER from the client's character table (legacyProperties.getCharactersData).
CHAR_GENDER = {10001: 1, 10002: 1, 20001: 1, 20002: 2, 30001: 2}
# Hall body used when the ♂/♀ switch needs a character of the other gender.
GENDER_CHAR = {1: int(os.environ.get("MALE_CHAR", "20001")), 2: int(os.environ.get("FEMALE_CHAR", "20002"))}
ROBOT_CHARS = {30001}


def current_gender():
    """dtsAppearanceGender: the character type's own GENDER, else the saved switch."""
    return CHAR_GENDER.get(get_account_char()) or get_account_gender()[0]


def set_account_char(char_type):
    """Store the character type locally and on RoS_Server (keeps the nickname)."""
    acc = load_accounts().get("default") or {}
    acc["char_type"] = int(char_type)
    save_account("default", acc)
    if account_link.current() and not account_link.set_character(get_account_name(), int(char_type)):
        print(f"      [ACC-LINK] character type {char_type} not saved to RoS_Server")


def build_custom_room_info(room_name, creator_name, gid, map_id=1, team_size=4):
    import pickle
    b = bwdefs.blob(room_name.encode())
    b += bwdefs.blob(creator_name.encode())
    b += bwdefs.blob(b"US")
    b += struct.pack("<Q", gid)
    b += b"\x00"
    b += struct.pack("<i", 1001)
    b += struct.pack("<i", team_size)
    b += struct.pack("<i", 1)
    member_b = bwdefs.blob(creator_name.encode()) + struct.pack("<Q", gid) + bwdefs.blob(b"US")
    b += struct.pack("<I", 1) + member_b
    b += bwdefs.blob(pickle.dumps({}, protocol=2))
    b += b"\x00"
    b += struct.pack("<I", 0)
    b += struct.pack("<i", map_id)
    b += b"\x00"
    return b


HALL_TEAM_MAP_GROUP = 1   # const.DtsMapBaseType.MAP_4K (client default, map 700)
LOGIN_STATE = None   # RoS_Server gateway state of the account logging in (account_link.get_state)


def login_yuanbao():
    if LOGIN_STATE is not None:
        return int(LOGIN_STATE.get("yuanbao", 0))
    return int(os.environ.get("ATHLETE_FREE_YUANBAO", "50000")) + int(os.environ.get("ATHLETE_PAY_YUANBAO", "50000"))


# Outfit list -> (equipped, shown) Athlete properties, and the client methods updating them.
LIST_PROPS = {"body": ("dtsBodyAppearanceList", "dtsShowBodyAppearanceList"),
              "wear": ("dtsWearableAppearanceList", "dtsShowWearableAppearanceList"),
              "weapon": ("dtsWeaponAppearanceList", "dtsShowWeaponAppearanceList"),
              "vehicle": ("dtsVehicleAppearanceList", "dtsShowVehicleAppearanceList")}
LIST_METHODS = {"body": ("onUpdateDtsBodyAppearanceList", "onUpdateDtsShowBodyAppearanceList"),
                "wear": ("onUpdateDtsWearableAppearanceList", "onUpdateDtsShowWearableAppearanceList"),
                "weapon": ("onUpdateDtsWeaponAppearanceList", "onUpdateDtsShowWeaponAppearanceList"),
                "vehicle": ("onUpdateVehicleAppearanceList", "onUpdateDtsShowVehicleAppearanceList")}


def athlete_create_message():
    """createBasePlayer for the hall player: Athlete (client type 56), all 720 BASE_AND_CLIENT
    props in .def parse order (bwdefs.py), defaults + identity overrides."""
    global LOGIN_STATE
    D = bwdefs.Defs()
    LOGIN_STATE = account_link.get_state() if account_link.current() else None
    local = local_state()
    if LOGIN_STATE is None:                        # not linked: this server's own saved state
        LOGIN_STATE = local
    elif local["outfit"]:                          # RoS_Server keeps body/wear only
        LOGIN_STATE["outfit"] = {**local["outfit"], **{k: v for k, v in (LOGIN_STATE.get("outfit") or {}).items() if v}}
    new_user = is_new_account()
    raw_name = "" if new_user else get_account_name()
    name = raw_name.encode() if raw_name else b""
    gid = account_link.current_gid()
    seed = _parse_seed_items("ATHLETE_SEED_ITEMS")
    cap = int(os.environ.get("ATHLETE_PKG_CAPACITY", "64"))
    char_type = get_account_char()
    ov = {
        "playerUUID": bwdefs.blob(bytes(range(16))),
        "playerName": bwdefs.blob(name), "identifierName": bwdefs.blob(name),
        "baseNickname": bwdefs.blob(name), "gid": struct.pack("<Q", gid),
        "baseLevel": struct.pack("<i", int(os.environ.get("ATHLETE_LEVEL", "1"))),
        "hostID": struct.pack("<i", 10001),
        "msHttpAP": bwdefs.blob(__import__("pickle").dumps((LOCAL_SERVER_IP, 443, 80), protocol=2)),
        "canCreateRoom": struct.pack("<b", int(os.environ.get("ATHLETE_CAN_CREATE_ROOM", "1"))),
        "needNormalRoomTip": struct.pack("<b", 0),
        "needOBRoomTip": struct.pack("<b", 0),
        "baseCharacterType": struct.pack("<I", char_type),
        "dtsAppearanceGender": struct.pack("<i", current_gender()),
        "freeYuanbao": struct.pack("<q", login_yuanbao() if LOGIN_STATE is not None
                                   else int(os.environ.get("ATHLETE_FREE_YUANBAO", "50000"))),
        "payYuanbao": struct.pack("<q", 0 if LOGIN_STATE is not None
                                  else int(os.environ.get("ATHLETE_PAY_YUANBAO", "50000"))),
        **({"dtsAppearancePackage": _encode_appearance_pkg(bwdefs, _all_appearance_ids(), 20000)}
           if os.environ.get("UNLOCK_ALL", "calls") == "stream" else {}),
        "dtsRos2RepertoryPackage": _encode_pkg_items(bwdefs, seed, cap),
        "dtsRos2BattleItemPackage": _encode_pkg_items(bwdefs, seed, cap, with_weight=True),
        "dtsRos2EquipBarPackage": _encode_pkg_items(bwdefs, seed[:7], 7),
        "dtsRos2DfdBattleItemPackage": _encode_pkg_items(bwdefs, [], cap, with_weight=True),
    }
    if LOGIN_STATE is not None:                    # owned items and worn outfit from RoS_Server
        owned = [int(i["prop_id"]) for i in LOGIN_STATE.get("items", [])]
        if owned:
            ov["dtsAppearancePackage"] = _encode_appearance_pkg(bwdefs, owned, 20000)
        arr = lambda ids: struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", int(i)) for i in ids)
        outfit = LOGIN_STATE.get("outfit") or {}
        for kind, (equipped, shown) in LIST_PROPS.items():
            if outfit.get(kind):
                ov[equipped] = ov[shown] = arr(outfit[kind])
        if outfit.get("theme"):
            ov["dtsHallThemeID"] = struct.pack("<i", int(outfit["theme"]))
        print(f"[*] account state: {LOGIN_STATE.get('yuanbao')} diamonds, {len(owned)} items, outfit={outfit}")
    # Sent only with a portrait: a full element currently misaligns the client's stream by
    # 2 bytes within its first ~70 bytes (SequenceDataType "Invalid size" -> EOFError on the
    # following PYTHON props -> login fails). The default (empty array) works.
    portrait = get_account_portrait()
    child = _child_props_with_portrait(D, portrait) if portrait else None
    if child:
        ov["childBaseClientPropertyList"] = child
    cur_raw = os.environ.get("ATHLETE_SEED_CURRENCY", "1:10000,2:1000").strip()
    if cur_raw:
        curs = []
        for part in cur_raw.split(","):
            if ":" not in part:
                continue
            cid, n = part.split(":", 1)
            curs.append(struct.pack("<iq", int(cid), int(n)))
        ov["currencyList"] = struct.pack("<I", len(curs)) + b"".join(curs)
    log = []
    stream = bwdefs.stream_for(D, "Athlete", ov, log)
    if len(stream) + 6 > 65535 and "dtsAppearancePackage" in ov:
        print("[!] Warning: Athlete stream exceeded 64KB! Removing stream appearance items to prevent overflow...")
        del ov["dtsAppearancePackage"]
        log = []
        stream = bwdefs.stream_for(D, "Athlete", ov, log)
    print(f"[*] Athlete base stream: {len(log)} props, {len(stream)} bytes "
          f"(name='{raw_name}' new_user={new_user} char={char_type} cap={cap} canCreateRoom=1)")
    eid = int(os.environ.get("ATHLETE_ID", "10002"))
    payload = struct.pack("<IH", eid, int(os.environ.get("ATHLETE_TYPE", "56"))) + stream
    if len(payload) > 65535:
        raise ValueError(f"Athlete createBasePlayer payload exceeds 65535 bytes: {len(payload)}")
    return b"\x05" + struct.pack("<H", len(payload)) + payload


class GateUDP(asyncio.DatagramProtocol):
    def __init__(self, port):
        self.port = port
        self._login_replied = {}   # addr -> True, to track post-login packets
        self._server_seq = 0
        self._player_created = {}  # addr -> True once createBasePlayer sent on this channel
        self._last_client_seq = {}  # addr -> latest reliable client seq (for keepalive re-ACKs)
        self._unacked_packets = {}  # addr -> {seq: {'fl', 'body', 'footer_prefix', 'time'}}
        self._handshake_done = {}   # addr -> True once Account.handshake was answered
        self._athlete_sent = {}     # addr -> True once Athlete transition sent
        self._hall_entered = {}     # addr -> True once Athlete hall entry calls sent
        self._last_recv = {}        # addr -> time of the last BaseApp packet from the client
        self._last_sent_ka = {}     # addr -> time of last sent keepalive ACK
        self._ka_gen = 0            # bumped per BaseApp login; stale keepalive timers stop
        self._supply = {}           # addr -> athlete_requests.SupplyState
        self._wallet = {}           # addr -> athlete_requests.Wallet
        self._outfit = {}           # addr -> athlete_requests.Outfit
        self._owned_items = {}      # addr -> set of owned appearance prop ids
        self._team = {}             # addr -> hall team mode (createHallTeam)
        self._in_battle = {}        # addr -> handed to the battle Avatar (Athlete decoding off)
        self._last_bf = {}          # addr -> BF key of the latest packet (for delayed sends)
    def connection_made(self, transport):
        self.transport = transport
    def datagram_received(self, data, addr):
        import time as _t
        account_link.touch()  # presence lease for the linked player (no I/O on this path)
        is_login = data[:4] == b"\x01\x00\x00\x84"

        if is_login:
            print(f"[UDP GATE:{self.port}] LOGIN from {addr} {len(data)}B seq={data[5:7].hex()}")
        else:
            print(f"[UDP GATE:{self.port}] NON-LOGIN from {addr} {len(data)}B: {data.hex()}")

        # Always capture to gate_capture.bin
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gate_capture.bin"), "ab") as f:
            f.write(data)

        # --- Login reply handler ---
        reply_variant_env = os.environ.get("REPLY_VARIANT", "24")
        if self.port == 25000 and is_login and reply_variant_env != "off":
            try:
                import loginapp, importlib
                importlib.reload(loginapp)
                if reply_variant_env != "sweep":
                    msgid = int(reply_variant_env)
                else:
                    sf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sweep_msgid.txt")
                    try:
                        msgid = int(open(sf).read().strip())
                    except Exception:
                        msgid = 0
                    with open(sf, "w") as fh:
                        fh.write(str((msgid + 1) & 0xFF))
                res = loginapp.build_reply(data, LOCAL_SERVER_IP, 25000, msgid)
                if res:
                    global CURRENT_BF_KEY
                    pkt, params, bf = res
                    global CURRENT_SESSION_U32
                    CURRENT_BF_KEY = bf
                    CURRENT_SESSION_U32 = loginapp.extract_session_u32(params)
                    if not link_login(params.get("username"), addr[0]):
                        return              # banned/suspended in the admin console: no login reply
                    sk = CURRENT_SESSION_U32.hex()
                    print(f"  [{_t.strftime('%H:%M:%S')}] [LOGIN] TRY msgid={msgid} (0x{msgid:02x}) -> {len(pkt)}B: {pkt.hex()}")
                    print(f"      user={params.get('username')} session_u32={sk} rest={params.get('rest',b'').hex()} bf={bf.hex() if bf else None}")
                    self.transport.sendto(pkt, addr)
                    self._login_replied[addr] = True
            except Exception as e:
                import traceback
                print(f"  [REPLY ERROR] {e}\n{traceback.format_exc()}")
            return

        # --- BaseApp Mercury channel handler ---
        if self.port == 25000 and not is_login:
            ts = _t.strftime('%H:%M:%S')
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "baseapp_capture.bin"), "ab") as f:
                f.write(len(data).to_bytes(2, 'little') + data)

            try:
                import loginapp
                bf_key = CURRENT_BF_KEY
                if not bf_key:
                    try:
                        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_bf_key.bin"), "rb") as f:
                            bf_key = f.read()[:4]
                    except Exception:
                        bf_key = bytes.fromhex("aa6a4a51")

                # Legacy CBC handler for baseAppLogin (0x0b is the msg length, not a magic).
                # Opt-in only: client logs "EncryptionFilter::recv: illegal wastage count" for
                # CBC replies — its filter uses the custom PFB mode (handled below).
                if data[:4] == b"\x01\x00\x00\x0b" and os.environ.get("BASEAPP_PROBE_HANDLER") == "cbc":
                    var = os.environ.get("BASEAPP_REPLY_VARIANT", "1")
                    try:
                        variant = int(var)
                    except ValueError:
                        variant = 1
                    probe_bf = bf_key if os.environ.get("BASEAPP_PROBE_BF", "off") == "on" else None
                    pkt = loginapp.build_baseapp_reply(data, variant, probe_bf)
                    if pkt:
                        self.transport.sendto(pkt, addr)
                        print(
                            f"  [{ts}] [BASEAPP PROBE 0x0b] variant={variant} -> {len(pkt)}B: {pkt.hex()}"
                        )
                    return
                
                # Check if this is a BaseApp login request:
                # flags=0x0001 (HAS_REQUESTS), msg_id=0 (baseAppLogin)
                if data[:3] == b"\x01\x00\x00":
                    req_id_5 = data[5:9]
                    req_id_7 = data[7:11]
                    if CURRENT_SESSION_U32 and len(CURRENT_SESSION_U32) == 4:
                        session_key = CURRENT_SESSION_U32
                    else:
                        session_key = data[11:15] if len(data) >= 15 else struct.pack("<I", 0x11223344)
                    print(f"  [{ts}] [BASEAPP LOGIN REQ] from {addr} req5={req_id_5.hex()} req7={req_id_7.hex()} sess={session_key.hex()} bf={bf_key.hex() if bf_key else None}")
                    # New BaseApp session: reset per-channel state
                    self._player_created.pop(addr, None)
                    self._last_client_seq.pop(addr, None)
                    self._unacked_packets.pop(addr, None)
                    self._handshake_done.pop(addr, None)
                    self._athlete_sent.pop(addr, None)
                    self._hall_entered.pop(addr, None)
                    self._server_seq = 0
                    self._ka_gen += 1
                    if os.environ.get("TIMER_KEEPALIVE", "on") == "on":
                        asyncio.get_event_loop().call_later(
                            1.0, self._keepalive, addr, bytes(bf_key), self._ka_gen)
                    
                    # Bundle both candidate reply IDs:
                    reply_msg1 = b"\xff" + struct.pack("<I", 8) + req_id_7 + session_key
                    reply_msg2 = b"\xff" + struct.pack("<I", 8) + req_id_5 + session_key
                    clear_reply = struct.pack("<H", 0x0040) + reply_msg1 + reply_msg2 + struct.pack("<I", 1)
                    
                    # Pad to multiple of 8 with wastage byte for EncryptionFilter
                    pad_len = 8 - (len(clear_reply) % 8)
                    padded = clear_reply + b"\x00" * (pad_len - 1) + bytes([pad_len])
                    enc_reply = loginapp.custom_bf_encrypt(bytes(bf_key), padded)
                    self.transport.sendto(enc_reply, addr)
                    print(f"  [{ts}] [BASEAPP LOGIN REPLY] Sent BF-encrypted reply ({len(enc_reply)}B) to {addr}")
                    return

                # Encrypted BaseApp traffic (channel established)
                if len(data) % 8 == 0:
                    pt = loginapp.custom_bf_decrypt(bytes(bf_key), data)
                    wastage = pt[-1]
                    if wastage <= 8:
                        pkt = bytes(pt[:-wastage])
                    else:
                        pkt = bytes(pt)
                else:
                    pkt = data
                
                flags = struct.unpack("<H", pkt[:2])[0]
                self._last_recv[addr] = _t.time()
                if not hasattr(self, "_keepalive_started"):
                    self._keepalive_started = set()
                if addr not in self._keepalive_started and os.environ.get("TIMER_KEEPALIVE", "on") == "on":
                    self._keepalive_started.add(addr)
                    asyncio.get_event_loop().call_later(0.5, self._keepalive, addr, bytes(bf_key), self._ka_gen)
                print(f"  [{ts}] [BASEAPP RECV] {len(pkt)}B flags=0x{flags:04x} pt={pkt.hex()}")
                
                # Check for remote ACKs of our sequence numbers (HAS_ACKS = 0x0004)
                if flags & 0x0004 and len(pkt) >= 3:
                    n_acks = pkt[-1]
                    if len(pkt) >= 1 + 4 * n_acks:
                        ack_start = len(pkt) - 1 - 4 * n_acks
                        unacked = self._unacked_packets.get(addr, {})
                        for a_i in range(n_acks):
                            acked_seq = struct.unpack_from("<I", pkt, ack_start + a_i * 4)[0]
                            if acked_seq in unacked:
                                del unacked[acked_seq]
                                print(f"      [BASEAPP] Remote ACKed our seq #{acked_seq}")

                # Client packet sequence (HAS_SEQUENCE = 0x0040)
                client_seq = None
                if flags & 0x0040:
                    end = len(pkt)
                    if flags & 0x0004:                   # strip [acks...][nAcks] first
                        end -= 1 + 4 * pkt[-1]
                    client_seq = struct.unpack("<I", pkt[end - 4:end])[0]
                    self._last_client_seq[addr] = max(self._last_client_seq.get(addr, 0), client_seq)
                    print(f"      [BASEAPP] Client seq #{client_seq}")

                body = b""
                # ClientInterface ids (client log named id 0 "authenticate", so regseq's map is
                # off by one here): 0 authenticate, 1 bandwidthNotification, 2 updateFrequency,
                # 3 setGameTime, 4 resetEntities(fixed 1), 5 createBasePlayer(var16),
                # 6 createCellPlayer(var16). (0x0d summariseVersionPoint is client->server only.)
                # createBasePlayer must wait for the client's enableEntities (BaseAppExt id 8):
                # ServerConnection::createBasePlayer (libclient+0x94c10c) only dispatches to its
                # handler once logOn completed; earlier copies are dropped ("did not consume").
                msgs = parse_client_bundle(pkt)
                if msgs:
                    print(f"      [BASEAPP] client msgs: {[(m, p.hex()) for m, p in msgs]}")



                # External trigger to transition to Hall/Lobby immediately:
                trig = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trigger_hall.txt")
                if os.path.exists(trig):
                    try:
                        os.remove(trig)
                    except Exception:
                        pass
                    self._transition_to_athlete(addr, bytes(bf_key))

                trig_hall = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trigger_enter_hall.txt")
                if os.path.exists(trig_hall):
                    try:
                        os.remove(trig_hall)
                    except Exception:
                        pass
                    self._hall_entered.pop(addr, None)
                    self._send_enter_hall_calls(addr, bytes(bf_key))

                # In-battle client requests (door open/close, loot pickup): answered by battle_flow.Match
                if self._in_battle.get(addr):
                    import battle_flow, importlib
                    if os.environ.get("BATTLE_RELOAD", "on") == "on":
                        _mt = os.path.getmtime(battle_flow.__file__)
                        if _mt != getattr(self, "_bf_mtime", _mt):
                            self._bf_mtime = _mt
                            _old = self.__dict__.get("_matches", {}).get(addr)
                            importlib.reload(battle_flow)
                            if _old is not None:      # keep doors/loot across a code reload
                                _new = self._battle_match(addr)
                                _new.__dict__.update(_old.__dict__)
                        self._bf_mtime = _mt
                    for m, p in msgs:
                        if 0x80 <= m <= 0xBF:
                            try:
                                reply = battle_flow.Match.handle(self._battle_match(addr), m, p, log=print)
                            except Exception as e:
                                reply = b""
                                print(f"      [BATTLE] request 0x{m:02x} failed: {e!r}")
                            if reply:
                                self._send_bundle(addr, reply, self._last_client_seq.get(addr), bytes(bf_key))
                    match = self.__dict__.get("_matches", {}).get(addr)
                    # Quit Game -> Confirm sends the base method requestLeaveDynamicSpace (raw base index 181,
                    # client index +3): msg 0xFD (var16) with sub byte 0x7B. Measured live 2026-11-20.
                    leave_sub = int(os.environ.get("BATTLE_LEAVE_SUB", "0x7B"), 0)
                    if any(m == 0xFD and p[:1] == bytes([leave_sub]) for m, p in msgs):
                        match = self._battle_match(addr)
                        match.leave = True
                    if match is not None and getattr(match, "leave", False):
                        # Quit Game: back to the lobby (Athlete), like the tutorial SKIP path
                        print("      [BATTLE] player left the match -> lobby")
                        self._matches.pop(addr, None)
                        self._in_battle[addr] = False
                        self._athlete_sent.pop(addr, None)
                        self._hall_entered.pop(addr, None)
                        self._transition_to_athlete(addr, bytes(bf_key))

                # Battle-flow experiments on a live match: one command per line (battle_flow.debug_command)
                trig_battle = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trigger_battle.txt")
                if os.path.exists(trig_battle) and self._in_battle.get(addr):
                    import battle_flow, importlib
                    try:
                        importlib.reload(battle_flow)        # edit battle_flow.py without a restart
                        lines = open(trig_battle).read().splitlines()
                        os.remove(trig_battle)
                        for line in lines:
                            data = battle_flow.debug_command(line, int(os.environ.get("BATTLE_MAP", "700")), self._battle_match(addr))
                            if data:
                                print(f"      [BATTLE] trigger {line!r} -> {data.hex()}")
                                self._send_bundle(addr, data, self._last_client_seq.get(addr), bytes(bf_key))
                    except Exception as e:
                        print(f"      [BATTLE] trigger failed: {e!r}")

                # Check if client requested skip tutorial / leave dynamic space (SKIP button in HUD)
                if any(m == 0xFD and len(p) >= 1 and p[0] in (0x7D, 0x58, 0x78, 0x71) for m, p in msgs):
                    print("      [BASEAPP] Client requested leave tutorial -> transitioning to Athlete (Lobby)...")
                    self._transition_to_athlete(addr, bytes(bf_key))

                # Check if Athlete has entered and needs hall ready calls
                if self._athlete_sent.get(addr) and addr not in self._hall_entered:
                    if any(m in (0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xD0) for m, _ in msgs):
                        self._send_enter_hall_calls(addr, bytes(bf_key))

                # Athlete client->server requests (exposed base methods), decoded by name
                # (athlete_requests.py; ids fitted on real traffic).
                if self._athlete_sent.get(addr) and not self._in_battle.get(addr):
                    self._last_bf[addr] = bytes(bf_key)
                    for m, p in msgs:
                        call = athlete_requests.decode(m, p)
                        if call:
                            body += self._athlete_request(addr, call[0], call[1])

                # Account.handshake = exposed base method 5 -> msg 0xC5 (confirmed). Answer with
                # Account client methods (parse order: iProxy 0-10, iQueue 11-12, iActivation 13,
                # iChildCare 14-16, Account: loadSceneAfterReconnect 17, onLogin 18, onChannelLogin 19).
                if (any(m == 0xC5 for m, _ in msgs) and addr not in self._handshake_done
                        and os.environ.get("SWITCH_TO", "athlete") == "athlete"):
                    # Direct route: Account -> Athlete (hall/lobby player, client type 56).
                    # Completely bypasses tutorial / battleground map 701.
                    self._handshake_done[addr] = True
                    body += b"\x04\x00"                              # resetEntities(False)
                    body += athlete_create_message()
                    print(f"      [BASEAPP] Account.handshake -> resetEntities + createBasePlayer(Athlete)")
                    if os.environ.get("ATHLETE_CELL", "off") == "on":
                        ccp = (struct.pack("<II", int(os.environ.get("CCP_SPACE", "1")), 0) +
                               struct.pack("<3f", 0.0, 0.0, 0.0) + struct.pack("<3f", 0.0, 0.0, 0.0))
                        body += b"\x06" + struct.pack("<H", len(ccp)) + ccp
                        print("      [BASEAPP] + createCellPlayer(Athlete)")
                    self._athlete_sent[addr] = True
                    delay = float(os.environ.get("HALL_DELAY", "2.0"))
                    asyncio.get_event_loop().call_later(
                        delay, self._send_enter_hall_calls, addr, bytes(bf_key))
                    print(f"      [BASEAPP] Scheduled _send_enter_hall_calls in {delay}s")
                elif (any(m == 0xC5 for m, _ in msgs) and addr not in self._handshake_done
                        and os.environ.get("SWITCH_TO", "athlete") == "avatar"):
                    # Tutorial route: Account -> battle Avatar in a space (loads map 701).
                    self._handshake_done[addr] = True
                    cbp_msg, ccp_msg = avatar_create_messages()
                    body += b"\x04\x00" + cbp_msg + ccp_msg       # resetEntities + base + cell
                    print("      [BASEAPP] Account.handshake -> resetEntities + createBasePlayer/createCellPlayer(Avatar)")
                    if os.environ.get("AUTO_TRANSITION_HALL", "on") == "on":
                        t_delay = float(os.environ.get("TRANSITION_DELAY", "2.5"))
                        asyncio.get_event_loop().call_later(
                            t_delay, self._transition_to_athlete, addr, bytes(bf_key))
                        print(f"      [BASEAPP] Scheduled auto-transition to Athlete (Lobby) in {t_delay}s")
                if any(m == 0xC5 for m, _ in msgs) and addr not in self._handshake_done:
                    self._handshake_done[addr] = True
                    eid = int(os.environ.get("CBP_ID", "10001"), 0)
                    sauth = {"uid": str(account_link.current_gid()),
                             "aid": str(account_link.current_gid()),
                             "token": "localguesttoken0001", "login_type": 7}
                    import pickle
                    i_ch = int(os.environ.get("IDX_ONCHANNELLOGIN", "19"))
                    i_lg = int(os.environ.get("IDX_ONLOGIN", "18"))
                    calls = client_method(i_ch, eid, b"\x00" + _bw_blob(pickle.dumps(sauth, protocol=2)))
                    if os.environ.get("SEND_ONLOGIN", "on") == "on":
                        calls += client_method(i_lg, eid, struct.pack("<i", 0) + _bw_blob(b""))
                    # The client defers createCellPlayer (~1s, prerequisites); calls that arrive
                    # before the player has entered stay buffered forever, so send them later.
                    delay = float(os.environ.get("METHOD_DELAY", "3.0"))
                    asyncio.get_event_loop().call_later(delay, self._send_bundle, addr, calls, None, bytes(bf_key))
                    print(f"      [BASEAPP] handshake -> onChannelLogin(idx {i_ch}, OK) + onLogin(idx {i_lg}, OK) in {delay}s")
                if addr not in self._player_created and any(m == 0x08 for m, _ in msgs):   # only after enableEntities (earlier copies are dropped)
                    cbp_type = int(os.environ.get("CBP_TYPE", "41"), 0)
                    cbp_id = int(os.environ.get("CBP_ID", "10001"), 0)
                    cbp_payload = (struct.pack("<I", cbp_id) + struct.pack("<H", cbp_type) +
                                   build_base_player_props(os.environ.get("CBP_PROPS", "account")))
                    msg_create = b"\x05" + struct.pack("<H", len(cbp_payload)) + cbp_payload
                    body += msg_create
                    # Entity-method calls are only dispatched to entities in ClientApp's "entered"
                    # map (onEntityMethod @+0x91e960 buffers the rest in +0x1088). createCellPlayer
                    # -> onCellPlayerCreate + onEntityEnter(+0x91d214) moves the player in and
                    # replays buffered calls. Payload: spaceID, vehicleID, pos xyz, yaw/pitch/roll.
                    if os.environ.get("SEND_CELL_PLAYER", "off") == "on":
                        ccp = (struct.pack("<II", int(os.environ.get("CCP_SPACE", "1")), 0) +
                               struct.pack("<3f", 0.0, 0.0, 0.0) + struct.pack("<3f", 0.0, 0.0, 0.0))
                        body += b"\x06" + struct.pack("<H", len(ccp)) + ccp
                        print(f"      [BASEAPP] + createCellPlayer(space={os.environ.get('CCP_SPACE', '1')})")
                    self._player_created[addr] = True
                    print(f"      [BASEAPP] enableEntities seen -> createBasePlayer(id={cbp_id}, type={cbp_type}, {len(cbp_payload)}B)")
                
                # Keepalive: the client drops the channel after 10s without inbound traffic
                # (REASON_INACTIVITY), and rejects bare 2-byte packets as "undersize". So when
                # there is nothing else to send, re-ACK the latest reliable client seq
                # (client logs re-acks as "already acked packet (ok)").
                if client_seq is not None:
                    self._last_client_seq[addr] = client_seq
                elif not body:
                    client_seq = self._last_client_seq.get(addr)
                    if client_seq is None:
                        return

                self._send_bundle(addr, body, client_seq, bytes(bf_key))
            except Exception as e:
                import traceback
                print(f"  [{ts}] [BASEAPP ERROR] {e}\n{traceback.format_exc()}")

    def _keepalive(self, addr, bf_key, gen):
        """Timer keepalive: retransmits unacked reliable packets every 0.3s-0.5s until ACKed,
        and sends keepalive ACKs to prevent channel timeout."""
        import time as _t, loginapp
        if gen != self._ka_gen:
            return
        now = _t.time()
        _flag1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "harness", "push_now.flag")
        _flag2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness", "push_now.flag")
        _flag = _flag1 if os.path.exists(_flag1) else (_flag2 if os.path.exists(_flag2) else None)
        if _flag:
            try:
                os.remove(_flag)
                self._push_appearance(addr, bytes(bf_key))
            except Exception as e:
                print(f"      [BASEAPP] push_now failed: {e}")
        c_seq = self._last_client_seq.get(addr)

        # Retransmit unacked reliable packets:
        unacked = self._unacked_packets.get(addr, {})
        for s, info in list(unacked.items()):
            if now - info['time'] >= 0.5:
                fl = info['fl']
                body = info['body']
                footer = info['footer_prefix']
                if c_seq is not None:
                    fl |= 0x0004
                    footer = footer + struct.pack("<I", c_seq) + b"\x01"
                else:
                    fl &= ~0x0004
                cleartext = struct.pack("<H", fl) + body + footer
                pad_len = 8 - (len(cleartext) % 8)
                padded = cleartext + b"\x00" * (pad_len - 1) + bytes([pad_len])
                enc = loginapp.custom_bf_encrypt(bf_key, padded)
                self.transport.sendto(enc, addr)
                info['time'] = now
                print(f"  [{_t.strftime('%H:%M:%S')}] [BASEAPP RESEND] seq={s} ack={c_seq} ({len(enc)}B) to {addr}")

        # In the hall the client drops the connection (and re-logs in) when it receives no real
        # game message for ~30 s (GameInit CLIENT_INACTIVE_HALL_TIME); bare acks do not count.
        hb = float(os.environ.get("HALL_HEARTBEAT", "8"))
        if (hb > 0 and self._hall_entered.get(addr) and not unacked and c_seq is not None
                and now - getattr(self, "_last_hb", {}).get(addr, 0) > hb):
            if not hasattr(self, "_last_hb"):
                self._last_hb = {}
            self._last_hb[addr] = now
            try:
                self._send_bundle(addr, athlete_method(
                    "onSyncSwitches", _bw_blob(b"URGENT_SWITCH_ENABLE_FORCE_UPGRADE") + b"\x00", quiet=True),
                    c_seq, bf_key)
            except Exception as e:
                print(f"      [BASEAPP] heartbeat failed: {e}")

        # If no unacked packets, send regular keepalive ACK:
        if not unacked and c_seq is not None and now - self._last_sent_ka.get(addr, 0) > 1.0:
            self._last_sent_ka[addr] = now
            self._send_bundle(addr, b"", c_seq, bf_key)

        asyncio.get_event_loop().call_later(0.3, self._keepalive, addr, bf_key, gen)

    def _send_enter_hall_calls(self, addr, bf_key):
        if self._hall_entered.get(addr):
            return
        self._hall_entered[addr] = True
        import pickle
        if is_new_account():
            print(f"      [BASEAPP] -> New account detected! Sending Athlete.showSelectCharacter...")
            calls = (athlete_method("onLogin", struct.pack("<i", 0) + _bw_blob(b"")) +
                     athlete_method("showSelectCharacter", struct.pack("<I", 0)))
            cur_seq = self._last_client_seq.get(addr)
            self._send_bundle(addr, calls, cur_seq, bytes(bf_key))
            print(f"      [BASEAPP] Sent Athlete.onLogin + showSelectCharacter")
        else:
            name = get_account_name()
            print(f"      [BASEAPP] -> Existing account ({name})! Sending onLogin + enterHall(1)...")
            # No-reset transition: the tutorial Avatar is still in the world (it kept
            # Globals.player set so the Athlete could pass prerequisites). Remove it with
            # leaveAoI (ClientInterface 15, var16) while map 701 is still loaded, before
            # enterHall tears the level down (its leaveWorld fails during level destroy).
            pre = b""
            if (os.environ.get("TRANSITION_RESET", "on") != "on"
                    and os.environ.get("LEAVE_OLD_AVATAR", "on") == "on"):
                av = struct.pack("<I", int(os.environ.get("AVATAR_ID", "10003")))
                n_leave = int(os.environ.get("LEAVE_COUNT", "2"))      # client logs enterCount 2
                pre = (b"\x0f" + struct.pack("<H", len(av)) + av) * n_leave
                if os.environ.get("LEAVE_MODE", "aoi") == "reset":
                    pre = b"\x04\x01"        # resetEntities(keepPlayerOnBase=True)
                print(f"      [BASEAPP] -> leaveAoI(old Avatar {os.environ.get('AVATAR_ID', '10003')}) x{n_leave}")
                gap = float(os.environ.get("LEAVE_GAP", "1.5"))
                if gap > 0 and not getattr(self, "_leave_sent", {}).get(addr):
                    # Own packet first; re-enter this method after the gap for the hall calls.
                    self._leave_sent = getattr(self, "_leave_sent", {})
                    self._leave_sent[addr] = True
                    self._hall_entered[addr] = False
                    self._send_bundle(addr, pre, self._last_client_seq.get(addr), bytes(bf_key))
                    asyncio.get_event_loop().call_later(gap, self._send_enter_hall_calls, addr, bytes(bf_key))
                    return
                if gap > 0:
                    pre = b""
            calls = pre + (
                athlete_method("onLogin", struct.pack("<i", 0) + _bw_blob(b"")) +
                athlete_method("onRoleCreateSuc", struct.pack("<i", 1)) +
                athlete_method("onSyncSwitches", _bw_blob(b"URGENT_SWITCH_ENABLE_FORCE_UPGRADE") + b"\x00") +
                athlete_method("onSetSwitches", _bw_blob(b"URGENT_SWITCH_ENABLE_FORCE_UPGRADE") + b"\x00") +
                self._lobby_data_calls()
            )
            cur_seq = self._last_client_seq.get(addr)
            self._send_bundle(addr, calls, cur_seq, bytes(bf_key))
            print(f"      [BASEAPP] Sent Athlete.onLogin + onRoleCreateSuc + switches + lobby data")
            
            # Send enterHall cleanly in its own bundle to avoid fragmentation corruption
            hall_call = athlete_method("enterHall", _first_login_today())
            asyncio.get_event_loop().call_later(
                0.2, self._send_bundle, addr, hall_call, self._last_client_seq.get(addr), bytes(bf_key)
            )
            print(f"      [BASEAPP] Scheduled enterHall in 0.2s")
            # Hall hero model needs a dress refresh after UIMain exists (loader stays None otherwise).
            if os.environ.get("UNLOCK_ALL", "calls") == "calls":
                asyncio.get_event_loop().call_later(float(os.environ.get("UNLOCK_DELAY", "20")),
                                                    self._unlock_all_batch, addr, bytes(bf_key), 0)
            for t in [float(x) for x in os.environ.get("APPEARANCE_PUSH", "").split(",") if x.strip()]:
                asyncio.get_event_loop().call_later(t, self._push_appearance, addr, bytes(bf_key))

    def _athlete_request(self, addr, name, args):
        """Reply to one decoded Athlete base call. Unknown names are only logged."""
        import time as _t
        rd = athlete_requests.Reader(args)
        py = athlete_requests.py
        if name not in athlete_requests.QUIET:
            print(f"      [BASEAPP] <- Athlete.{name} args={args.hex()[:80]}")
        try:
            if name == "createCharacter":
                career_type = rd.i32()
                char_name = rd.string()
                print(f"      [BASEAPP] Athlete.createCharacter: name='{char_name}', type={career_type}")
                save_account("default", {"name": char_name, "char_type": career_type})
                if account_link.current() and not account_link.set_character(char_name, career_type):
                    print(f"      [ACC-LINK] character '{char_name}' not saved to RoS_Server")
                return (athlete_method("onCreateCharacter", b"\x01" + _bw_blob(b"")) +
                        athlete_method("onRoleCreateSuc", struct.pack("<i", 1)) +
                        athlete_method("updateBaseNickname", _bw_blob(char_name.encode())) +
                        athlete_method("updateBaseCharacter", struct.pack("<i", career_type)) +
                        athlete_method("onSyncSwitches", _bw_blob(b"URGENT_SWITCH_ENABLE_FORCE_UPGRADE") + b"\x00") +
                        athlete_method("onSetSwitches", _bw_blob(b"URGENT_SWITCH_ENABLE_FORCE_UPGRADE") + b"\x00") +
                        self._lobby_data_calls() +
                        athlete_method("enterHall", _first_login_today()))
            if name == "requestRoomListInfo":
                return athlete_method("onRequestRoomListInfo", struct.pack("<I", 0) + struct.pack("<i", 0))
            if name == "requestRoomCountInfo":
                return athlete_method("onRequestRoomCountInfo", struct.pack("<iii", 0, 0, 0))
            if name == "createDtsCustomGame":
                creator_name = get_account_name()
                room_info = build_custom_room_info(f"{creator_name}'s Room", creator_name, account_link.current_gid())
                print(f"      [BASEAPP] createDtsCustomGame -> onCreateDtsCustomGame for host '{creator_name}'")
                return athlete_method("onCreateDtsCustomGame", room_info)

            # Supply boxes (draws). Free: no currency check or deduction on this private server.
            supply = self._supply.setdefault(addr, athlete_requests.SupplyState())
            if name == "queryAvailableSupplement":
                return (athlete_method("onQueryAvailableSupplement", py(athlete_requests.supplement_info())) +
                        athlete_method("onUpdateFreeLotteryTimeStampDict", py(supply.free_ts) + py(supply.free_times)))
            if name == "openSupplyBoxFree":
                sid = rd.i32()
                prizes = athlete_requests.draw(sid, 1)
                supply.note_free(sid)
                self._settle(addr, 0, prizes, f"free:{sid}")
                print(f"      [BASEAPP] free draw box {sid} -> {prizes}")
                return (athlete_method("onUpdateFreeLotteryTimeStampDict", py(supply.free_ts) + py(supply.free_times)) +
                        self._grant_props(prizes) +
                        athlete_method("onOpenFreeSupplyBox", struct.pack("<i", sid) + py(prizes)))
            if name in ("openSupplyBox", "openMultipleSupplyBox"):
                multi = name == "openMultipleSupplyBox"
                sid, currency = rd.i32(), rd.i32()           # 2nd arg: chosen currency id
                rd.i32_array()                                # cash coupons (ignored)
                watch_ad = rd.i8() if not multi and rd.i < len(rd.b) else 0
                price = athlete_requests.draw_price(sid, currency, multi)
                diamonds = price if currency == athlete_requests.YUANBAO else 0
                prizes = athlete_requests.draw(sid, athlete_requests.multi_count(sid) if multi else 1)
                if not self._settle(addr, diamonds, prizes, f"draw:{sid}"):
                    return athlete_method(
                        "onMultiOpenSupplyBoxFailed" if multi else "onOpenSupplyBoxFailed",
                        struct.pack("<i", sid) + _bw_blob(b"") + struct.pack("<ii", currency, price) + struct.pack("<I", 0))
                print(f"      [BASEAPP] {'multi ' if multi else ''}draw box {sid} currency={currency} price={price} -> {prizes}")
                calls = (self._diamond_props(addr) if diamonds else b"") + self._grant_props(prizes)
                if multi:
                    return calls + athlete_method("onMultiOpenSupplyBox", struct.pack("<i", sid) + py(prizes))
                return calls + athlete_method("onOpenSupplyBox", struct.pack("<i", sid) + py(prizes) + bytes([1 if watch_ad else 0]))

            # Store (UIMall & co.): the client only enables BUY for goods listed in its
            # availableMallGoodsDict, which these replies fill (extract/mall_goods.json).
            if name == "queryAvailableMallGoodsByType":
                types = rd.u32()
                goods = athlete_requests.mall_goods(types)
                print(f"      [BASEAPP] mall goods type={types} -> {len(goods)} goods")
                return athlete_method("onQueryAvailableMallGoodsByType", struct.pack("<I", types) + self._mall_py(goods))
            if name == "queryAvailableMallGoods":
                return athlete_method("onQueryAvailableMallGoods", self._mall_py(athlete_requests.mall_goods(0)))
            if name == "queryAvailableMallGoodsForAppearanceMall":
                return athlete_method("onQueryAvailableMallGoodsForAppearanceMall",
                                      py(athlete_requests.appearance_mall_goods()))
            if name in ("buyMallGood", "buyMallGoodInAppearanceMall"):
                good, num = rd.i32(), rd.i32()
                price = athlete_requests.mall_good_price(good, num)
                prop = athlete_requests.mall_good_prop(good)
                if price is None or prop is None:
                    print(f"      [BASEAPP] {name} {good}: not a buyable mall good")
                    return athlete_method("onBuyMallGoodFailed", _bw_blob(b"") + struct.pack("<iiii", good, num, 0, 0)
                                          + struct.pack("<I", 0) + _bw_blob(b""))
                cur, amount = price
                diamonds = amount if cur == athlete_requests.YUANBAO else 0
                props = [prop] * max(num, 1)
                if not self._settle(addr, diamonds, props, f"mall:{good}x{num}"):
                    print(f"      [BASEAPP] {name} {good}: not enough currency {cur} ({amount})")
                    return athlete_method("onBuyMallGoodFailed", _bw_blob(b"") + struct.pack("<iiii", good, num, cur, amount)
                                          + struct.pack("<I", 0) + _bw_blob(b""))
                print(f"      [BASEAPP] {name} {good} x{num} -> prop {prop}, paid {amount} (currency {cur})")
                return ((self._diamond_props(addr) if diamonds else b"") + self._grant_props(props, force=True) +
                        athlete_method("onBuyMallGood", struct.pack("<I", len(props)) +
                                       b"".join(struct.pack("<i", p) for p in props)))

            # Store multi-buy (e.g. Lobby Theme "Selected n/4" -> BUY): goods[], nums[], coupons[],
            # logStr. One charge for the total; reply like buyMallGood with every granted prop.
            if name == "buyMultipleMallGood":
                goods, nums, _coupons = rd.i32_array(), rd.i32_array(), rd.i32_array()
                nums += [1] * (len(goods) - len(nums))
                total, props, bad = 0, [], []
                for good, num in zip(goods, nums):
                    price, prop = athlete_requests.mall_good_price(good, num), athlete_requests.mall_good_prop(good)
                    if price is None or prop is None or price[0] != athlete_requests.YUANBAO:
                        bad.append(good)
                        continue
                    total += price[1]
                    props += [prop] * max(num, 1)
                if bad or not props or not self._settle(addr, total, props, f"mall-multi:{goods}"):
                    print(f"      [BASEAPP] buyMultipleMallGood {goods}: failed (unbuyable {bad}, total {total})")
                    g0 = goods[0] if goods else 0
                    return athlete_method("onBuyMallGoodFailed", _bw_blob(b"") + struct.pack("<iiii", g0, 1, athlete_requests.YUANBAO, total)
                                          + struct.pack("<I", 0) + _bw_blob(b""))
                print(f"      [BASEAPP] buyMultipleMallGood {goods} -> props {props}, paid {total}")
                return (self._diamond_props(addr) + self._grant_props(props, force=True) +
                        athlete_method("onBuyMallGood", struct.pack("<I", len(props)) +
                                       b"".join(struct.pack("<i", p) for p in props)))

            # Wardrobe hall-prop buys, paid in the client's own listed currency and price
            # (extract/hallprop_prices.json); the won item is added for the session.
            if name == "buyDtsHallProp":
                good = rd.i32()
                price = athlete_requests.hallprop_price(good) if name == "buyDtsHallProp" else None
                cur, amount = price or (athlete_requests.YUANBAO, 0)
                diamonds = amount if cur == athlete_requests.YUANBAO else 0
                if not self._settle(addr, diamonds, [good], f"buy:{good}"):
                    print(f"      [BASEAPP] {name} {good}: not enough currency {cur} ({amount})")
                    return athlete_method("onBuyMallGoodFailed", _bw_blob(b"") + struct.pack("<iiii", good, 1, cur, amount)
                                          + struct.pack("<I", 0) + _bw_blob(b""))
                print(f"      [BASEAPP] {name} {good} price={price}")
                return (self._diamond_props(addr) if diamonds else b"") + self._grant_props([good], force=True) + athlete_method("onBuyMallGood", struct.pack("<Ii", 1, good))

            # Daily sign-in popup (UIDtsSign) "Claim": the popup stays as a dim mask until this
            # answer arrives. Award per day = client legacyProperties.iterDtsSigninData awardID.
            if name == "requestDtsSigninAward":
                import time as _tm
                day = _tm.strftime("%Y-%m-%d", _tm.gmtime(athlete_requests.game_now()))
                st = load_accounts().get("signin") or {"level": 0, "day": ""}
                level = st["level"] if st.get("day") == day else min(st["level"] + 1, len(SIGNIN_AWARDS))
                save_account("signin", {"level": level, "day": day})
                award = SIGNIN_AWARDS[max(level, 1) - 1]
                print(f"      [BASEAPP] sign-in claim -> level {level}, award {award}")
                return athlete_method("onRequestDtsSignInAward",
                                      struct.pack("<Ii", 1, award) + struct.pack("<i", level))

            if name == "setHasAlreadyShowSupplyID":
                sid = rd.i32()
                save_account("supply_push", {"id": sid})
                print(f"      [BASEAPP] weekly supply push shown: box {sid}")
                return athlete_method("onUpdateAlreadyShowSupplyID", struct.pack("<i", sid))

            if name == "getOpenMaintenanceFightTipFlag":     # START button asks this first
                return athlete_method("onGetOpenMaintenanceFightTipFlag", b"\x00" + struct.pack("<i", 0))

            # START, then: createHallTeam(mode) -> a one-player team; getReadyForBattleGround ->
            # ready + matching timer (client iHallTeam.py; BattleMatchState NONE 0 / MATCHING 1 /
            # ENTERING 2 / PRE_ENTERING 3). Entering the battle itself is not implemented yet.
            if name == "createHallTeam":
                mode = rd.i32()
                self._team[addr] = mode
                gid = account_link.current_gid()
                members = struct.pack("<I", 1) + self._hall_team_member(addr)
                print(f"      [BASEAPP] createHallTeam mode={mode} -> onEnterHallTeam (solo, leader {gid})")
                return athlete_method("onEnterHallTeam", struct.pack("<iQb", mode, gid, 1) + members +
                                      struct.pack("<i", HALL_TEAM_MAP_GROUP) + b"\x00\x00")
            if name == "getReadyForBattleGround":
                gid = account_link.current_gid()
                print(f"      [BASEAPP] getReadyForBattleGround -> ready + MATCHING")
                return (athlete_method("syncReadyState", struct.pack("<QBB", gid, 1, 0)) +
                        athlete_method("syncMatchState", struct.pack("<hqB", 1, int(athlete_requests.game_now()), 0) + py(None)) +
                        athlete_method("syncMatchingProgress", struct.pack("<iif", 1, 100, 0.0)))
            # matchBattleGround(1): "match found" at once -> ENTERING, then hand the client to a
            # battle Avatar (like BaseEntity.giveClientTo): resetEntities + createBasePlayer +
            # createCellPlayer; PlayerAvatar.onBecomePlayer loads currentMapID itself.
            if name == "matchBattleGround":
                print(f"      [BASEAPP] matchBattleGround -> ENTERING")
                if os.environ.get("BATTLE_ENTER", "on") == "on":
                    asyncio.get_event_loop().call_later(float(os.environ.get("BATTLE_DELAY", "3")),
                                                        self._enter_battle, addr)
                return athlete_method("syncMatchState", struct.pack("<hqB", 2, int(athlete_requests.game_now()), 0) + py(None))
            if name in ("notReadyForBattleGround", "cancelMatchBattleGround"):   # timer X sends cancel
                gid = account_link.current_gid()
                print(f"      [BASEAPP] {name} -> not ready + NONE")
                return (athlete_method("syncReadyState", struct.pack("<QBB", gid, 0, 0)) +
                        athlete_method("syncMatchState", struct.pack("<hqB", 0, 0, 0) + py(None)))

            # Equip (clothes, face/hair/decorations, weapon & vehicle skins, lobby theme, emojis), as the
            # client's DtsAppearance.<type>.equipAppearanceRequestServer does it.
            if name == "equipAppearance":
                pid = rd.i32()
                slot = athlete_requests.appearance_slot(pid)
                if slot and slot[2] not in (0, current_gender()):
                    return athlete_method("onNotifyEquipAppearanceFailed", _bw_blob(b"I_DTS_APPEARANCE_GENDER_INVALID"))
                outfit = self._session_outfit(addr)
                kind = outfit.equip(pid)
                if not kind:
                    app_type = athlete_requests.appearance_type(pid)
                    print(f"      [BASEAPP] equipAppearance {pid}: type not tracked ({app_type})")
                    if app_type == "EmojiType":
                        return (athlete_method("onUpdateDtsEmojiID", struct.pack("<i", pid)) +
                                athlete_method("onNotifyEquipedAppearance", struct.pack("<i", pid)))
                    return athlete_method("onNotifyEquipedAppearance", struct.pack("<i", pid))
                self._save_outfit(outfit)
                print(f"      [BASEAPP] equipAppearance {pid} ({kind}) -> {outfit.to_dict()}")
                return self._outfit_calls(outfit, kind) + athlete_method("onNotifyEquipedAppearance", struct.pack("<i", pid))

            if name == "unloadAppearance":
                pid = rd.i32()
                app_type = athlete_requests.appearance_type(pid)
                print(f"      [BASEAPP] unloadAppearance {pid} ({app_type})")
                calls = athlete_method("onNotifyUnloadAppearance", struct.pack("<i", pid))
                if app_type == "EmojiType":
                    calls += athlete_method("onUpdateDtsEmojiID", struct.pack("<i", 0))
                return calls

            # Clothes suits (Depot > SET): put on = show every piece; the pieces you own are worn.
            if name in ("putOnAppearanceClothSuit", "takeOffAppearanceClothSuit"):
                sid = rd.i32()
                suit = athlete_requests.appearance_suit(sid)
                if not suit:
                    print(f"      [BASEAPP] {name} {sid}: unknown suit")
                    return b""
                if suit["gender"] not in (0, current_gender()):
                    return athlete_method("onNotifyEquipAppearanceFailed", _bw_blob(b"I_DTS_APPEARANCE_GENDER_INVALID"))
                outfit = self._session_outfit(addr)
                owned = self._owned(addr)
                kinds = set()
                for pid in suit["items"]:
                    if name == "takeOffAppearanceClothSuit":
                        worn = pid in getattr(outfit, outfit.kind(pid) or "body", [])
                        kinds.add(outfit.equip(pid) if worn else outfit.try_off(pid))
                    elif pid in owned:
                        if pid not in getattr(outfit, outfit.kind(pid) or "body", []):
                            kinds.add(outfit.equip(pid))
                    else:
                        kinds.add(outfit.try_on(pid))
                kinds.discard(None)
                if name == "putOnAppearanceClothSuit":
                    # equip() resets the shown list; re-show the pieces only tried on
                    for pid in suit["items"]:
                        if pid not in owned:
                            outfit.try_on(pid)
                self._save_outfit(outfit)
                print(f"      [BASEAPP] {name} {sid} '{suit['name']}' {suit['items']} -> {outfit.to_dict()}")
                return b"".join(self._outfit_calls(outfit, k) for k in kinds)

            # Hall gender switch (♂/♀ under the model; also restored when leaving the action
            # preview). iDtsEquipAppearanceAthlete.onSetDtsAppearanceGender sets
            # dtsAppearanceGender and resets the hall model, so the gender's body parts go first.
            if name == "setDtsAppearanceGender":
                gender = rd.i32()
                if gender not in (1, 2):
                    print(f"      [BASEAPP] setDtsAppearanceGender: bad gender {gender}")
                    return b""
                old, body_by = get_account_gender()
                outfit = self._session_outfit(addr)
                body_by[str(old)] = list(outfit.body)
                outfit.body = [int(i) for i in body_by.get(str(gender), [])]
                set_account_gender(gender, body_by)
                outfit.show_body = None
                self._save_outfit(outfit)
                # The hall model is built from baseCharacterType (UIMain.resetMainModel ->
                # player.getCharacterType()), and each type has a fixed GENDER in the client's
                # character table, so the gender flag alone only flips the UI.
                char = get_account_char()
                if CHAR_GENDER.get(char) != gender or char not in GENDER_CHAR.values():
                    char = GENDER_CHAR[gender]
                    set_account_char(char)
                arr = lambda ids: struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", i) for i in ids)
                print(f"      [BASEAPP] setDtsAppearanceGender {old} -> {gender}, char={char}, body={outfit.body}")
                return (athlete_method("onUpdateDtsShowBodyAppearanceList", arr(outfit.body)) +
                        athlete_method("updateBaseCharacter", struct.pack("<i", char)) +
                        athlete_method("onSetDtsAppearanceGender", struct.pack("<i", gender)))

            # Wardrobe preview (DtsAppearance.tryOnAppearanceRequestServer): swap the item into the
            # shown list only; leaving the wardrobe sends cancelTryOnAllRequest.
            if name == "tryOnAppearance":
                pid = rd.i32()
                slot = athlete_requests.appearance_slot(pid)
                if slot and slot[2] not in (0, current_gender()):
                    print(f"      [BASEAPP] tryOnAppearance {pid}: other gender ({slot[2]})")
                    return b""
                outfit = self._session_outfit(addr)
                kind = outfit.try_on(pid)
                if not kind or kind == "theme":
                    print(f"      [BASEAPP] tryOnAppearance {pid}: no shown list ({athlete_requests.appearance_type(pid)})")
                    return b""
                shown = outfit.shown(kind)
                print(f"      [BASEAPP] tryOnAppearance {pid} ({kind}) -> shown {shown}")
                return self._show_list_calls(kind, shown)
            if name == "tryOffAppearance":
                pid = rd.i32()
                outfit = self._session_outfit(addr)
                kind = outfit.try_off(pid)
                if not kind or kind == "theme":
                    return b""
                print(f"      [BASEAPP] tryOffAppearance {pid} ({kind}) -> shown {outfit.shown(kind)}")
                return self._show_list_calls(kind, outfit.shown(kind))
            if name == "cancelTryOnAllRequest":
                outfit = self._session_outfit(addr)
                outfit.cancel_try_on()
                return b"".join(self._show_list_calls(k, outfit.shown(k)) for k in outfit.LISTS)

            # My Page / Stats / Credit screens (server/profile_screens.py), from RoS_Server's profile.
            if name in PROFILE_REQUESTS:
                return self._profile_reply(addr, name, rd)

            # Avatar upload: token for the FilePicker upload, then the chosen file id.
            if name == "requestFilePickerToken":
                return athlete_method("onRequestFilePickerToken", _bw_blob(b"ros-local-filepicker") + struct.pack("<i", 0))
            if name == "setPortrait":
                fid = rd.string()
                set_account_portrait(fid)
                print(f"      [BASEAPP] setPortrait -> '{fid}'")
                return athlete_method("onSetPortrait", _bw_blob(fid.encode()))
        except Exception as e:
            print(f"      [BASEAPP] Error handling Athlete.{name}: {e!r}")
        return b""

    @staticmethod
    def _show_list_calls(kind, ids):
        arr = struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", int(i)) for i in ids)
        return athlete_method(LIST_METHODS[kind][1], arr)

    @staticmethod
    def _outfit_calls(outfit, kind):
        """Equipped + shown list updates for one outfit list (or the lobby theme id)."""
        if kind == "theme":
            return athlete_method("onUpdateDtsHallThemeID", struct.pack("<i", outfit.theme))
        ids = getattr(outfit, kind)
        arr = struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", int(i)) for i in ids)
        return athlete_method(LIST_METHODS[kind][0], arr) + GateUDP._show_list_calls(kind, outfit.shown(kind))

    @staticmethod
    def _save_outfit(outfit):
        save_local_state(outfit=outfit.to_dict())
        if account_link.current() and not account_link.set_outfit(outfit.body, outfit.wear):
            print("      [ACC-LINK] outfit not saved to RoS_Server")

    def _owned(self, addr):
        """Appearance items this account owns (saved state at login + bought/won since)."""
        if addr not in self._owned_items:
            self._owned_items[addr] = {int(i["prop_id"]) for i in (LOGIN_STATE or {}).get("items", [])}
        return self._owned_items[addr]

    @staticmethod
    def _mall_py(goods):
        """Pickled goods dict; entity messages are var16 (< 64 KB), so the full catalogue
        (1160 goods) drops NAME, which the client also has in its own mall table."""
        blob = athlete_requests.py(goods)
        if len(blob) > 60000:
            blob = athlete_requests.py({k: {f: v for f, v in g.items() if f != "NAME"} for k, g in goods.items()})
        return blob

    def _profile_reply(self, addr, name, rd):
        """Answer one My Page / Stats / Credit request. Other players' gids get this player's
        own data only when they ask about themselves; anyone else gets an empty profile."""
        py = athlete_requests.py
        own_gid = account_link.current_gid()
        profile = account_link.get_profile()
        u64 = lambda v: struct.pack("<Q", v)
        if name == "requireRecordData":
            gid, record_type = rd.u64(), rd.i16()
            data = profile_screens.record_data(profile if gid == own_gid else None, record_type)
            print(f"      [BASEAPP] requireRecordData gid={gid} type={record_type} -> {list(data)}")
            return athlete_method("onGetRecordData", u64(gid) + py(data))
        if name == "requireBaseInfo":
            gid = rd.u64()
            nick, score, level = profile_screens.base_info(profile if gid == own_gid else None, get_account_name())
            return athlete_method("onGetBaseInfo", u64(gid) + _bw_blob(nick.encode()) + b"\x00" + u64(score)
                                  + struct.pack("<iii", 0, 0, level) + _bw_blob(b""))
        if name == "queryPersonalInfo":
            gid = rd.u64()
            linked = account_link.current() or {}
            info = profile_screens.personal_info(profile if gid == own_gid else None, gid, get_account_name(),
                                                 get_account_char(), linked.get("portrait", ""))
            return athlete_method("queryPersonalInfoCB", u64(gid) + py(info))
        if name == "queryPersonalSpaceLikeCnt":
            return athlete_method("queryPersonalSpaceLikeCntCB", u64(own_gid) +
                                  struct.pack("<i", profile_screens.space_likes(profile)))
        score, status, weeks, gifts, rows = profile_screens.credit(profile)
        sync = athlete_method("syncCreditStatus", struct.pack("<ii", status, weeks) + py(gifts))
        if name == "queryCreditStatus":
            return athlete_method("queryCreditStatusCB", struct.pack("<i", status))
        if name == "queryCreditScore":
            return athlete_method("queryCreditScoreCB", struct.pack("<i", score) + py(rows)) + sync
        if name == "requireCreditReward":
            claimed = account_link.claim_credit_reward() or {"awards": []}
            awards = [int(p) for p in claimed["awards"]]
            print(f"      [BASEAPP] requireCreditReward -> {awards}")
            after = {"credit": claimed.get("credit") or (profile or {}).get("credit")}
            _score, status, weeks, gifts, _rows = profile_screens.credit(after)
            return (self._grant_props(awards) + athlete_method("requireCreditRewardCB", py(awards)) +
                    athlete_method("syncCreditStatus", struct.pack("<ii", status, weeks) + py(gifts)))
        return b""

    def _diamond_props(self, addr):
        """iCurrency.onYBUpdated(freeYuanbao, payYuanbao, src) with the session's diamond balance
        (the lobby shows their sum; all of it is reported as free diamonds)."""
        total = self._session_wallet(addr).balances.get(athlete_requests.YUANBAO, 0)
        return athlete_method("onYBUpdated", struct.pack("<qqi", total, 0, 0))

    def _session_wallet(self, addr):
        """Diamonds: RoS_Server balance loaded at login, else the ATHLETE_*_YUANBAO defaults."""
        if addr not in self._wallet:
            self._wallet[addr] = athlete_requests.Wallet({athlete_requests.YUANBAO: login_yuanbao()})
        return self._wallet[addr]

    def _session_outfit(self, addr):
        if addr not in self._outfit:
            self._outfit[addr] = athlete_requests.Outfit.from_dict((LOGIN_STATE or {}).get("outfit"))
        return self._outfit[addr]

    def _settle(self, addr, diamonds, props, reason):
        """Charge `diamonds` and record `props` as owned. RoS_Server is the source of truth when
        linked (one transaction; refuses when the balance is too low); otherwise session only."""
        wallet = self._session_wallet(addr)
        if account_link.current():
            result = account_link.purchase(diamonds, props, reason)
            if result and "_error" in result:
                return False
            if result:
                wallet.balances[athlete_requests.YUANBAO] = int(result["yuanbao"])
                self._owned(addr).update(int(p) for p in props)
                return True
            print(f"      [ACC-LINK] {reason}: RoS_Server unreachable, not saved")
        if diamonds and not wallet.pay(athlete_requests.YUANBAO, diamonds):
            return False
        # Not linked: keep the purchase on this server (saved_accounts.json "inventory:<gid>").
        self._owned(addr).update(int(p) for p in props)
        save_local_state(yuanbao=wallet.balances.get(athlete_requests.YUANBAO, 0), add_items=props)
        return True

    def _battle_match(self, addr):
        import battle_flow
        m = self.__dict__.setdefault("_matches", {})
        if addr not in m:
            m[addr] = battle_flow.Match()
        return m[addr]

    def _enter_battle(self, addr):
        if self._in_battle.get(addr) or addr not in self._last_bf:
            return
        self._in_battle[addr] = True
        self.__dict__.setdefault("_matches", {}).pop(addr, None)     # fresh doors/loot for each match
        map_id = int(os.environ.get("BATTLE_MAP", "700"))
        char = int(os.environ.get("BATTLE_CHAR", "0")) or get_account_char()
        # BattleGroundAvatar (Avatar + iDtsEquip/iDtsProp/iDtsPackage/iDtsEquipAppearanceAvatar):
        # plain Avatar lacks dtsBattlegroundPropAppearanceList (PlayerCommonAppear.onInit).
        ent = os.environ.get("BATTLE_ENTITY", "BattleGroundAvatar")
        cbp_msg, ccp_msg = avatar_create_messages(map_id, char, get_account_name(), ent)
        print(f"      [BASEAPP] -> battle: resetEntities + {ent} (map {map_id}, char {char})")
        self._send_bundle(addr, b"\x04\x00" + cbp_msg + ccp_msg, self._last_client_seq.get(addr), self._last_bf[addr])

    def _hall_team_member(self, addr):
        """HALL_TEAM_MEMBER_CLIENT for our own player: .def defaults plus identity and outfit."""
        D = bwdefs.Defs()
        outfit = self._session_outfit(addr)
        arr = lambda ids: struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", i) for i in ids)
        ov = {"entID": struct.pack("<i", int(os.environ.get("ATHLETE_ID", "10002"))),
              "gid": struct.pack("<Q", account_link.current_gid()),
              "nickname": bwdefs.blob(get_account_name().encode()),
              "level": struct.pack("<i", 1),
              "characterType": struct.pack("<i", get_account_char()),
              "inWorld": b"\x01",
              # 0 is not a theme prop (iHallTeam.onEnterHallTeam -> getHallThemeScore(0) -> None.PROP_TYPE)
              "hallThemeID": struct.pack("<i", outfit.theme or int(os.environ.get("HALL_THEME_ID", "270000"))),
              "dtsBodyAppearanceList": arr(outfit.body),
              "dtsWearableAppearanceList": arr(outfit.wear)}
        return b"".join(ov.get(n) or bwdefs.encode_default(t, fd) for n, t, fd in D.resolve("HALL_TEAM_MEMBER_CLIENT")[1])

    def _grant_props(self, prop_ids, force=False):
        """Add won appearance items to the client's package (other prop kinds: display only)."""
        appearance = set(_all_appearance_ids())
        info = _bw_blob(__import__("pickle").dumps({"ex_tm": 0}, protocol=2))
        calls = b""
        for iid in prop_ids:
            if force or iid in appearance:
                item = _bw_blob(os.urandom(16)) + struct.pack("<i", 1) + info + struct.pack("<i", 0)
                calls += athlete_method("onAddDtsAppearanceItem",
                                        struct.pack("<iI", iid, 1) + item + struct.pack("<ii", 0, 0), quiet=True)
        return calls

    def _lobby_data_calls(self):
        """Client-side Athlete attributes the real server fills at login (lobby UI reads them in
        UIMain.on_enter; a missing one aborts the whole lobby UI setup)."""
        import pickle, time as _t
        now = int(athlete_requests.game_now())
        lucky = {
            "operation": 10000,
            "luckySeasonDraws": 0, "luckyRoundCloseTime": now + 172800, "luckySeasonNo": 1,
            "luckyRoundBuff": 0, "luckyRoundState": 1, "luckySeasonEndTime": now + 30 * 86400,
            "luckySeasonGiftGotState": [], "luckyRoundGotIndex": [], "luckyRoundGift": [],
            "luckyRoundDraws": 0, "luckyRoundNo": 1, "luckySeasonCharge": 0,
            "luckyRoundGiftValue": 0, "luckyRoundRefreshTime": now + 21600,
            "luckyRoundIsSuper": False, "luckyRoundByRecommend": False,
        }   # all keys required: refreshLuckyCarnivalData indexes each of them (do not trim)
        py = lambda o: _bw_blob(pickle.dumps(o, protocol=2))
        month_rebate = {"awards": {}, "status": [0] * 32, "gotUpradePropIdxes": [], "exp": 0}
        # Server clock first: client_utils.getServerSysTime() = this origin + elapsed
        # BigWorld time (10 Hz ticks, hence tenths of a second); without it the client uses
        # the device clock.
        calls = (athlete_method("syncServerTime", struct.pack("<q", int(now * 10))) +
                 athlete_method("syncServerTimeZone", struct.pack("<qqq", 0, 0, 0)))
        # The monthly Supreme page (UIMonthlySupplyPackage) picks its box with the DEVICE clock
        # (supplement_utils.getCurrentMonthSupplementID uses time.time(); last box ends
        # 2022.12.30), so on a 2026 device it is blank and its Awake crashes. Turn the page off:
        # onSetSwitches = setattr(shared.switches, name, value).
        # Returning-player sign-in (UIDtsSign via huiliu) and friend recall (Recruit Rewards) pop
        # up at login once the date is in 2022; their data is not served, so UIDtsSign stays an
        # empty dim mask that blocks the lobby. Off as well (LOBBY_SWITCHES_OFF, comma list).
        off = os.environ.get("LOBBY_SWITCHES_OFF", "SysEnableMonthSupply,SysEnableHuiliuRecallSystem,"
                                                   "EnableRecallPlayer,EnableNewRecallPlayer")
        for sw in filter(None, (x.strip() for x in off.split(","))):
            calls += athlete_method("onSetSwitches", _bw_blob(sw.encode()) + b"\x00", quiet=True)
        # Weekly supply push (UIMgr.gotoThisWeekSupplyPackage) opens Supply at every login
        # until hasAlreadyShowSupplyID equals this week's box; the client reports it with
        # setHasAlreadyShowSupplyID.
        shown = (load_accounts().get("supply_push") or {}).get("id", 0)
        calls += athlete_method("onUpdateAlreadyShowSupplyID", struct.pack("<i", int(shown)))
        # Hall theme: dtsHallThemeID defaults to 0, which has no theme data. Leaving the outfit
        # screen restores the theme (HallTheme.onShowOriTheme -> onThemeChange -> onUIChange),
        # hits currentThemeData None ('DEFAULT_LIGHT'), aborts leave_ui and leaves every UI
        # hidden. 270000 = const.DEFAULT_HALL_THEME_ID.
        calls += athlete_method("onUpdateDtsHallThemeID",
                                struct.pack("<i", int(os.environ.get("HALL_THEME_ID", "270000"))))
        try:
            calls += athlete_method("onUpdateLuckyCarnivalData", py(lucky))
        except Exception as e:
            print(f"      [BASEAPP] Warning: onUpdateLuckyCarnivalData skipped: {e}")
        try:
            calls += athlete_method("gmsyncRedPoints", struct.pack("<I", 0))
        except Exception as e:
            print(f"      [BASEAPP] Warning: gmsyncRedPoints skipped: {e}")
        try:
            # version, dailyCount, weeklyCount, dailyTs, weeklyTs, weeklyGiftState, clickState, weeklyGotList
            calls += athlete_method("onAccumulateChargeUpdate", struct.pack("<7i", 0, 0, 0, 0, 0, 0, 0) + py([]))
        except Exception as e:
            print(f"      [BASEAPP] Warning: onAccumulateChargeUpdate skipped: {e}")
        try:
            # Minimal stub for enterHall; full supplement info is sent on demand when opening Supply screen.
            calls += athlete_method("onQueryAvailableSupplement", py({}))
            calls += athlete_method("onUpdateBuySupplementCntDict", py({}) + py({}) + py({}))
        except Exception as e:
            print(f"      [BASEAPP] Warning: onQueryAvailableSupplement stub skipped: {e}")
        try:
            # iVip.syncVipInfo; draw-result and ad screens read vipInfo["level"] / ["rewardStatus"].
            calls += athlete_method("syncVipInfo", py({"level": 0, "exp": 0, "rewardStatus": {}}))
        except Exception as e:
            print(f"      [BASEAPP] Warning: syncVipInfo skipped: {e}")
        try:
            calls += athlete_method("syncMonthPayRebateSpecialAwardInfo", py(month_rebate))
        except Exception as e:
            print(f"      [BASEAPP] Warning: syncMonthPayRebateSpecialAwardInfo skipped: {e}")
        try:
            # Event panel (UILimitWelfareController.on_enter) reads personalRecommendCanBuy, set
            # only by iPersonalRecommend.onPersonalRecommendStateUpdated(state, time, gift, version).
            # No personal offer: state 0, empty gift list.
            calls += athlete_method("onPersonalRecommendStateUpdated", struct.pack("<ii", 0, 0) + py([]) + struct.pack("<i", 0))
        except Exception as e:
            print(f"      [BASEAPP] Warning: onPersonalRecommendStateUpdated skipped: {e}")
        try:
            action_ids, suit_action_ids = _all_action_ids()
            emoji_ids = _all_emoji_ids()
            calls += athlete_method("onSyncSwitches", _bw_blob(b"SysEnableInGameAction") + b"\x01", quiet=True)
            calls += athlete_method("onSetSwitches", _bw_blob(b"SysEnableInGameAction") + b"\x01", quiet=True)
            calls += athlete_method("onSyncSwitches", _bw_blob(b"SysEnableEmoji") + b"\x01", quiet=True)
            calls += athlete_method("onSetSwitches", _bw_blob(b"SysEnableEmoji") + b"\x01", quiet=True)
            if action_ids:
                calls += athlete_method("syncDtsInGameActionAppearanceIDs", py(action_ids))
            if suit_action_ids:
                calls += athlete_method("syncDtsInGameActionSuitAppearanceIDs", py(suit_action_ids))
            if emoji_ids:
                arr_fn = lambda ids: struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", int(i)) for i in ids)
                calls += athlete_method("onUpdateDtsEmojiList", arr_fn(emoji_ids))
        except Exception as e:
            print(f"      [BASEAPP] Warning: action/emoji sync skipped: {e}")
        return calls

    def _unlock_all_batch(self, addr, bf_key, pos):
        """Give the test user every appearance item (onAddDtsAppearanceItem), a few per packet."""
        import pickle
        ids = _all_appearance_ids()
        n = int(os.environ.get("UNLOCK_BATCH", "12"))
        if pos >= len(ids) or self._hall_entered.get(addr) is None:
            if pos >= len(ids):
                print(f"      [BASEAPP] unlock-all done: {len(ids)} appearance items")
            return
        info = _bw_blob(pickle.dumps({"ex_tm": 0}, protocol=2))   # handler reads info["ex_tm"] (0 = permanent)
        calls = b""
        for iid in ids[pos:pos + n]:
            item = _bw_blob(os.urandom(16)) + struct.pack("<i", 1) + info + struct.pack("<i", 0)
            calls += athlete_method("onAddDtsAppearanceItem",
                                    struct.pack("<iI", iid, 1) + item + struct.pack("<ii", 0, 0), quiet=True)
        self._send_bundle(addr, calls, self._last_client_seq.get(addr), bytes(bf_key))
        asyncio.get_event_loop().call_later(float(os.environ.get("UNLOCK_GAP", "0.12")),
                                            self._unlock_all_batch, addr, bf_key, pos + n)

    def _push_appearance(self, addr, bf_key):
        import pickle
        arr = lambda ids: struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", i) for i in ids)
        py = lambda o: _bw_blob(pickle.dumps(o, protocol=2))
        body_ids = [int(x) for x in os.environ.get("APPEAR_BODY", "").split(",") if x.strip()]
        wear_ids = [int(x) for x in os.environ.get("APPEAR_WEAR", "").split(",") if x.strip()]
        calls = (athlete_method("onSetDtsAppearanceGender", struct.pack("<i", get_account_gender()[0])) +
                 athlete_method("onUpdateDtsShowBodyAppearanceList", arr(body_ids)) +
                 athlete_method("onUpdateDtsShowWearableAppearanceList", arr(wear_ids)))
        action_ids, suit_action_ids = _all_action_ids()
        emoji_ids = _all_emoji_ids()
        try:
            calls += athlete_method("onSetSwitches", _bw_blob(b"SysEnableInGameAction") + b"\x01", quiet=True)
            calls += athlete_method("onSetSwitches", _bw_blob(b"SysEnableEmoji") + b"\x01", quiet=True)
            if action_ids:
                calls += athlete_method("syncDtsInGameActionAppearanceIDs", py(action_ids))
            if suit_action_ids:
                calls += athlete_method("syncDtsInGameActionSuitAppearanceIDs", py(suit_action_ids))
            if emoji_ids:
                calls += athlete_method("onUpdateDtsEmojiList", arr(emoji_ids))
        except Exception as e:
            print(f"      [BASEAPP] Warning: _push_appearance action/emoji push failed: {e}")
        self._send_bundle(addr, calls, self._last_client_seq.get(addr), bytes(bf_key))
        print(f"      [BASEAPP] pushed appearance refresh body={body_ids} wear={wear_ids} + actions({len(action_ids)}) emojis({len(emoji_ids)})")

    def _transition_to_athlete(self, addr, bf_key):
        """Transition from Avatar battle/tutorial space into Athlete (Lobby/Hall player).
        PlayerAvatar already established Application.scene + Globals.player, satisfying
        prerequisites(). Sending resetEntities + createBasePlayer(Athlete) + enterHall
        causes PlayerAthlete.enterHall -> _realEnterHall -> SceneSystem.loadHallScene."""
        if self._athlete_sent.get(addr):
            return
        self._athlete_sent[addr] = True
        print(f"      [BASEAPP] Transitioning to Athlete (Lobby/Hall)...")

        # 1. Reset current entities in battle space and create Athlete (Lobby player)
        # TRANSITION_RESET=off keeps the Avatar in the world (Globals.player stays set, which
        # ClientEntity.prerequisites requires before the Athlete can enter and get its RPCs).
        reset = b"\x04\x00" if os.environ.get("TRANSITION_RESET", "on") == "on" else b""
        trans_body = reset + athlete_create_message()

        # 2. Athlete is Base-only in BW defs, but BigWorld Mercury requires createCellPlayer
        # to populate ServerConnection::pPlayer_ (0x140) and trigger enterWorld() on player.
        # Without pPlayer_, EntityMessageHandler (0x94bc24) drops all incoming RPCs!
        if os.environ.get("ATHLETE_CELL", "off") == "on":
            ccp = (struct.pack("<II", int(os.environ.get("CCP_SPACE", "1")), 0) +
                   struct.pack("<3f", 0.0, 0.0, 0.0) + struct.pack("<3f", 0.0, 0.0, 0.0))
            trans_body += b"\x06" + struct.pack("<H", len(ccp)) + ccp
            print(f"      [BASEAPP] + createCellPlayer(Athlete)")

        c_seq = self._last_client_seq.get(addr)
        self._send_bundle(addr, trans_body, c_seq, bytes(bf_key))

        # 3. Schedule Athlete.onLogin + enterHall timer (give 2s for PlayerAthlete creation)
        delay = float(os.environ.get("HALL_DELAY", "2.0"))
        asyncio.get_event_loop().call_later(delay, self._send_enter_hall_calls, addr, bytes(bf_key))

    def _send_bundle(self, addr, body, client_seq, bf_key):
        """Build, encrypt and send one on-channel packet.
        Footer layout (confirmed: client ACKs our seqs with this):
          [body] [seq u32 LE, if HAS_SEQUENCE] [ack u32 LE ...] [nAcks u8, if HAS_ACKS]"""
        import time as _t, loginapp
        max_body = int(os.environ.get("FRAG_BODY", "1200"))
        if len(body) > max_body:
            chunks = [body[i:i + max_body] for i in range(0, len(body), max_body)]
            first = self._server_seq
            last = first + len(chunks) - 1
            for n, chunk in enumerate(chunks):
                seq = self._server_seq
                self._server_seq += 1
                fl = 0x0008 | 0x0010 | 0x0040 | 0x0020
                footer_prefix = struct.pack("<II", first, last) + struct.pack("<I", seq)
                footer = footer_prefix
                if client_seq is not None and n == 0:
                    fl |= 0x0004
                    footer += struct.pack("<I", client_seq) + b"\x01"
                cleartext = struct.pack("<H", fl) + chunk + footer
                pad_len = 8 - (len(cleartext) % 8)
                padded = cleartext + b"\x00" * (pad_len - 1) + bytes([pad_len])
                self.transport.sendto(loginapp.custom_bf_encrypt(bf_key, padded), addr)
                self._unacked_packets.setdefault(addr, {})[seq] = {
                    'fl': fl, 'body': chunk, 'footer_prefix': footer_prefix, 'time': _t.time()
                }
                print(f"  [{_t.strftime('%H:%M:%S')}] [BASEAPP SEND] fragment {n + 1}/{len(chunks)} seq={seq} [{first}..{last}] {len(padded)}B")
            return
        fl = 0x0008                              # ON_CHANNEL
        footer_prefix = b""
        sent_seq = None
        if body:
            fl |= 0x0010 | 0x0040                # RELIABLE | HAS_SEQUENCE
            sent_seq = self._server_seq
            footer_prefix = struct.pack("<I", sent_seq)
            self._server_seq += 1
        footer = footer_prefix
        if client_seq is not None:
            fl |= 0x0004                         # HAS_ACKS
            footer += struct.pack("<I", client_seq) + b"\x01"
        cleartext = struct.pack("<H", fl) + body + footer
        pad_len = 8 - (len(cleartext) % 8)
        padded = cleartext + b"\x00" * (pad_len - 1) + bytes([pad_len])
        enc = loginapp.custom_bf_encrypt(bf_key, padded)
        self.transport.sendto(enc, addr)
        if sent_seq is not None:
            self._unacked_packets.setdefault(addr, {})[sent_seq] = {
                'fl': fl, 'body': body, 'footer_prefix': footer_prefix, 'time': _t.time()
            }
        print(f"  [{_t.strftime('%H:%M:%S')}] [BASEAPP SEND] flags=0x{fl:04x} {len(enc)}B seq={sent_seq} ack={client_seq} pt={cleartext.hex()}")


async def start_tcp_gate():
    loop = asyncio.get_event_loop()
    servers = []
    for port in (GATE_TCP_PORT, 25000):   # 25000 = game server port from server_list_ad.txt
        servers.append(await asyncio.start_server(handle_gate_client, HOST_IP, port))
        print(f"[*] NeoX TCP Gate Listener started on {HOST_IP}:{port}")
        await loop.create_datagram_endpoint(lambda p=port: GateUDP(p), local_addr=(HOST_IP, port))
        print(f"[*] NeoX UDP Gate Listener started on {HOST_IP}:{port}")
    await asyncio.gather(*(s.serve_forever() for s in servers))

def start_http_server():
    httpd = ThreadingHTTPServer((HOST_IP, HTTP_PORT), RoSHTTPHandler)
    print(f"[*] HTTP Patch/UniSDK Listener started on {HOST_IP}:{HTTP_PORT}")
    httpd.serve_forever()


class Stub8080Handler(BaseHTTPRequestHandler):
    """Minimal OK stub so UniSDK JNI stops blocking on PC:8080 ConnectException."""

    def log_message(self, fmt, *args):
        print(f"[HTTP:8080] {self.address_string()} {fmt % args}")

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"code":0,"status":"ok"}')

    def do_POST(self):
        self.do_GET()


def start_stub_8080():
    if os.environ.get("STUB_8080", "on") != "on":
        return
    httpd = ThreadingHTTPServer((HOST_IP, 8080), Stub8080Handler)
    print(f"[*] UniSDK stub HTTP on {HOST_IP}:8080 (STUB_8080=off to disable)")
    httpd.serve_forever()


class LoggingTLSServer(ThreadingHTTPServer):
    """HTTPS server that logs handshake failures (e.g. client rejected our cert)."""
    ssl_ctx = None

    def process_request_thread(self, request, client_address):
        # TLS handshake in the worker thread (not the accept loop): one stalled client
        # must not block every other HTTPS connection.
        try:
            request.settimeout(10)
            request = self.ssl_ctx.wrap_socket(request, server_side=True)
            request.settimeout(None)
        except Exception as e:
            print(f"[HTTPS] {client_address[0]} handshake error: {type(e).__name__}: {e}")
            try:
                self.shutdown_request(request)
            except Exception:
                pass
            return
        super().process_request_thread(request, client_address)

    def handle_error(self, request, client_address):
        import sys
        err = sys.exc_info()[1]
        print(f"[HTTPS] {client_address[0]} error: {type(err).__name__}: {err}")


def start_https_server():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(CERT_DIR, "server_chain.crt"), os.path.join(CERT_DIR, "server.key"))

    def sni_cb(sslobj, server_name, _ctx):
        print(f"[HTTPS] TLS ClientHello SNI={server_name}")
    ctx.sni_callback = sni_cb

    httpd = LoggingTLSServer((HOST_IP, HTTPS_PORT), RoSHTTPHandler, bind_and_activate=True)
    httpd.ssl_ctx = ctx   # per-connection wrap happens in LoggingTLSServer.process_request_thread
    print(f"[*] HTTPS Listener started on {HOST_IP}:{HTTPS_PORT}")
    httpd.serve_forever()


if __name__ == "__main__":
    import functools, builtins
    builtins.print = functools.partial(builtins.print, flush=True)  # unbuffered logs
    threading.Thread(target=start_http_server, daemon=True).start()
    threading.Thread(target=start_https_server, daemon=True).start()
    threading.Thread(target=start_stub_8080, daemon=True).start()
    asyncio.run(start_tcp_gate())