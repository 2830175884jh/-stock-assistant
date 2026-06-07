from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..config import Settings
from ..llm.client import LLMUnavailable, OllamaClient
from ..llm.prompts import SYSTEM_PROMPT, build_daily_prompt, build_market_prompt


DISCLAIMER = (
    "免责声明：本工具仅供学习与研究，不构成任何投资建议。\n"
    "股市有风险，投资需谨慎。历史表现不代表未来收益。"
)


def write_market_report(settings: Settings, brief: dict) -> Path:
    prompt = build_market_prompt(brief)
    content = _rule_market_report(brief)
    ai_text, note = _generate_ai_text(settings, prompt)
    if ai_text:
        content = f"{content.rstrip()}\n\n## AI 解读\n\n{ai_text.strip()}\n"
    output = _append_footer(content, note)
    path = settings.reports_dir / f"market_analysis_{brief['trade_date']}.md"
    path.write_text(output, encoding="utf-8")
    return path


def write_daily_report(
    settings: Settings,
    brief: dict,
    sectors: list[dict],
    picks: list[dict],
) -> Path:
    prompt = build_daily_prompt(brief, sectors, picks)
    content = _rule_daily_report(brief, sectors, picks)
    ai_text, note = _generate_ai_text(settings, prompt)
    if ai_text:
        content = f"{content.rstrip()}\n\n## AI 复盘解读\n\n{ai_text.strip()}\n"
    output = _append_footer(content, note)
    path = settings.reports_dir / f"daily_report_{brief['trade_date']}.md"
    path.write_text(output, encoding="utf-8")
    return path


def _generate_ai_text(settings: Settings, prompt: str) -> tuple[str | None, str | None]:
    client = OllamaClient(settings)
    if not client.is_available():
        return None, "LLM 降级：未连接到本地 Ollama，仅保留规则版报告。"
    try:
        guard = (
            f"{prompt}\n\n"
            "请只输出 3-5 条定性文字解读，不要输出表格。"
            "不要输出任何阿拉伯数字、百分号、股票代码或股票名称；关键数据已由规则报告给出。"
        )
        text = client.chat(guard, SYSTEM_PROMPT)
        if not _is_valid_ai_text(text):
            return None, "LLM 降级：模型输出未通过金融报告校验，仅保留规则版报告。"
        return text, None
    except LLMUnavailable as exc:
        return None, f"LLM 降级：{exc}"


def _is_valid_ai_text(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 20:
        return False
    off_topic_markers = [
        "find /",
        "```bash",
        "linux",
        "directory",
        "recursively",
        "enumerate all files",
    ]
    lower = stripped.lower()
    if any(marker in lower for marker in off_topic_markers):
        return False
    finance_keywords = ["市场", "板块", "指数", "风险", "成交", "上涨", "下跌", "涨幅", "观察", "仓位"]
    if any(char.isdigit() for char in stripped) or "%" in stripped:
        return False
    return sum(1 for keyword in finance_keywords if keyword in stripped) >= 2


def _rule_market_report(brief: dict) -> str:
    indices = brief.get("indices", [])
    index_lines = [
        f"- {item.get('name', item.get('ts_code'))}: {item.get('pct_chg', 0):.2f}%"
        for item in indices
    ] or ["- 指数数据缺失，无法展开指数表现。"]
    return f"""# 市场分析日报（{brief['trade_date']}）

## 市场综述

市场温度：{brief['market_temperature']}。全市场 {brief['stocks']} 只股票中，上涨 {brief['up']} 只，下跌 {brief['down']} 只，上涨比例 {brief['up_ratio']:.2%}，平均涨跌幅 {brief['avg_pct_chg']:.2f}%。

## 指数表现

{chr(10).join(index_lines)}

## 情绪特征

- 成交额约 {brief['amount_100m']:.2f} 亿元。
- 估算涨停 {brief['limit_up_est']} 只，估算跌停 {brief['limit_down_est']} 只。
- 涨跌分布：{brief.get('distribution', {})}

## 次日关注

关注上涨家数能否继续扩大、成交额是否配合放大，以及强势板块是否出现分化。若市场温度偏弱，优先控制仓位和观察风险释放。
"""


def _rule_daily_report(brief: dict, sectors: list[dict], picks: list[dict]) -> str:
    sector_lines = [
        (
            f"- {item['industry']}: 热度 {item['heat_score']:.2f}，"
            f"平均涨跌幅 {item['avg_pct_chg']:.2f}%，上涨比例 {item['up_ratio']:.2%}"
        )
        for item in sectors
    ] or ["- 暂无可用板块数据。"]

    picks_by_sector: dict[str, list[dict]] = defaultdict(list)
    for item in picks:
        picks_by_sector[item["industry"]].append(item)

    pick_sections = []
    for sector in sectors:
        industry = sector["industry"]
        rows = picks_by_sector.get(industry, [])
        if not rows:
            continue
        lines = [
            (
                f"- {row['name']}（{row['ts_code']}）：评分 {row['score']:.2f}，"
                f"涨跌幅 {row['pct_chg']:.2f}%，风险等级 {row['risk_level']}，"
                f"标签：{', '.join(row['tags'])}"
            )
            for row in rows
        ]
        pick_sections.append(f"### {industry}\n\n" + "\n".join(lines))

    pick_text = "\n\n".join(pick_sections) or "暂无个股观察清单。"
    return f"""# A 股投资观察日报（{brief['trade_date']}）

## 市场概览

市场温度：{brief['market_temperature']}。上涨比例 {brief['up_ratio']:.2%}，平均涨跌幅 {brief['avg_pct_chg']:.2f}%，成交额约 {brief['amount_100m']:.2f} 亿元。

## 热门板块

{chr(10).join(sector_lines)}

## 个股观察清单

{pick_text}

## 风险提示

以上清单来自当日行情规则评分，只适合作为复盘和观察入口。高涨幅、高波动或涨停附近个股需要重点留意追高风险。
"""


def _append_footer(content: str, note: str | None) -> str:
    parts = [content.strip()]
    if note:
        parts.append(f"> {note}")
    parts.append(DISCLAIMER)
    return "\n\n---\n\n".join(parts) + "\n"
