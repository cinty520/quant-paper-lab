"""全局设定。改动这些数值等于改动预注册内容，必须在 docs/TRIALS.md 记录。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "coinbase"
PAPER_DIR = ROOT / "paper"
REPORTS_DIR = ROOT / "reports"

# 只读公开行情接口，不需要也不使用任何密钥
COINBASE_API = "https://api.exchange.coinbase.com"
PRODUCTS = ["BTC-USD", "ETH-USD"]

# 时间划分（UTC 日线，日期 = K 线开盘日）
EVAL_START = "2017-01-01"      # 回测评估起点（之前的数据只用于指标预热）
HOLDOUT_START = "2025-11-01"   # 留出期起点（含）
HOLDOUT_END = "2026-10-31"     # 留出期终点（含）
WF_TRAIN_DAYS = 1095           # 滚动前推：训练窗 3 年
WF_TEST_DAYS = 182             # 测试窗约 6 个月
WF_FIRST_TEST = "2020-01-01"

# 交易成本（每一边，按成交额比例），出处见 docs/METHODOLOGY.md
FEE_RATE = 0.0060   # Coinbase Advanced 入门档 taker 费率
SLIPPAGE = 0.0005   # 5 个基点：价差 + 市价单冲击 + 收盘到成交的时间差
COST_RATE = FEE_RATE + SLIPPAGE
COST_SENSITIVITY = {"低成本(0.10%)": 0.0010, "中成本(0.45%)": 0.0045, "主设定(0.65%)": COST_RATE}

REBALANCE_BAND = 0.02  # 单个资产目标权重与当前权重差 ≤2% 时不调仓（减少无谓换手）
ANN = 365              # 加密货币全年交易
