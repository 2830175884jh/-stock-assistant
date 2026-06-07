# 股票投资小助手

一个本地可运行的 A 股投资辅助工具。它会拉取最近交易日行情，生成市场情绪、热门板块和个股观察清单，并用本地 Ollama 模型生成中文复盘报告。

本项目是 Vibe Coding 2-3 小时 MVP 作业版本，只做学习演示，不做实盘交易。

## 功能

- 自动识别最近交易日并拉取 A 股日行情。
- 生成市场温度、涨跌家数、成交额、指数表现等摘要。
- 行业字段可用时按行业计算热门板块；不可用时按市场板块生成热点分组。
- 在热点分组内输出个股观察清单和风险等级。
- 使用本地 Ollama 模型 `qwen3:4b` 生成中文分析；Ollama 不可用时降级为规则版报告。

## 环境要求

- Python 3.10+
- Tushare Pro Token
- 可选：已启动 Ollama，并已存在模型 `qwen3:4b`

检查本地模型：

```powershell
ollama list
```

应能看到：

```text
qwen3:4b
```

## 安装

```powershell
cd weektemp\stock-assistant
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## 配置

复制配置模板：

```powershell
copy .env.example .env
```

编辑 `.env`：

```ini
TUSHARE_TOKEN=你的TushareToken
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT=60
```

说明：

- 需要配置的 API Key/Token 是 `TUSHARE_TOKEN`。
- Ollama 本地模型不需要 API Key。
- 如果 Ollama 未启动，项目仍会生成规则版 Markdown 报告。
- `qwen3:4b` 响应较快，默认等待 60 秒。

## 运行

一键运行全部步骤：

```powershell
python -m stock_assistant --steps "01,02,03"
```

指定日期：

```powershell
python -m stock_assistant --date 20260605 --steps "01,02,03"
```

单步运行：

```powershell
python scripts\01_fetch.py
python scripts\02_analyze.py
python scripts\03_recommend.py
```

## 输出

行情缓存：

```text
data/a_share_out/
├── daily_{date}.csv
├── index_{date}.csv
├── stock_basic_{date}.csv
├── summary_{date}.csv
└── _latest_trade_date.txt
```

报告：

```text
data/reports/
├── market_brief_{date}.json
├── market_analysis_{date}.md
├── sectors_{date}.json
├── stock_picks_{date}.json
└── daily_report_{date}.md
```

## 项目结构

```text
stock-assistant/
├── src/stock_assistant/
│   ├── cli.py              # 命令行编排
│   ├── config.py           # .env 和路径配置
│   ├── data/               # 交易日与 Tushare 抓数
│   ├── analysis/           # 市场、板块、个股规则分析
│   ├── llm/                # Ollama 客户端与 Prompt
│   └── report/             # Markdown 报告生成
├── scripts/                # 单步运行入口
├── tests/                  # 最小测试
├── docs/                   # 数据接口、术语和投资逻辑说明
├── requirements.txt
└── .env.example
```

## 测试

```powershell
pytest
```

## 常见问题

### 提示 `TUSHARE_TOKEN 未配置`

复制 `.env.example` 为 `.env`，并填写 Tushare 个人中心里的 Token。

### Ollama 已启动但报告仍降级

确认地址和模型名：

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
ollama list
```

`.env` 中的模型名必须写成 `qwen3:4b`。

### 当天没有数据

非交易日或收盘前数据为空时，程序会自动向前回退最近可用交易日。

## 免责声明

本工具仅供学习与研究，不构成任何投资建议。股市有风险，投资需谨慎。历史表现不代表未来收益。
