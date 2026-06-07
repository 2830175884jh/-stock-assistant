from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from requests import Session

from ..config import Settings
from .calendar import latest_open_trade_date, normalize_date, previous_day, write_latest_trade_date


INDEX_CODES = ["000001.SH", "399001.SZ", "399006.SZ"]


@dataclass(frozen=True)
class FetchResult:
    trade_date: str
    daily_path: Path
    index_path: Path
    summary_path: Path
    stock_basic_path: Path


def fetch_market_data(settings: Settings, target_date: str | None = None) -> FetchResult:
    if not settings.tushare_token:
        pro = None
    else:
        import tushare as ts

        pro = ts.pro_api(settings.tushare_token)
    desired_date = normalize_date(target_date)
    try:
        if pro is None:
            raise RuntimeError("TUSHARE_TOKEN 未配置，改用 Eastmoney 公共行情兜底。")
        trade_date, daily = _fetch_latest_nonempty_daily(pro, desired_date)
        stock_basic = _fetch_stock_basic(pro, daily, settings.a_share_dir, trade_date)
        index_daily = _fetch_index_daily(pro, trade_date)
        source = "tushare"
    except Exception as exc:
        trade_date, daily, stock_basic, index_daily = _fetch_eastmoney_snapshot(desired_date)
        source = f"eastmoney_fallback: {exc}"
    summary = _build_summary(trade_date, daily, source)

    settings.a_share_dir.mkdir(parents=True, exist_ok=True)
    daily_path = settings.a_share_dir / f"daily_{trade_date}.csv"
    index_path = settings.a_share_dir / f"index_{trade_date}.csv"
    summary_path = settings.a_share_dir / f"summary_{trade_date}.csv"
    stock_basic_path = settings.a_share_dir / f"stock_basic_{trade_date}.csv"

    daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
    index_daily.to_csv(index_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    stock_basic.to_csv(stock_basic_path, index=False, encoding="utf-8-sig")
    write_latest_trade_date(settings.a_share_dir, trade_date)

    return FetchResult(
        trade_date=trade_date,
        daily_path=daily_path,
        index_path=index_path,
        summary_path=summary_path,
        stock_basic_path=stock_basic_path,
    )


def _fetch_latest_nonempty_daily(pro, target_date: str) -> tuple[str, pd.DataFrame]:
    probe_date = target_date
    last_error: Exception | None = None
    for _ in range(10):
        trade_date = latest_open_trade_date(pro, probe_date)
        try:
            daily = pro.daily(trade_date=trade_date)
        except Exception as exc:
            last_error = exc
            daily = pd.DataFrame()

        if daily is not None and not daily.empty:
            return trade_date, _select_columns(
                daily,
                ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "pct_chg", "vol", "amount"],
            )

        probe_date = previous_day(trade_date)

    if last_error:
        raise RuntimeError(f"Tushare daily 接口调用失败：{last_error}") from last_error
    raise RuntimeError("最近 10 个候选交易日都没有拉到日行情数据。")


def _fetch_index_daily(pro, trade_date: str) -> pd.DataFrame:
    frames = []
    for code in INDEX_CODES:
        try:
            frame = pro.index_daily(ts_code=code, trade_date=trade_date)
        except Exception:
            frame = pd.DataFrame()
        if frame is not None and not frame.empty:
            frames.append(frame)
    if len(frames) < len(INDEX_CODES):
        try:
            eastmoney_indices = _eastmoney_get_indices(trade_date)
            if not eastmoney_indices.empty:
                return eastmoney_indices
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=["ts_code", "trade_date", "close", "pct_chg", "amount"])
    return _select_columns(
        pd.concat(frames, ignore_index=True),
        ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "pct_chg", "vol", "amount"],
    )


def _fetch_stock_basic(
    pro,
    daily: pd.DataFrame,
    a_share_dir: Path,
    trade_date: str,
) -> pd.DataFrame:
    try:
        stock_basic = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,name,industry,market,list_status",
        )
    except Exception:
        stock_basic = pd.DataFrame()

    if stock_basic is not None and not stock_basic.empty:
        return _select_columns(stock_basic, ["ts_code", "name", "industry", "market", "list_status"])

    return pd.DataFrame(
        {
            "ts_code": daily["ts_code"],
            "name": daily["ts_code"],
            "industry": "未分类",
            "market": "",
            "list_status": "",
        }
    )


