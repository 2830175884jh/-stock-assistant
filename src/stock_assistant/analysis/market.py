from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..data.calendar import resolve_data_date


def build_market_brief(
    a_share_dir: Path,
    reports_dir: Path,
    requested_date: str | None = None,
) -> dict:
    trade_date = resolve_data_date(a_share_dir, requested_date)
    daily = pd.read_csv(a_share_dir / f"daily_{trade_date}.csv")
    summary = pd.read_csv(a_share_dir / f"summary_{trade_date}.csv").iloc[0].to_dict()
    index_daily = _read_optional_csv(a_share_dir / f"index_{trade_date}.csv")

    pct = pd.to_numeric(daily["pct_chg"], errors="coerce").fillna(0)
    amount = pd.to_numeric(daily["amount"], errors="coerce").fillna(0)
    up_ratio = float((pct > 0).mean()) if len(pct) else 0.0
    avg_pct_chg = float(pct.mean()) if len(pct) else 0.0
    index_avg_pct = _safe_mean(index_daily, "pct_chg")

    brief = {
        "trade_date": trade_date,
        "market_temperature": classify_temperature(up_ratio, avg_pct_chg, index_avg_pct),
        "stocks": int(summary.get("stocks", len(daily))),
        "up": int(summary.get("up", 0)),
        "down": int(summary.get("down", 0)),
        "flat": int(summary.get("flat", 0)),
        "up_ratio": round(up_ratio, 4),
        "avg_pct_chg": round(avg_pct_chg, 4),
        "median_pct_chg": round(float(pct.median()) if len(pct) else 0.0, 4),
        "index_avg_pct": round(index_avg_pct, 4),
        "amount_100m": round(float(amount.sum()) / 100000, 2),
        "limit_up_est": int(summary.get("limit_up_est", 0)),
        "limit_down_est": int(summary.get("limit_down_est", 0)),
        "distribution": build_distribution(pct),
        "indices": build_indices(index_daily),
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"market_brief_{trade_date}.json"
    output_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    return brief


def classify_temperature(up_ratio: float, avg_pct_chg: float, index_avg_pct: float) -> str:
    if up_ratio >= 0.6 and (avg_pct_chg >= 0.4 or index_avg_pct >= 0.4):
        return "偏强"
    if up_ratio <= 0.4 or avg_pct_chg <= -0.5 or index_avg_pct <= -0.5:
        return "偏弱"
    return "中性"


def build_distribution(pct: pd.Series) -> dict[str, int]:
    return {
        "大涨_大于5": int((pct >= 5).sum()),
        "中涨_2到5": int(((pct >= 2) & (pct < 5)).sum()),
        "小涨_0到2": int(((pct > 0) & (pct < 2)).sum()),
        "平盘": int((pct == 0).sum()),
        "小跌_0到-2": int(((pct < 0) & (pct > -2)).sum()),
        "中跌_-2到-5": int(((pct <= -2) & (pct > -5)).sum()),
        "大跌_小于-5": int((pct <= -5).sum()),
    }


def build_indices(index_daily: pd.DataFrame) -> list[dict]:
    names = {
        "000001.SH": "上证指数",
        "399001.SZ": "深证成指",
        "399006.SZ": "创业板指",
    }
    rows = []
    for _, row in index_daily.iterrows():
        code = str(row.get("ts_code", ""))
        rows.append(
            {
                "ts_code": code,
                "name": names.get(code, code),
                "close": _round_number(row.get("close")),
                "pct_chg": _round_number(row.get("pct_chg")),
            }
        )
    return rows


def _read_optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _safe_mean(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).mean())


def _round_number(value) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0

