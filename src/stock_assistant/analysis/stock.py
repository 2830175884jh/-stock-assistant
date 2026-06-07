from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..data.calendar import resolve_data_date
from .sector import _load_daily_with_basic


def pick_sector_stocks(
    a_share_dir: Path,
    reports_dir: Path,
    requested_date: str | None,
    sectors: list[dict],
    top_k: int = 3,
) -> list[dict]:
    trade_date = resolve_data_date(a_share_dir, requested_date)
    daily, stock_basic = _load_daily_with_basic(a_share_dir, trade_date)
    merged = daily.merge(stock_basic, on="ts_code", how="left")
    merged["name"] = merged["name"].fillna(merged["ts_code"])
    from .sector import _build_sector_series

    merged["sector"] = _build_sector_series(merged)
    for column in ["pct_chg", "amount", "vol", "high", "low", "close"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0)

    picked: list[dict] = []
    for sector in sectors:
        industry = sector["industry"]
        frame = merged[merged["sector"] == industry].copy()
        if frame.empty:
            continue
        frame = frame[~frame["name"].astype(str).str.contains("ST", case=False, na=False)]
        if frame.empty:
            continue
        frame["score"] = _score_frame(frame)
        frame = frame.sort_values("score", ascending=False).head(top_k)
        for _, row in frame.iterrows():
            picked.append(
                {
                    "trade_date": trade_date,
                    "industry": industry,
                    "ts_code": str(row["ts_code"]),
                    "name": str(row["name"]),
                    "pct_chg": round(float(row["pct_chg"]), 4),
                    "amount_100m": round(float(row["amount"]) / 100000, 2),
                    "score": round(float(row["score"]), 2),
                    "tags": _build_tags(row),
                    "risk_level": _risk_level(row),
                }
            )

    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"stock_picks_{trade_date}.json"
    output_path.write_text(json.dumps(picked, ensure_ascii=False, indent=2), encoding="utf-8")
    return picked


def _score_frame(frame: pd.DataFrame) -> pd.Series:
    pct_score = ((frame["pct_chg"] + 10) / 20 * 100).clip(0, 100)
    amount_score = frame["amount"].rank(pct=True) * 100
    vol_score = frame["vol"].rank(pct=True) * 100
    high_low_range = (frame["high"] - frame["low"]).replace(0, 1)
    close_position = ((frame["close"] - frame["low"]) / high_low_range * 100).clip(0, 100)
    return pct_score * 0.35 + amount_score * 0.3 + vol_score * 0.15 + close_position * 0.2


def _build_tags(row: pd.Series) -> list[str]:
    tags: list[str] = []
    pct = float(row.get("pct_chg", 0))
    amount = float(row.get("amount", 0))
    if pct >= 5:
        tags.append("强势上涨")
    elif pct > 0:
        tags.append("红盘")
    if amount >= 500000:
        tags.append("成交活跃")
    high = float(row.get("high", 0))
    low = float(row.get("low", 0))
    close = float(row.get("close", 0))
    if high > low and close >= low + (high - low) * 0.7:
        tags.append("收盘靠近高位")
    if pct >= 9.5:
        tags.append("涨停附近")
    return tags or ["观察"]


def _risk_level(row: pd.Series) -> str:
    pct = float(row.get("pct_chg", 0))
    amount = float(row.get("amount", 0))
    if pct >= 9.5 or pct <= -9.5:
        return "高"
    if pct >= 6 or pct <= -5 or amount < 20000:
        return "中"
    return "低"
