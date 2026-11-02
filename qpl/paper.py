"""模拟盘运行器：只用假钱，不连接任何交易账户。

台账（仓库内文件即唯一事实来源）：
- paper/equity.csv：每个已处理的日线一行（收盘价、目标仓位、持仓、现金、权益、基准）
- paper/trades.csv：每笔模拟成交一行，id = 日期|资产
- paper/briefs/YYYY-MM-DD.md：每日简报

幂等：只处理 equity.csv 最后日期之后、已收盘的日线；成交 id 已存在则跳过。
重复运行同一时段不会重复记账；漏跑的日子会在下次运行时按顺序补上。
成交价 = 当日收盘价 ×(1 ± 滑点)；手续费 = 成交额 × 费率。与回测引擎时序一致。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config
from .strategies import VARIANTS, target_weights

TRADE_COLS = ["id", "date", "asset", "side", "qty", "close", "fill_price", "notional", "fee", "cash_after"]


def _read(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else None


def run(px: pd.DataFrame, cfg: dict, out_dir: Path) -> list[str]:
    out_dir = Path(out_dir)
    (out_dir / "briefs").mkdir(parents=True, exist_ok=True)
    trades_p, eq_p = out_dir / "trades.csv", out_dir / "equity.csv"
    assets = list(px.columns)
    fee, slip, band = cfg["fee_rate"], cfg["slippage"], cfg.get("band", config.REBALANCE_BAND)
    init = float(cfg["initial_cash"])
    start = pd.Timestamp(cfg["start_date"])

    eq = _read(eq_p)
    trades = _read(trades_p)
    seen = set(trades["id"]) if trades is not None else set()
    if eq is None:
        cash, units, last = init, {a: 0.0 for a in assets}, None
    else:
        row = eq.iloc[-1]
        cash, units, last = float(row["cash"]), {a: float(row[f"units_{a}"]) for a in assets}, pd.Timestamp(row["date"])

    p0 = px.loc[start]
    done = []
    for d in px.index[(px.index >= start) & ((px.index > last) if last is not None else True)]:
        P = px.loc[d]
        if P.isna().any():
            raise ValueError(f"{d.date()} 缺少收盘价，停止以免记错账")
        tgt = target_weights(cfg["strategy"], px.loc[:d]).iloc[-1]  # 只用 d 日及以前的数据
        equity = cash + sum(units[a] * P[a] for a in assets)
        orders = []
        for a in assets:
            diff = tgt[a] - units[a] * P[a] / equity
            if abs(diff) > band or (tgt[a] == 0 and units[a] > 0):
                orders.append((a, diff * equity))
        new_rows = []
        for a, notional in sorted(orders, key=lambda x: x[1]):  # 先卖后买
            if notional < 0:
                qty = units[a] if tgt[a] == 0 else min(units[a], -notional / P[a])
                fill = P[a] * (1 - slip)
                gross = qty * fill
                f = gross * fee
                cash += gross - f
                units[a] = 0.0 if tgt[a] == 0 else units[a] - qty
                side = "SELL"
            else:
                gross = min(notional, cash / (1 + fee))
                fill = P[a] * (1 + slip)
                qty = gross / fill
                f = gross * fee
                cash -= gross + f
                units[a] += qty
                side = "BUY"
            tid = f"{d:%Y-%m-%d}|{a}"
            if tid not in seen:
                new_rows.append([tid, f"{d:%Y-%m-%d}", a, side, qty, P[a], fill, gross, f, cash])
                seen.add(tid)
        if new_rows:
            pd.DataFrame(new_rows, columns=TRADE_COLS).to_csv(
                trades_p, mode="a", header=not trades_p.exists() or trades_p.stat().st_size == 0, index=False)

        equity = cash + sum(units[a] * P[a] for a in assets)
        k = 1 - (fee + slip)
        rec = {"date": f"{d:%Y-%m-%d}", "strategy": cfg["strategy"]}
        rec.update({f"close_{a}": P[a] for a in assets})
        rec.update({f"target_{a}": tgt[a] for a in assets})
        rec.update({f"units_{a}": units[a] for a in assets})
        rec.update({"cash": cash, "equity": equity,
                    "bench_btc": init * k * P["BTC-USD"] / p0["BTC-USD"],
                    "bench_ew": init * k * 0.5 * sum(P[a] / p0[a] for a in assets)})
        pd.DataFrame([rec]).to_csv(eq_p, mode="a", header=not eq_p.exists() or eq_p.stat().st_size == 0,
                                   index=False)
        _brief(out_dir, cfg, rec, assets, new_rows, init)
        done.append(rec["date"])
    return done


def _brief(out_dir, cfg, rec, assets, rows, init):
    fam, _, params = VARIANTS[cfg["strategy"]]
    lines = [
        f"# 模拟盘日报 {rec['date']}（UTC 日线收盘）",
        "",
        "> 这是用假钱运行的模拟盘，用于检验策略，不构成任何投资建议，也不代表真实交易结果。",
        "",
        f"- 策略：{cfg['strategy']}（{fam}，参数 {json.dumps(params, ensure_ascii=False)}）",
        "- 收盘价：" + "，".join(f"{a} {rec[f'close_{a}']:,.2f}" for a in assets),
        "- 目标仓位：" + "，".join(f"{a} {rec[f'target_{a}']:.0%}" for a in assets) + f"，现金 {1 - sum(rec[f'target_{a}'] for a in assets):.0%}",
        "- 今日模拟成交：" + ("；".join(f"{r[3]} {r[2]} {r[4]:.6f} @ {r[6]:,.2f}（费 {r[8]:.2f}）" for r in rows) or "无"),
        f"- 账户权益：{rec['equity']:,.2f} 美元（起始 {init:,.0f}，累计 {rec['equity'] / init - 1:+.2%}）",
        f"- 对照（同日起扣同样成本）：买入持有 BTC {rec['bench_btc']:,.2f}（{rec['bench_btc'] / init - 1:+.2%}），"
        f"BTC/ETH 等权 {rec['bench_ew']:,.2f}（{rec['bench_ew'] / init - 1:+.2%}）",
        "",
    ]
    (out_dir / "briefs" / f"{rec['date']}.md").write_text("\n".join(lines), encoding="utf-8")
