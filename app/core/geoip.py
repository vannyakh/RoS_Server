"""Offline IP-to-country lookup.

Reads an MMDB country database from GEOIP_DB_PATH (for example DB-IP "IP to Country Lite",
CC BY 4.0, or MaxMind GeoLite2-Country). No IP address leaves this server. Without the
`maxminddb` package or the file, every lookup returns None and logins still work.
"""

import ipaddress
import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_public(ip: str | None) -> bool:
    if not ip:
        return False
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return address.is_global


@lru_cache(maxsize=1)
def _reader(path: str):
    if not path:
        return None
    try:
        import maxminddb
    except ImportError:
        logger.warning("GEOIP_DB_PATH is set but the maxminddb package is not installed")
        return None
    try:
        return maxminddb.open_database(path)
    except (OSError, ValueError) as exc:
        logger.warning("GeoIP database could not be opened: %s", type(exc).__name__)
        return None


def country_for(ip: str | None) -> str | None:
    """ISO 3166 alpha-2 code for a public IP, or None (private IP, no database, not found)."""
    if not is_public(ip):
        return None
    reader = _reader(settings.geoip_db_path)
    if reader is None:
        return None
    try:
        record = reader.get(ip)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    country = record.get("country") or record.get("registered_country") or {}
    code = country.get("iso_code") if isinstance(country, dict) else None
    return code.upper() if isinstance(code, str) and len(code) == 2 else None
