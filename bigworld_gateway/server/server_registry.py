"""This gateway as a game server on RoS_Server: heartbeat + server-select list from the API.

Heartbeat: every HEARTBEAT_SECS, while linked (account_link.enabled()), POST
/api/v1/gateway/servers/heartbeat with this process's address, version and player counts. The API
registers the server on the first beat and the Game servers page shows it live.

Server list: the client fetches server_list_ad.txt and parses one line per server
(ui.UILogin.parseOneServerInfo, keys in order: zone, numberSt, serverSt, name, oriName, tel, cnc,
edu, groupid), e.g.
    Region 1 8 2 Private-Server Private-Server 192.0.2.10:25000 192.0.2.10:25000 192.0.2.10:25000 10001
server_list_text() builds those lines from GET /api/v1/gateway/servers (listed servers, operator
names). None when not linked or the API is down: the caller then serves the static file.

numberSt drives the coloured spot and text (UIServerList.number_st_icon / number_st_txt: green,
yellow, red, grey). Only 8 is verified (green "Fast", seen on LDPlayer); the codes for busy, full and
maintenance are not extracted yet (read them with client/frida/payloads/server_status_codes.py) and
default to 8 until SERVER_STATUS_CODES (e.g. "smooth:8,busy:5,full:1,maintenance:0") is set. To take
a server out of the game's list, untick "listed" on the Game servers page.
"""
import os
import threading
import time

import account_link

HEARTBEAT_SECS = float(os.environ.get("SERVER_HEARTBEAT_SECS", "10"))
ACTIVE_SECS = float(os.environ.get("SERVER_ACTIVE_SECS", "30"))   # a client silent this long is gone
LIST_TTL = float(os.environ.get("SERVER_LIST_TTL", "10"))
SERVER_ST = 2                       # serverSt column; every known list uses 2
VERIFIED_CODES = {"smooth": 8}      # numberSt seen on device
STARTED_AT = time.time()

_lock = threading.Lock()
_seen = {}                          # addr -> (monotonic time, in_match)
_thread = None
_list_cache = (0.0, None)           # (monotonic time, text or None)
_last_beat = None                   # last heartbeat answer (dict) or None


def server_key():
    return os.environ.get("GATEWAY_SERVER_KEY", "main")


def default_name():
    return os.environ.get("GATEWAY_SERVER_NAME", "Private-Server")


def host():
    return os.environ.get("ROS_PC_IP", "127.0.0.1")


def port():
    return int(os.environ.get("GATEWAY_SERVER_PORT", "25000"))


def version():
    return os.environ.get("GATEWAY_VERSION", "bigworld_gateway")


def status_codes():
    codes = {"smooth": 8, "busy": 8, "full": 8, "maintenance": 8}
    codes.update(VERIFIED_CODES)
    for part in filter(None, os.environ.get("SERVER_STATUS_CODES", "").split(",")):
        name, _, value = part.partition(":")
        if name.strip() in codes and value.strip().lstrip("-").isdigit():
            codes[name.strip()] = int(value)
    return codes


# ---- player counts ------------------------------------------------------------------------------

def note(addr, in_match=False, now=None):
    """Record a BaseApp packet from a client address (cheap; called on the packet path)."""
    with _lock:
        _seen[addr] = (time.monotonic() if now is None else now, bool(in_match))


def counts(now=None):
    """(players online, players in a match) over clients heard from in the last ACTIVE_SECS."""
    now = time.monotonic() if now is None else now
    with _lock:
        for addr in [a for a, (t, _m) in _seen.items() if now - t > ACTIVE_SECS]:
            del _seen[addr]
        active = list(_seen.values())
    return len(active), sum(1 for _t, in_match in active if in_match)


# ---- heartbeat ----------------------------------------------------------------------------------

def heartbeat_body(now=None):
    online, in_match = counts(now)
    return {
        "server_key": server_key(), "name": default_name(), "host": host(), "port": port(),
        "version": version(), "players_online": online, "players_in_match": in_match,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(STARTED_AT)),
    }


def heartbeat():
    """One heartbeat. Returns the API's answer (name, status, listed) or None (not linked / down)."""
    global _last_beat
    if not account_link.enabled():
        return None
    data = account_link._call("POST", "/api/v1/gateway/servers/heartbeat", heartbeat_body())
    _last_beat = None if not data or "_error" in data else data
    return _last_beat


def _loop():
    while True:
        try:
            heartbeat()
        except Exception as e:      # never let a report kill the thread
            print(f"[SERVERS] heartbeat failed: {e!r}")
        time.sleep(HEARTBEAT_SECS)


def start():
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, name="ros-server-heartbeat", daemon=True)
    _thread.start()
    print(f"[SERVERS] heartbeat every {HEARTBEAT_SECS:.0f}s as '{server_key()}' ({host()}:{port()})")


# ---- server list --------------------------------------------------------------------------------

def list_line(entry, codes=None):
    codes = codes or status_codes()
    addr = f"{entry['host']}:{int(entry['port'])}"
    name = entry["name"]
    code = codes.get(entry.get("status") or "smooth", codes["smooth"])
    return (f"Region {int(entry['zone'])} {code} {SERVER_ST} {name} {name} "
            f"{addr} {addr} {addr} {int(entry['group_id'])} ")


def build_list(entries, codes=None):
    """server_list_ad.txt body for these API entries (same layout as real/server_list_ad.local.txt)."""
    lines = [list_line(e, codes) for e in entries if e.get("listed", True)]
    return ("\n".join(lines) + "\n#network=tel").encode("ascii") if lines else None


def server_list_text(now=None):
    """Bytes for /server_list_ad.txt from the API, cached LIST_TTL; None -> serve the static file."""
    global _list_cache
    if os.environ.get("SERVER_LIST_FROM_API", "on") == "off" or not account_link.enabled():
        return None
    now = time.monotonic() if now is None else now
    at, text = _list_cache
    if text is not None and now - at < LIST_TTL:
        return text
    data = account_link._call("GET", "/api/v1/gateway/servers", None)
    if not data or "_error" in data:
        return text                 # keep the last good list while the API is briefly down
    text = build_list(data.get("servers") or [])
    _list_cache = (now, text)
    return text
