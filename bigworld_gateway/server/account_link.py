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
import urllib.error
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_FILES = (os.path.join(_HERE, "..", ".env"), os.path.join(_HERE, "..", "..", ".env"))
DEFAULT_UID = "9000000001"
_DEVICE_ID = re.compile(r"[0-9a-f]{8,64}")

_current = None  # last resolved account (dict), used by the single-player lobby code
_login_uid = None  # uid from the last Mercury login


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
    data = _call("POST", "/api/v1/gateway/accounts/resolve", {"external_uid": uid, "ip_address": ip_address})
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
