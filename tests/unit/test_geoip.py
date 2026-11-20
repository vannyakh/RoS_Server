"""Offline country lookup: public IPs only, nothing without a database."""

from app.core import geoip


class _Reader:
    def get(self, ip):
        return {"country": {"iso_code": "kh"}} if ip == "203.0.113.9" else None


def test_private_and_bad_addresses_have_no_country(monkeypatch):
    monkeypatch.setattr(geoip, "_reader", lambda path: _Reader())
    for ip in (None, "", "192.168.1.50", "127.0.0.1", "10.0.0.1", "not-an-ip"):
        assert geoip.country_for(ip) is None
    assert geoip.is_public("8.8.8.8") is True
    assert geoip.is_public("192.168.1.50") is False


def test_public_address_uses_the_database(monkeypatch):
    monkeypatch.setattr(geoip, "_reader", lambda path: _Reader())
    monkeypatch.setattr(geoip, "is_public", lambda ip: True)
    assert geoip.country_for("203.0.113.9") == "KH"
    assert geoip.country_for("203.0.113.10") is None


def test_no_database_means_no_country(monkeypatch):
    monkeypatch.setattr(geoip.settings, "geoip_db_path", "")
    geoip._reader.cache_clear()
    monkeypatch.setattr(geoip, "is_public", lambda ip: True)
    assert geoip.country_for("8.8.8.8") is None
