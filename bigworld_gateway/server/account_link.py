"""Link original-client logins to RoS_Server accounts through /api/v1/gateway.

Standard library only. If the API is not configured or not reachable, every call
returns None and ros_server.py keeps its local saved_accounts.json behaviour.

Settings (environment first, then <gateway>/.env, then the RoS_Server .env two folders up):
  ROS_API_URL      default http://127.0.0.1:8000
  GATEWAY_API_KEY  shared key; empty turns the link off
"""

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_FILES = (os.path.join(_HERE, "..", ".env"), os.path.join(_HERE, "..", "..", ".env"))
DEFAULT_UID = "9000000001"
_DEVICE_ID = re.compile(r"[0-9a-f]{8,64}")

_current = None  # last resolved account (dict), used by the single-player lobby code
_login_uid = None  # uid from the last Mercury login

# Presence: RoS_Server holds a 75 s lease per report. Renew every 20 s while packets keep
# arriving; report offline once a uid has been silent for 45 s. Reports run on one daemon
# thread, so the packet path only stamps a time and never waits on HTTP.
PRESENCE_EVERY = 20.0
PRESENCE_IDLE = 45.0
_presence_lock = threading.Lock()
_activity = {}  # uid -> monotonic time of the last packet
_reported = {}  # uid -> monotonic time of the last online report
_presence_thread = None

# Device details from the SDK requests that come before the Mercury login, keyed by uid.
# User-Agent "NeteaseMobileGame/a2.20.2 (V2266A;28)" -> model V2266A, Android API 28.
_SDK_UA = re.compile(r"NeteaseMobileGame/([a-z])[\w.]+ \(([^;()]{1,64});(\d{1,3})\)")
_ANDROID = {21: "5.0", 22: "5.1", 23: "6", 24: "7.0", 25: "7.1", 26: "8.0", 27: "8.1", 28: "9", 29: "10",
            30: "11", 31: "12", 32: "12L", 33: "13", 34: "14", 35: "15", 36: "16"}
_devices = {}  # uid -> {"model", "os_name", "client_version", "time_zone", "language"}


def device_uid(path):
    """SDK user id for the device that sent this request.

    Every NetEase SDK request carries ci=<device id> (16 hex, Android-ID style, stable per
    install). Hashing it gives each device its own 10-digit uid in 9000000000-9999999999,
    which the client then uses as its Mercury login name. CBP_GID pins one uid for all
    devices; DEVICE_UIDS=off restores the old shared uid.
    """
    if os.environ.get("CBP_GID"):
        return os.environ["CBP_GID"]
    if os.environ.get("DEVICE_UIDS", "on") != "on":
        return DEFAULT_UID
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(path or "").query)
    ci = (query.get("ci") or [""])[0].strip().lower()
    if not _DEVICE_ID.fullmatch(ci):
        return DEFAULT_UID
    return str(9_000_000_000 + int(hashlib.sha256(ci.encode()).hexdigest(), 16) % 1_000_000_000)


def note_login(username):
    """Remember the uid of the Mercury login in progress and return it."""
    global _login_uid
    _login_uid = uid_from_login(username)
    return _login_uid


def current_gid():
    """Player gid for entity properties: the logged-in uid, or the fixed default."""
    if os.environ.get("CBP_GID"):
        return int(os.environ["CBP_GID"])
    if _login_uid and _login_uid.isdigit():
        return int(_login_uid)
    return int(DEFAULT_UID)


def _dotenv(name):
    for env_file in _ENV_FILES:
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(name + "="):
                        value = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if value:
                            return value
        except OSError:
            pass
    return ""


def _setting(name, default=""):
    return os.environ.get(name) or _dotenv(name) or default


def enabled():
    return bool(_setting("GATEWAY_API_KEY"))


def uid_from_login(username):
    """'9000000001@ad.netease_global.win.163.com' -> '9000000001'."""
    if isinstance(username, bytes):
        username = username.decode("utf-8", errors="replace")
    return (username or "").split("@", 1)[0].strip() or None


def _call(method, path, body):
    key = _setting("GATEWAY_API_KEY")
    if not key:
        return None
    url = _setting("ROS_API_URL", "http://127.0.0.1:8000").rstrip("/") + path
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json", "X-Gateway-Key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=float(_setting("ROS_API_TIMEOUT", "2"))) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read()[:200]
        print(f"[ACC-LINK] {method} {path} -> HTTP {e.code} {detail!r}")
        return {"_error": e.code}
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"[ACC-LINK] {method} {path} failed ({e}); using local accounts")
        return None


def resolve(uid, ip_address=None):
    """Find or create the account for this uid. Returns the account dict or None."""
    global _current
    if not uid:
        return None
    body = {"external_uid": uid, "ip_address": ip_address}
    if _devices.get(uid):
        body["device"] = _devices[uid]
    data = _call("POST", "/api/v1/gateway/accounts/resolve", body)
    if not data or "_error" in data:
        _current = None
        return None
    data["external_uid"] = uid
    _current = data
    print(
        f"[ACC-LINK] uid={uid} -> {data['username']} nickname={data['nickname']!r} "
        f"char={data['char_type']} status={data['status']} new={data['is_new']}"
    )
    return data


