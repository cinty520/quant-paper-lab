# quant-paper-lab：加密货币模拟盘实验

用 BTC/ETH 现货的公开历史行情检验几类有公开研究支撑的简单交易规则，并用**假钱**跑模拟盘。

> **只用假钱。** 本项目只读取 Coinbase 公开行情接口，不注册交易所账号、不使用任何 API 密钥、不调用任何下单或账户接口。
> 文档和结果都不是投资建议，也不代表照做能赚钱。

## 结论（详见 [`reports/backtest-report.md`](reports/backtest-report.md)）

**没有找到能证明"持续赚钱"的证据。** 预注册规则选出的 MA-50（50 日均线趋势）在最近 12 个月的留出期扣费后 +10.8%，
买入持有 BTC −29.8%、BTC/ETH 等权 −35.8%；但多重检验校正后统计证据不足（DSR 85.8% < 95%），
而且这次领先主要来自下跌年份里一半时间空仓。15 个变体中有 13 个在留出期亏钱，在开发期的样本外检验里，
"每次挑过去最好的变体"这种做法也不如买入持有。

## 目录

| 路径 | 内容 |
|---|---|
| `qpl/data.py` | 抓取 Coinbase 公开日线/小时线，增量缓存到 `data/coinbase/`，来源与抓取时间记录在 `meta.json` |
| `qpl/backtest.py` | 自写的日线回测引擎（为什么自写见 `docs/METHODOLOGY.md`） |
| `qpl/strategies.py` | 15 个预注册变体 |
| `qpl/metrics.py` | 年化收益、夏普、最大回撤、换手率、Deflated Sharpe Ratio |
| `qpl/paper.py` | 模拟盘台账（幂等：重复运行不重复记账，漏跑自动补） |
| `docs/PREREGISTRATION.md` | 预注册（在任何样本外评估前提交） |
| `docs/TRIALS.md` | 全部试验记录，含失败的 |
| `docs/METHODOLOGY.md` | 引擎选择、成本取值与出处 |
| `reports/` | 开发期结果、留出期结果、回测报告 |
| `paper/` | 模拟盘：`equity.csv`（每日权益）、`trades.csv`（模拟成交）、`briefs/`（每日简报）、`config.json` |
| `.github/workflows/paper-trade.yml` | 每天 UTC 00:37 自动跑模拟盘并提交台账 |

## 本地运行

```bash
pip install -r requirements.txt
```

```bash
python -m pytest -q
```

```bash
python scripts/fetch_data.py
```

```bash
python scripts/paper_trade.py
```

`scripts/run_dev.py` 重算开发期结果；`scripts/run_holdout.py` 是一次性的留出期评估，已经运行过，再次运行会被拒绝。

## 让模拟盘每天自动运行

定时工作流只在默认分支 `main` 上按时触发。把工作分支合并进 `main` 后即自动生效：

1. 打开 <https://github.com/cinty520/quant-paper-lab/compare/main...claude/paper-trading-v1>，点 **Create pull request**，再点 **Merge pull request**。
2. 想立刻试跑：仓库页面 → **Actions** → **paper-trade** → **Run workflow**。
3. 如果"提交台账"这一步报 403：**Settings → Actions → General → Workflow permissions** 选 **Read and write permissions** 后保存。

额度：每次约 1 分钟，每月约 30 分钟。公开仓库不限分钟数；私有仓库的免费额度是每月 2000 分钟，绰绰有余。
GitHub 的定时任务偶尔会延迟或跳过，运行器下次会把漏掉的日子按顺序补记。
