from __future__ import annotations

import argparse
import sys

from .config import ensure_output_dirs, load_settings


VALID_STEPS = {"01", "02", "03"}


def _parse_steps(raw_steps: str) -> list[str]:
    steps = [_normalize_step(item.strip()) for item in raw_steps.split(",") if item.strip()]
    invalid = [step for step in steps if step not in VALID_STEPS]
    if invalid:
        raise ValueError(f"未知步骤: {', '.join(invalid)}。可选步骤为 01,02,03。")
    return steps or ["01", "02", "03"]


def _normalize_step(step: str) -> str:
    if step in {"1", "2", "3"}:
        return f"0{step}"
    return step


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="股票投资小助手 MVP")
    parser.add_argument(
        "--steps",
        default="01,02,03",
        help="要执行的步骤，逗号分隔。可选: 01,02,03。默认全部执行。",
    )
    parser.add_argument("--doctor", action="store_true", help="检测 Ollama 地址、模型和实际对话，不抓取行情。")
    parser.add_argument("--date", help="目标日期，格式 YYYYMMDD。默认使用今天并自动回退交易日。")
    parser.add_argument("--top-sectors", type=int, default=5, help="输出热门板块数量。")
    parser.add_argument("--top-stocks", type=int, default=3, help="每个板块输出个股数量。")
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        steps = _parse_steps(args.steps)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    settings = load_settings()
    if args.doctor:
        from .llm.client import LLMUnavailable, OllamaClient

        client = OllamaClient(settings)
        print(f"Ollama: {client.base_url}; 模型: {client.model}; 超时: {client.timeout}s")
        try:
            client.check()
            client.chat("请用中文回答：连接成功。")
        except LLMUnavailable as exc:
            print(f"自检失败：{exc}", file=sys.stderr)
            return 1
        print("自检成功：模型存在，/api/chat 返回有效正文。")
        return 0
    ensure_output_dirs(settings)

    market_brief = None
    sectors = None
    stock_picks = None

    try:
        if "01" in steps:
            from .data.fetcher import fetch_market_data

            result = fetch_market_data(settings, args.date)
            print(f"步骤 01 完成：已抓取 {result.trade_date} 行情，输出到 {settings.a_share_dir}")

        if "02" in steps:
            from .analysis.market import build_market_brief
            from .report.builder import write_market_report

            market_brief = build_market_brief(settings.a_share_dir, settings.reports_dir, args.date)
            report_path = write_market_report(settings, market_brief)
            print(f"步骤 02 完成：市场分析已生成 {report_path}")

        if "03" in steps:
            from .analysis.market import build_market_brief
            from .analysis.sector import analyze_sectors
            from .analysis.stock import pick_sector_stocks
            from .report.builder import write_daily_report

            if market_brief is None:
                market_brief = build_market_brief(settings.a_share_dir, settings.reports_dir, args.date)
            sectors = analyze_sectors(
                settings.a_share_dir,
                settings.reports_dir,
                args.date,
                top_n=args.top_sectors,
            )
            stock_picks = pick_sector_stocks(
                settings.a_share_dir,
                settings.reports_dir,
                args.date,
                sectors,
                top_k=args.top_stocks,
            )
            report_path = write_daily_report(settings, market_brief, sectors, stock_picks)
            print(f"步骤 03 完成：综合日报已生成 {report_path}")

    except Exception as exc:
        print(f"运行失败：{exc}", file=sys.stderr)
        return 1

    return 0


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(run(argv))
