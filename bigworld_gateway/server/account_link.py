"""Link original-client logins to RoS_Server accounts through /api/v1/gateway.

Standard library only. If the API is not configured or not reachable, every call
returns None and ros_server.py keeps its local saved_accounts.json behaviour.

Settings (environment first, then <gateway>/.env, then the RoS_Server .env two folders up):
  ROS_API_URL      default http://127.0.0.1:8000
  GATEWAY_API_KEY  shared key; empty turns the link off
"""

import hashlib
import os
import re
import threading
import time
import urllib.parse

import api_client  # pooled keep-alive HTTP client for /api/v1/gateway (server/api_client.py)

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


def _call(method, path, body, retry_stale=False):
    """One request to RoS_Server through the shared pooled api_client.ApiClient (same return
    contract as before: None when not linked/down, {"_error": status, "detail"?} on non-2xx).
    Tests replace this function; every RoS_Server call in this module goes through it."""
    if not _setting("GATEWAY_API_KEY"):
        return None
    try:
        client = api_client.from_settings(_setting)
    except ValueError as e:  # bad ROS_API_URL / timeout setting: behave as "not reachable"
        print(f"[ACC-LINK] {method} {path} failed ({e}); using local accounts")
        return None
    return client.call(method, path, body, retry_stale=retry_stale)


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


def set_head_frame(frame_id, uid=None):
    """Save the worn avatar frame (HeadFrameAppearanceType prop id, 0 = none). Returns the account dict or None."""
    global _current
    uid = uid or (_current or {}).get("external_uid")
    if not uid:
        return None
    data = _call("PUT", f"/api/v1/gateway/accounts/{urllib.parse.quote(uid, safe='')}/head-frame",
                 {"head_frame": int(frame_id)})
    if not data or "_error" in data:
        return None
    data["external_uid"] = uid
    _current = data
    return data


def set_national_flag(flag, uid=None):
    """Save the player's country code ("" = none). Returns the account dict or None."""
    global _current
    uid = uid or (_current or {}).get("external_uid")
    if not uid:
        return None
    data = _call("PUT", f"/api/v1/gateway/accounts/{urllib.parse.quote(uid, safe='')}/national-flag",
                 {"national_flag": flag})
    if not data or "_error" in data:
        return None
    data["external_uid"] = uid
    _current = data
    return data


def _uid_path(suffix):
    uid = (_current or {}).get("external_uid")
    return f"/api/v1/gateway/accounts/{urllib.parse.quote(uid, safe='')}/{suffix}" if uid else None


def get_state():
    """{"yuanbao", "items": [{"prop_id", "number"}], "outfit": {"body", "wear", "theme"}, "head_frame",
    "recent_got": [prop_id, ...], "currencies": {"1": gold}} or None. Items with number 0 are not
    listed; currency keys are the client currency id as a string (only "1", gold coins, is stored)."""
    path = _uid_path("state")
    data = _call("GET", path, None) if path else None
    return None if not data or "_error" in data else data


def ledger_reason(reason):
    """RoS_Server only takes ledger reasons matching ^[a-z0-9_.:-]+$ (max 64); anything else is
    answered 422 and the purchase is refused (e.g. "mall-multi:[10002]" from the Lobby Theme BUY)."""
    text = re.sub(r"[^a-z0-9_.:-]+", ".", str(reason).lower()).strip(".")[:64]
    return text or "gateway"


def topup(amount, reference, reason="topup"):
    """Add diamonds on RoS_Server for a private IAP reference.
    Returns {"yuanbao", "replayed"?}; 409 when the reference was already credited; None if down."""
    path = _uid_path("topup")
    if not path:
        return None
    ref = ledger_reason(reference)[:40] or "iap"
    body = {
        "amount": int(amount),
        "reference": ref,
        "reason": ledger_reason(reason) or "gateway:topup",
    }
    return _call("POST", path, body, retry_stale=True)


def purchase(price, props, reason, request_id=None):
    """Charge `price` diamonds and add `props` on RoS_Server.
    Returns {"yuanbao", "added", "replayed"?}; {"_error": 409} when the balance is too low; None if
    not linked/down. `request_id` (8..64 of [A-Za-z0-9_-]) makes the purchase idempotent: RoS_Server
    applies one id once and answers a repeat with the first result and replayed=true."""
    path = _uid_path("purchase")
    if not path:
        return None
    body = {"price": int(price), "props": [int(p) for p in props], "reason": ledger_reason(reason)}
    if request_id:
        body["request_id"] = str(request_id)
    return _call("POST", path, body, retry_stale=bool(request_id))


def _counts(pairs):
    return [{"prop_id": int(p), "number": int(n)} for p, n in pairs]


def workshop_compound(request_id, require, consume, consume_currency, add, reason):
    """Depot > Workshop upgrade, applied atomically by RoS_Server.

    require / consume / add are lists of (prop_id, number); consume_currency is a list of
    (currency_id, amount) and only currency 1 (gold) is accepted. Returns
    {"items": [{"prop_id", "number"}], "currencies": {"1": gold}, "replayed": bool};
    {"_error": 409, "detail": {"code": "insufficient", "missing": [...]}} when the player lacks
    an item or gold (nothing changed); None if not linked/down. The same request_id is applied
    once: a retry returns the first result with replayed=True."""
    path = _uid_path("workshop/compound")
    if not path:
        return None
    return _call("POST", path, {
        "request_id": str(request_id),
        "require": _counts(require),
        "consume": _counts(consume),
        "consume_currency": [{"currency_id": int(c), "amount": int(a)} for c, a in consume_currency],
        "add": _counts(add),
        "reason": ledger_reason(reason),
    })


