from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path


DATE_FORMAT = "%Y%m%d"
ANCHOR_FILE = "_latest_trade_date.txt"


def normalize_date(value: str | None = None) -> str:
    if value is None or value == "":
        return date.today().strftime(DATE_FORMAT)
    if not is_yyyymmdd(value):
        raise ValueError("日期格式必须是 YYYYMMDD，例如 20260607。")
    return value


def is_yyyymmdd(value: str) -> bool:
    if len(value) != 8 or not value.isdigit():
        return False
    try:
        datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        return False
    return True


def previous_day(value: str) -> str:
    dt = datetime.strptime(value, DATE_FORMAT).date() - timedelta(days=1)
    return dt.strftime(DATE_FORMAT)


def anchor_path(a_share_dir: Path) -> Path:
    return a_share_dir / ANCHOR_FILE


def write_latest_trade_date(a_share_dir: Path, trade_date: str) -> Path:
    if not is_yyyymmdd(trade_date):
        raise ValueError("交易日锚点必须是 YYYYMMDD 格式。")
    path = anchor_path(a_share_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(trade_date, encoding="utf-8")
    return path


def read_latest_trade_date(a_share_dir: Path) -> str | None:
    path = anchor_path(a_share_dir)
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value if is_yyyymmdd(value) else None


def find_latest_trade_date_from_files(a_share_dir: Path) -> str | None:
    candidates: list[str] = []
    for file_path in a_share_dir.glob("daily_*.csv"):
        value = file_path.stem.replace("daily_", "", 1)
        if is_yyyymmdd(value):
            candidates.append(value)
    return max(candidates) if candidates else None


def resolve_data_date(a_share_dir: Path, requested_date: str | None = None) -> str:
    if requested_date:
        return normalize_date(requested_date)

    anchored = read_latest_trade_date(a_share_dir)
    if anchored:
        return anchored

    from_files = find_latest_trade_date_from_files(a_share_dir)
    if from_files:
        return from_files

    raise FileNotFoundError("没有找到行情缓存。请先运行 --steps 01 抓取数据。")


def latest_open_trade_date(pro, target_date: str) -> str:
    target = normalize_date(target_date)
    start = (
        datetime.strptime(target, DATE_FORMAT).date() - timedelta(days=90)
    ).strftime(DATE_FORMAT)
    try:
        calendar = pro.trade_cal(exchange="SSE", start_date=start, end_date=target)
    except Exception:
        return target
    if calendar is None or calendar.empty:
        return target

    open_days = calendar[calendar["is_open"].astype(str) == "1"]
    if open_days.empty:
        return target
    return str(open_days["cal_date"].max())
