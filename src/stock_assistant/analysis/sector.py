from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..data.calendar import resolve_data_date


def analyze_sectors(
    a_share_dir: Path,
    reports_dir: Path,
    requested_date: str | None = None,
    top_n: int = 5,
) -> list[dict]:
    trade_date = resolve_data_date(a_share_dir, requested_date)
    daily, stock_basic = _load_daily_with_basic(a_share_dir, trade_date)
    merged = daily.merge(stock_basic, on="ts_code", how="left")
    merged["sector"] = _build_sector_series(merged)
    merged["pct_chg"] = pd.to_numeric(merged["pct_chg"], errors="coerce").fillna(0)
    merged["amount"] = pd.to_numeric(merged["amount"], errors="coerce").fillna(0)

    total_amount = float(merged["amount"].sum()) or 1.0
    grouped = merged.groupby("sector", dropna=False)
    rows = []
    for sector, frame in grouped:
        stocks = len(frame)
        if stocks < 2:
            continue
        avg_pct = float(frame["pct_chg"].mean())
        up_ratio = float((frame["pct_chg"] > 0).mean())
        amount = float(frame["amount"].sum())
        amount_share = amount / total_amount
        heat_score = avg_pct * 0.5 + up_ratio * 5 + amount_share * 10
        rows.append(
            {
                "trade_date": trade_date,
                "industry": str(sector),
                "stocks": int(stocks),
                "avg_pct_chg": round(avg_pct, 4),
                "up_ratio": round(up_ratio, 4),
                "amount_100m": round(amount / 100000, 2),
                "amount_share": round(amount_share, 4),
                "heat_score": round(float(heat_score), 4),
            }
        )

    sectors = sorted(rows, key=lambda item: item["heat_score"], reverse=True)[:top_n]
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"sectors_{trade_date}.json"
    output_path.write_text(json.dumps(sectors, ensure_ascii=False, indent=2), encoding="utf-8")
    return sectors


def _load_daily_with_basic(a_share_dir: Path, trade_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = pd.read_csv(a_share_dir / f"daily_{trade_date}.csv")
    stock_basic_path = a_share_dir / f"stock_basic_{trade_date}.csv"
    if stock_basic_path.exists():
        stock_basic = pd.read_csv(stock_basic_path)
    else:
        stock_basic = pd.DataFrame(
            {"ts_code": daily["ts_code"], "name": daily["ts_code"], "industry": "未分类"}
        )
    for column in ["ts_code", "name", "industry"]:
        if column not in stock_basic.columns:
            stock_basic[column] = "" if column != "ts_code" else daily["ts_code"]
    return daily, stock_basic[["ts_code", "name", "industry"]]


def _build_sector_series(merged: pd.DataFrame) -> pd.Series:
    industries = merged["industry"].fillna("").astype(str).str.strip()
    useful = industries[(industries != "") & (industries != "未分类")]
    if len(useful) >= max(10, len(merged) * 0.1):
        return industries.replace("", "未分类")
    return merged["ts_code"].astype(str).map(_market_group)


def _market_group(ts_code: str) -> str:
    code = ts_code.split(".", 1)[0]
    suffix = ts_code.split(".")[-1] if "." in ts_code else ""
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith("688"):
        return "科创板"
    if code.startswith(("600", "601", "603", "605")):
        return "沪市主板"
    if code.startswith(("000", "001", "002", "003")):
        return "深市主板"
    if code.startswith(("8", "4")) or suffix == "BJ":
        return "北交所"
    return "其他市场"