def dev_grant(props, currencies):
    """Development only (RoS_Server answers 404 unless APP_ENV=development): add props
    [(prop_id, number)] and currencies [(currency_id, amount)]. Returns the state dict or None."""
    path = _uid_path("dev/grant")
    data = _call("POST", path, {
        "props": _counts(props),
        "currencies": [{"currency_id": int(c), "amount": int(a)} for c, a in currencies],
    }) if path else None
    return None if not data or "_error" in data else data


def set_outfit(outfit):
    """Save depot outfit (body, wear, weapon, vehicle, hall_vehicle, show_*, theme, recent_got)."""
    path = _uid_path("outfit")
    if not path:
        return None
    if not isinstance(outfit, dict):
        outfit = {"body": list(outfit), "wear": [], "theme": 0}
    data = _call("PUT", path, outfit)
    return None if not data or "_error" in data else data


def persist_recent_got(recent):
    """Store Athlete.recentGotPropIDList without changing the worn outfit."""
    state = get_state() or {}
    outfit = dict(state.get("outfit") or {})
    outfit["recent_got"] = [int(x) for x in recent[:20]]
    return set_outfit(outfit)


def get_profile():
    """My Page / Stats / Credit data (RoS_Server GatewayProfile) or None if not linked/down."""
    path = _uid_path("profile")
    data = _call("GET", path, None) if path else None
    return None if not data or "_error" in data else data


def record_match(report):
    """POST one finished match (`GatewayMatchReport` fields) for the linked account.

    Returns the updated profile dict, or None when the link is off, RoS_Server is down, the uid
    is unknown (404), or validation fails. Never raises into the match loop. There is no match id
    on the route: each call adds one row to season/all-time stats — call at most once per match;
    retries double-count."""
    path = _uid_path("matches")
    if not path or not isinstance(report, dict):
        return None
    data = _call("POST", path, report)
    return None if not data or "_error" in data else data


def claim_credit_reward():
    """{"awards": [prop ids], "credit": {...}} for the Claim button, or None if not linked/down."""
    path = _uid_path("credit/claim")
    data = _call("POST", path, {}) if path else None
    return None if not data or "_error" in data else data


# System mail (UISystemMail). MailView = {"mail_id", "type" (SysMailTypeEnum: 0 TXT, 1 PROPS),
# "title", "sender", "abstract", "sent_at" (unix), "deadline" (unix, 0 = none), "unread", "claimed",
# "attachments": [{"prop_id", "number"}], "gold"}. Deleted and expired mail is never listed.

def list_mails():
    """[MailView, ...] newest first, or None if not linked/down."""
    path = _uid_path("mails")
    data = _call("GET", path, None) if path else None
    return None if not data or "_error" in data else data.get("mails", [])


def mail_detail(mail_id):
    """MailView + "content", and marks the mail read. {"_error": 404, ...} when it is missing,
    deleted or expired (client: onLoadMailDetailFailed); None if not linked/down."""
    path = _uid_path(f"mails/{int(mail_id)}")
    return _call("GET", path, None) if path else None


def claim_mail(mail_id):
    """Add the mail's attachments and gold on RoS_Server, once. Returns {"props": [{"prop_id",
    "number"}], "gold", "items": [{"prop_id", "number"}] (current counts), "currencies": {"1": gold},
    "replayed": bool}; a repeat claim adds nothing and has replayed=True. {"_error": 404, ...} when
    missing/deleted/expired; None if not linked/down."""
    path = _uid_path(f"mails/{int(mail_id)}/claim")
    return _call("POST", path, {}) if path else None


def delete_mail(mail_id):
    """Soft delete; unclaimed attachments are forfeited. True when RoS_Server deleted it."""
    path = _uid_path(f"mails/{int(mail_id)}")
    data = _call("DELETE", path, None) if path else None
    return data is not None and "_error" not in data


# Operator store listings (price / on-sale overrides). Fetched at most every LISTINGS_TTL
# seconds, so an admin change reaches the store without a gateway restart. When RoS_Server
# is down or the link is off the result is [] (client prices), also cached for the TTL so a
# dead server does not add a timeout to every store request.
# The fetch goes through _call (the pooled api_client) rather than ApiClient.get_cached, so
# the one seam tests replace (_call) also serves listings; this cache is pinned by
# tests/unit/test_gateway_store_listings.py (_listings_cache, time.monotonic).
LISTINGS_TTL = 15.0
_listings_cache = (None, [])  # (monotonic fetch time or None, rows)


def store_listings():
    global _listings_cache
    fetched, rows = _listings_cache
    now = time.monotonic()
    if fetched is not None and now - fetched < LISTINGS_TTL:
        return rows
    data = _call("GET", "/api/v1/gateway/store/listings", None)
    rows = data.get("listings", []) if isinstance(data, dict) and "_error" not in data else []
    _listings_cache = (now, rows)
    return rows


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
    data = _call("POST", f"/api/v1/gateway/accounts/{urllib.parse.quote(uid, safe='')}/presence", {"online": bool(online)}, retry_stale=True)
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
