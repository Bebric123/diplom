from datetime import datetime, timedelta, timezone

import pytest

from src.services.stats_service import (
    default_range_days,
    parse_iso_utc,
    resolve_time_range,
)


def test_parse_iso_utc_none():
    assert parse_iso_utc(None) is None
    assert parse_iso_utc("") is None


def test_parse_iso_utc_z_suffix():
    dt = parse_iso_utc("2026-03-15T10:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.hour == 10


def test_parse_iso_utc_offset():
    dt = parse_iso_utc("2026-03-15T12:00:00+03:00")
    assert dt is not None


def test_default_range_days_order():
    start, end = default_range_days(7)
    assert start < end
    assert (end - start) >= timedelta(days=6, hours=23)


def test_resolve_time_range_defaults():
    start, end = resolve_time_range(None, None, default_days=7)
    assert end.tzinfo is not None
    assert start < end
    assert (end - start) >= timedelta(days=6, hours=23)


def test_resolve_time_range_swapped_if_inverted():
    start = datetime(2026, 3, 20, tzinfo=timezone.utc)
    end = datetime(2026, 3, 10, tzinfo=timezone.utc)
    a, b = resolve_time_range(
        start.isoformat().replace("+00:00", "Z"),
        end.isoformat().replace("+00:00", "Z"),
        default_days=7,
    )
    assert a <= b

