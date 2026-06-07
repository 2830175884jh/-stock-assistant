from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_assistant.data.calendar import (
    find_latest_trade_date_from_files,
    is_yyyymmdd,
    read_latest_trade_date,
    resolve_data_date,
    write_latest_trade_date,
)


def test_date_validation() -> None:
    assert is_yyyymmdd("20260607")
    assert not is_yyyymmdd("2026-06-07")
    assert not is_yyyymmdd("20261301")


def test_anchor_roundtrip(tmp_path: Path) -> None:
    write_latest_trade_date(tmp_path, "20260605")
    assert read_latest_trade_date(tmp_path) == "20260605"
    assert resolve_data_date(tmp_path) == "20260605"


def test_find_latest_trade_date_from_files(tmp_path: Path) -> None:
    (tmp_path / "daily_20260601.csv").write_text("x\n", encoding="utf-8")
    (tmp_path / "daily_20260603.csv").write_text("x\n", encoding="utf-8")
    assert find_latest_trade_date_from_files(tmp_path) == "20260603"

