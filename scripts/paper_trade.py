"""模拟盘运行器（只用假钱）：拉最新公开日线 → 算信号 → 更新模拟台账与每日简报。

可重复运行：已记账的日期不会重复记账；漏跑的日期会按顺序补上。
用法：python scripts/paper_trade.py [--no-fetch]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qpl import config, data, paper  # noqa: E402

if __name__ == "__main__":
    if "--no-fetch" not in sys.argv:
        for p in config.PRODUCTS:
            data.update_cache(p, "1d")
    cfg = json.loads((config.PAPER_DIR / "config.json").read_text())
    px = data.load_daily_close()
    done = paper.run(px, cfg, config.PAPER_DIR)
    print(f"本次新记账 {len(done)} 天：{', '.join(done) or '无（已是最新）'}")