def set_character(nickname, char_type, uid=None):
    """Save the created character. Returns the account dict, or None if it was not saved."""
    global _current
    uid = uid or (_current or {}).get("external_uid")
    if not uid:
        return None
    data = _call(
        "PUT",
        f"/api/v1/gateway/accounts/{urllib.parse.quote(uid, safe='')}/character",
        {"nickname": nickname, "char_type": int(char_type)},
    )
    if not data or "_error" in data:
        return None
    data["external_uid"] = uid
    _current = data
    return data


def set_portrait(file_id, uid=None):
    """Save the player's avatar file id ("" = built-in). Returns the account dict or None."""
    global _current
    uid = uid or (_current or {}).get("external_uid")
    if not uid:
        return None
    data = _call(
        "PUT",
        f"/api/v1/gateway/accounts/{urllib.parse.quote(uid, safe='')}/portrait",
        {"portrait": file_id},
    )
    if not data or "_error" in data:
        return None
    data["external_uid"] = uid
    _current = data
    return data


def _uid_path(suffix):
    uid = (_current or {}).get("external_uid")
    return f"/api/v1/gateway/accounts/{urllib.parse.quote(uid, safe='')}/{suffix}" if uid else None


def get_state():
    """{"yuanbao", "items": [{"prop_id", "number"}], "outfit": {"body", "wear"}} or None."""
    path = _uid_path("state")
    data = _call("GET", path, None) if path else None
    return None if not data or "_error" in data else data


def purchase(price, props, reason):
    """Charge `price` diamonds and add `props` on RoS_Server.
    Returns {"yuanbao", "added"}; {"_error": 409} when the balance is too low; None if not linked/down."""
    path = _uid_path("purchase")
    return _call("POST", path, {"price": int(price), "props": [int(p) for p in props], "reason": reason}) if path else None


def set_outfit(body, wear):
    path = _uid_path("outfit")
    data = _call("PUT", path, {"body": list(body), "wear": list(wear)}) if path else None
    return None if not data or "_error" in data else data


def get_profile():
    """My Page / Stats / Credit data (RoS_Server GatewayProfile) or None if not linked/down."""
    path = _uid_path("profile")
    data = _call("GET", path, None) if path else None
    return None if not data or "_error" in data else data


def claim_credit_reward():
    """{"awards": [prop ids], "credit": {...}} for the Claim button, or None if not linked/down."""
    path = _uid_path("credit/claim")
    data = _call("POST", path, {}) if path else None
    return None if not data or "_error" in data else data


def current():
    return _current


def parse_device(path, user_agent):
    """Device fields from one SDK request; only the ones present are returned."""
    device = {}
    match = _SDK_UA.search(user_agent or "")
    if match:
        platform, model, level = match.group(1), match.group(2).strip(), int(match.group(3))
        device["model"] = model[:64]
        if platform == "a":  # only the Android form has been seen; others keep the model only
            device["os_name"] = f"Android {_ANDROID[level]}" if level in _ANDROID else f"Android API {level}"
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(path or "").query)
    for key, field, limit in (("gv", "client_version", 32), ("time_zone", "time_zone", 64), ("lang", "language", 16)):
        value = (query.get(key) or [""])[0].strip()
        if value:
            device[field] = value[:limit]
    return device


def note_device(path, user_agent):
    """Remember what this device's SDK request said, for the login that follows."""
    if "ci=" not in (path or ""):
        return
    device = parse_device(path, user_agent)
    if device:
        uid = device_uid(path)
        _devices[uid] = {**_devices.get(uid, {}), **device}


def touch(uid=None):
    """Note a packet from the linked player. Cheap: no I/O on this thread."""
    uid = uid or (_current or {}).get("external_uid")
    if not uid or not enabled():
        return
    with _presence_lock:
        _activity[uid] = time.monotonic()
    _start_presence()


def report_presence(uid, online):
    """POST /presence. Returns the server's answer (bool) or None if not linked/down."""
    data = _call("POST", f"/api/v1/gateway/accounts/{urllib.parse.quote(uid, safe='')}/presence", {"online": bool(online)})
    return None if not data or "_error" in data else bool(data.get("online"))


def presence_tick(now=None):
    """One reporter pass: renew active uids, end silent ones. Returns [(uid, online), ...] sent."""
    now = time.monotonic() if now is None else now
    with _presence_lock:
        seen = list(_activity.items())
    sent = []
    for uid, last in seen:
        if now - last < PRESENCE_IDLE:
            if now - _reported.get(uid, float("-inf")) >= PRESENCE_EVERY:
                report_presence(uid, True)
                _reported[uid] = now
                sent.append((uid, True))
            continue
        if uid in _reported:
            report_presence(uid, False)
            del _reported[uid]
            sent.append((uid, False))
        with _presence_lock:
            if _activity.get(uid) == last:
                del _activity[uid]
    return sent


def _presence_loop():
    while True:
        try:
            presence_tick()
        except Exception as e:  # never let a report kill the thread
            print(f"[ACC-LINK] presence report failed: {e!r}")
        time.sleep(5)


def _start_presence():
    global _presence_thread
    if _presence_thread is not None and _presence_thread.is_alive():
        return
    _presence_thread = threading.Thread(target=_presence_loop, name="ros-presence", daemon=True)
    _presence_thread.start()
