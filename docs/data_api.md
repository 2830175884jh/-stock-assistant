# 数据接口说明

MVP 默认使用 Tushare Pro：

- `trade_cal`：判断交易日并自动回退。
- `daily`：获取全市场日行情。
- `index_daily`：获取上证指数、深证成指、创业板指行情。
- `stock_basic`：可选获取股票名称。行业字段不作为 MVP 必需依赖。

如果接口权限不足，优先保证 `daily` 可用。`trade_cal`、`index_daily`、`stock_basic` 都允许降级；行业不可用时，热点部分按市场板块分组。
