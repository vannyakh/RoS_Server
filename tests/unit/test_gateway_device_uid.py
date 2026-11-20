"""bigworld_gateway gives each device its own SDK uid, derived from the ci= device id."""

import importlib
import sys
from pathlib import Path

import pytest

SDK_PATH = "/api/users/login/v2/sdk_token?game_id=123&ci={ci}&lang=en-US"


@pytest.fixture
def link(monkeypatch):
    monkeypatch.delenv("CBP_GID", raising=False)
    monkeypatch.delenv("DEVICE_UIDS", raising=False)
    monkeypatch.syspath_prepend(str(Path("bigworld_gateway/server").resolve()))
    module = importlib.import_module("account_link")
    yield importlib.reload(module)
    sys.modules.pop("account_link", None)


def test_each_device_id_maps_to_its_own_stable_ten_digit_uid(link):
    first = link.device_uid(SDK_PATH.format(ci="ae5633f89bc1f549"))
    again = link.device_uid(SDK_PATH.format(ci="AE5633F89BC1F549"))
    other = link.device_uid(SDK_PATH.format(ci="0123456789abcdef"))
    assert first == again
    assert first != other
    for uid in (first, other):
        assert uid.isdigit() and len(uid) == 10 and uid.startswith("9")


def test_missing_or_odd_device_id_falls_back_to_the_shared_uid(link):
    assert link.device_uid("/api/users/login/v2/sdk_token?game_id=123") == link.DEFAULT_UID
    assert link.device_uid(SDK_PATH.format(ci="not-hex!")) == link.DEFAULT_UID


def test_overrides_pin_or_disable_per_device_uids(link, monkeypatch):
    path = SDK_PATH.format(ci="ae5633f89bc1f549")
    monkeypatch.setenv("DEVICE_UIDS", "off")
    assert link.device_uid(path) == link.DEFAULT_UID
    monkeypatch.setenv("CBP_GID", "9000000042")
    assert link.device_uid(path) == "9000000042"


def test_gid_follows_the_mercury_login_name(link):
    assert link.current_gid() == int(link.DEFAULT_UID)
    assert link.note_login(b"9123456789@ad.netease_global.win.163.com") == "9123456789"
    assert link.current_gid() == 9123456789


SDK_GET = (
    "/api/games/config?game_id=123&gv=1227927&time_zone=Asia%2FPhnom_Penh&lang=en-US&ci=ae5633f89bc1f549"
)
SDK_UA = "com.netease.chiji/1227927 NeteaseMobileGame/a2.20.2 (V2266A;28)"


def test_sdk_request_reports_model_os_version_and_time_zone(link):
    assert link.parse_device(SDK_GET, SDK_UA) == {
        "model": "V2266A",
        "os_name": "Android 9",
        "client_version": "1227927",
        "time_zone": "Asia/Phnom_Penh",
        "language": "en-US",
    }
    assert link.parse_device("/x?gv=1", "curl/8") == {"client_version": "1"}


def test_device_is_kept_for_the_uid_that_logs_in(link, monkeypatch):
    link._devices.clear()
    link.note_device(SDK_GET, SDK_UA)
    uid = link.device_uid(SDK_GET)
    assert link._devices[uid]["model"] == "V2266A"
    sent = {}
    monkeypatch.setattr(link, "_call", lambda method, path, body: sent.update(body) or None)
    link.resolve(uid, "192.168.1.50")
    assert sent["device"]["os_name"] == "Android 9"
