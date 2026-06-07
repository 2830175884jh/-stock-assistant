from __future__ import annotations

import json


SYSTEM_PROMPT = (
    "你是一个谨慎的 A 股市场分析助手。只能根据用户提供的数据做解释，"
    "不得编造未提供的行情、资金、政策、新闻或公司基本面。"
)


def build_market_prompt(brief: dict) -> str:
    return f"""
请根据下面的市场结构化数据，生成一份中文市场日报。

要求：
1. 使用 Markdown。
2. 必须包含：市场综述、指数表现、情绪特征、次日关注。
3. 不要给出确定性买卖指令。
4. 不要编造未提供的数据。
5. 语言面向普通投资者，简洁清楚。

市场数据：
{json.dumps(brief, ensure_ascii=False, indent=2)}
""".strip()


def build_daily_prompt(brief: dict, sectors: list[dict], picks: list[dict]) -> str:
    return f"""
请根据下面的数据，生成一份中文 A 股投资观察日报。

要求：
1. 使用 Markdown。
2. 必须包含：市场概览、热门板块、个股观察、风险提示。
3. 个股只能称为“观察清单”，不能称为买入建议。
4. 不要编造新闻、政策、资金流或未提供的公司信息。
5. 如果数据偏弱，要明确提示控制仓位和观望。

市场数据：
{json.dumps(brief, ensure_ascii=False, indent=2)}

热门板块：
{json.dumps(sectors, ensure_ascii=False, indent=2)}

个股观察：
{json.dumps(picks, ensure_ascii=False, indent=2)}
""".strip()