def _fetch_eastmoney_snapshot(target_date: str) -> tuple[str, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = _eastmoney_get_all_stocks()
    if not rows:
        raise RuntimeError("Tushare 不可用，Eastmoney 兜底也未返回行情数据。")

    trade_date = _eastmoney_trade_date(rows, target_date)
    daily_records = []
    basic_records = _eastmoney_basic_records(rows)
    for row in rows:
        code = str(row.get("f12", "")).zfill(6)
        ts_code = _eastmoney_ts_code(code)
        close = _to_float(row.get("f2"))
        pct_chg = _to_float(row.get("f3"))
        pre_close = _to_float(row.get("f18"))
        daily_records.append(
            {
                "ts_code": ts_code,
                "trade_date": trade_date,
                "open": _to_float(row.get("f17")),
                "high": _to_float(row.get("f15")),
                "low": _to_float(row.get("f16")),
                "close": close,
                "pre_close": pre_close,
                "pct_chg": pct_chg,
                "vol": _to_float(row.get("f5")),
                "amount": _to_float(row.get("f6")) / 1000,
            }
        )

    daily = pd.DataFrame(daily_records)
    stock_basic = pd.DataFrame(basic_records)
    index_daily = _eastmoney_get_indices(trade_date)
    return trade_date, daily, stock_basic, index_daily


def _eastmoney_get_all_stocks() -> list[dict]:
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    rows: list[dict] = []
    page = 1
    page_size = 500
    while True:
        params = {
            "pn": page,
            "pz": page_size,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f12,f14,f2,f3,f5,f6,f17,f15,f16,f18,f100,f124",
        }
        data = _eastmoney_get(url, params)
        diff = data.get("data", {}).get("diff") or []
        if not diff:
            break
        rows.extend(diff)
        total = int(data.get("data", {}).get("total") or 0)
        if len(rows) >= total or page >= 80:
            break
        page += 1
    return rows


def _eastmoney_basic_records(rows: list[dict]) -> list[dict]:
    records = []
    for row in rows:
        code = str(row.get("f12", "")).zfill(6)
        ts_code = _eastmoney_ts_code(code)
        records.append(
            {
                "ts_code": ts_code,
                "name": str(row.get("f14") or ts_code),
                "industry": str(row.get("f100") or "未分类"),
                "market": "",
                "list_status": "L",
            }
        )
    return records


def _eastmoney_get_indices(trade_date: str) -> pd.DataFrame:
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    params = {
        "fltt": 2,
        "invt": 2,
        "fields": "f12,f14,f2,f3,f5,f6,f17,f15,f16,f18",
        "secids": "1.000001,0.399001,0.399006",
    }
    rows = _eastmoney_get(url, params).get("data", {}).get("diff") or []
    code_map = {"000001": "000001.SH", "399001": "399001.SZ", "399006": "399006.SZ"}
    records = []
    for row in rows:
        code = str(row.get("f12", ""))
        records.append(
            {
                "ts_code": code_map.get(code, code),
                "trade_date": trade_date,
                "open": _to_float(row.get("f17")),
                "high": _to_float(row.get("f15")),
                "low": _to_float(row.get("f16")),
                "close": _to_float(row.get("f2")),
                "pre_close": _to_float(row.get("f18")),
                "pct_chg": _to_float(row.get("f3")),
                "vol": _to_float(row.get("f5")),
                "amount": _to_float(row.get("f6")) / 1000,
            }
        )
    return pd.DataFrame(records)


def _eastmoney_get(url: str, params: dict) -> dict:
    last_error: Exception | None = None
    for trust_env in (False, True):
        for _ in range(2):
            try:
                with Session() as session:
                    session.trust_env = trust_env
                    response = session.get(
                        url,
                        params=params,
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=30,
                    )
                response.raise_for_status()
                break
            except Exception as exc:
                last_error = exc
        else:
            continue
        break
    else:
        raise RuntimeError(f"Eastmoney 请求失败：{last_error}") from last_error
    data = response.json()
    if data.get("rc") != 0:
        raise RuntimeError(f"Eastmoney 接口返回异常：{data.get('rc')}")
    return data


def _eastmoney_trade_date(rows: list[dict], fallback_date: str) -> str:
    timestamps = [row.get("f124") for row in rows if row.get("f124")]
    if not timestamps:
        return fallback_date
    return datetime.fromtimestamp(max(timestamps)).strftime("%Y%m%d")


def _eastmoney_ts_code(code: str) -> str:
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    return f"{code}.SZ"


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_summary(trade_date: str, daily: pd.DataFrame, source: str) -> pd.DataFrame:
    pct = pd.to_numeric(daily["pct_chg"], errors="coerce").fillna(0)
    amount = pd.to_numeric(daily["amount"], errors="coerce").fillna(0)
    row = {
        "source": source,
        "trade_date": trade_date,
        "stocks": int(len(daily)),
        "up": int((pct > 0).sum()),
        "down": int((pct < 0).sum()),
        "flat": int((pct == 0).sum()),
        "total_amount": float(amount.sum()),
        "limit_up_est": int((pct >= 9.8).sum()),
        "limit_down_est": int((pct <= -9.8).sum()),
    }
    return pd.DataFrame([row])


def _select_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    selected = frame.copy()
    for column in columns:
        if column not in selected.columns:
            selected[column] = None
    return selected[columns]
