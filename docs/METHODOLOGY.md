# 方法说明

## 回测引擎：自己写，不用开源库

选择自写（`qpl/backtest.py`，约 80 行），理由：

1. **透明**：只有日线、两个资产、只做多，核心就是一个逐日循环，非专业人士也能逐行读懂。
2. **时序约定可测试**："t 日收盘定权重 → 只赚 t+1 日收益"写在一处，由 `tests/test_lookahead.py` 直接核对；
   换用 backtrader / vectorbt 等库要先弄清它们各自的成交时点、费用和对齐约定，出错更隐蔽。
3. **依赖少**：只需 numpy、pandas，GitHub Actions 上安装快，免费额度消耗小。

代价：功能少（无限价单、无日内撮合、无做空/杠杆），但本项目也不需要。

## 防止偷看未来

- 策略函数只用 rolling / shift 等向后看的运算；测试逐个变体检查"截断到 t 日计算"与"全量计算"在 t 日的结果完全一致，
  以及"改动 t 日之后的价格"不会改变 t 日及之前的信号和收益。
- 引擎测试用手算公式核对 `收益[t+1] = 权重[t] × 资产收益[t+1]`，并用一个"看到当日上涨才买"的作弊信号确认它拿不到好处。
- 开发脚本只能从 `load_dev_close()` 取数据（在留出期前截断并断言）；留出期脚本只在预注册和最终候选都已提交后才能运行。

## 交易成本取值与出处（2026-11-02 查询）

| 项目 | 取值（每一边） | 依据 |
|---|---|---|
| 手续费 | 0.60% | Coinbase Advanced 入门档 taker 费率（maker 0.40% / taker 0.60%）。小资金市价单按 taker 计。 |
| 滑点 | 0.05% | BTC、ETH 现货买卖价差通常远低于 0.05%；这里额外覆盖"收盘价算信号、稍后才成交"的时间差和小额冲击。 |
| 合计 | **0.65%**，一买一卖约 1.3% | 主设定，偏保守 |
| 敏感性 | 0.10%、0.45% | 0.45% 约等于 Kraken Pro 入门档 taker 0.40% + 滑点；0.10% 接近高交易量用户 |

出处（第三方汇总，各交易所费率会变动且分档，请以登录后的官方费率页为准）：
- [Coinbase vs. Kraken: Fee Structures (BrokerChooser)](https://brokerchooser.com/news/coinbase-vs-kraken-fee-structures-and-trading-features-compared--bbeea493)
- [Kraken vs Coinbase (Coin Bureau, 2026-02 更新)](https://coinbureau.com/analysis/kraken-vs-coinbase)
- [Coinbase vs Kraken 2026 (Freenance)](https://freenance.io/comparisons/coinbase-vs-kraken-2026-comparison/)
- [Kraken 费率说明（官方支持页）](https://support.kraken.com/cn/articles/201893638)

注意：查询时各来源对 Kraken 的入门档费率说法不一（0.25%/0.40% 与 0.16%/0.26% 都有），所以主设定用了更贵的 Coinbase 数字。

## 其他约定

- 夏普按无风险利率 0 计算（持有美元现金在回测中不计利息，这对空仓较多的策略略显不利）。
- 年化按 365 天。缺失日用前值填充（当日收益为 0）。
- 回测在评估区间起点前一日收盘空仓建仓，建仓成本计入第一天，策略与基准一致。
