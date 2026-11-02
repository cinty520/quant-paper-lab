"""开发期评估：样本内 + 滚动前推 + DSR。只读取留出期之前的数据。

输出：reports/dev-results.md、reports/finalist.json、docs/TRIALS.md、paper/config.json
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qpl import config, data  # noqa: E402
from qpl.backtest import BENCHMARKS, buy_and_hold, simulate  # noqa: E402
from qpl.metrics import deflated_sharpe, perf  # noqa: E402
from qpl.report import md_table  # noqa: E402
from qpl.strategies import VARIANTS, target_weights  # noqa: E402

COLS = ["年化收益", "累计收益", "年化波动", "夏普", "最大回撤", "年换手", "平均仓位"]
# 除 15 个预注册变体外的额外试验（含失败/作废的），每一项都计入 DSR 的试验数 N
EXTRA_TRIALS: list[str] = []
NOTES = [
    "开发期评估按预注册方案一次跑完，未修改策略、参数或成本设定。",
    "留出期脚本第一次运行在写 JSON 文件时因 numpy 布尔值无法序列化而报错退出（结论尚未输出）。"
    "修复序列化后重跑一次；计算逻辑与数据未改，结果是确定性的。",
]


def run_all(px, tgts, start, end, cost):
    out = {v: simulate(px, tgts[v], start, end, cost) for v in VARIANTS}
    out.update({b: buy_and_hold(px, w, start, end, cost) for b, w in BENCHMARKS.items()})
    return out


def walk_forward(px, tgts, series, candidates, cost):
    end = px.index.max()
    t0, pieces, log, prev = pd.Timestamp(config.WF_FIRST_TEST), [], [], None
    while t0 <= end:
        t1 = min(t0 + pd.Timedelta(days=config.WF_TEST_DAYS - 1), end)
        tr0, tr1 = t0 - pd.Timedelta(days=config.WF_TRAIN_DAYS), t0 - pd.Timedelta(days=1)
        best = max(candidates, key=lambda v: perf(series[v].loc[tr0:tr1])["夏普"])
        seg = series[best].loc[t0:t1].copy()
        before = t0 - pd.Timedelta(days=1)
        old = tgts[prev].loc[before] if prev else 0.0 * tgts[best].loc[before]
        sw = float((tgts[best].loc[before] - old).abs().sum()) if best != prev else 0.0
        seg.iloc[0, 0] = (1 + seg.iloc[0, 0]) * (1 - sw * cost) - 1  # 切换策略的调仓成本
        seg.iloc[0, 1] += sw
        pieces.append(seg)
        log.append(f"{t0.date()}～{t1.date()}: {best}")
        prev, t0 = best, t1 + pd.Timedelta(days=1)
    return pd.concat(pieces), log


def main():
    px = data.load_dev_close()  # 截断在留出期之前
    dev_end = px.index.max().strftime("%Y-%m-%d")
    tgts = {v: target_weights(v, px) for v in VARIANTS}
    cost = config.COST_RATE

    # 1) 样本内（整个开发期）
    ins = run_all(px, tgts, config.EVAL_START, dev_end, cost)
    is_perf = {k: perf(v) for k, v in ins.items()}
    n_trials = len(VARIANTS) + len(EXTRA_TRIALS)
    srs = [is_perf[v]["夏普"] / config.ANN ** 0.5 for v in VARIANTS]
    for v in VARIANTS:
        is_perf[v].update(deflated_sharpe(ins[v]["ret"], srs, n_trials))
    finalist = max(VARIANTS, key=lambda v: is_perf[v]["夏普"])

    # 2) 成本敏感性（样本内）
    sens = {}
    for label, c in config.COST_SENSITIVITY.items():
        res = run_all(px, tgts, config.EVAL_START, dev_end, c)
        for k, v in res.items():
            sens.setdefault(k, {})[f"夏普@{label}"] = perf(v)["夏普"]

    # 3) 滚动前推
    oos_fixed = run_all(px, tgts, config.WF_FIRST_TEST, dev_end, cost)
    oos_perf = {k: perf(v) for k, v in oos_fixed.items()}
    sel_perf, sel_logs = {}, {}
    groups = {"选择器: 全部15个变体": list(VARIANTS)}
    for fam in dict.fromkeys(f for f, _, _ in VARIANTS.values()):
        groups[f"选择器: {fam}"] = [v for v, (f, _, _) in VARIANTS.items() if f == fam]
    for name, cands in groups.items():
        comp, log = walk_forward(px, tgts, ins, cands, cost)
        sel_perf[name] = perf(comp)
        sel_logs[name] = log

    # ---- 写报告 ----
    fin = is_perf[finalist]
    lines = [
        "# 开发期结果（自动生成，勿手改）",
        "",
        f"数据截止 {dev_end}（留出期之前）。成本主设定每边 {cost:.2%}。夏普无风险利率取 0。",
        "",
        f"## 1. 样本内：{config.EVAL_START} 至 {dev_end}",
        "",
        md_table(is_perf, COLS + ["PSR", "DSR"]),
        "",
        f"DSR 的试验数 N = {n_trials}，多重检验门槛 SR0（年化）= {fin['SR0(年化)']:.2f}：",
        "在 N 个真实夏普为 0 的变体中，最大的样本夏普期望就有这么高。",
        "",
        "## 2. 成本敏感性（样本内夏普）",
        "",
        md_table(sens, list(next(iter(sens.values())).keys())),
        "",
        f"## 3. 滚动前推：{config.WF_FIRST_TEST} 至 {dev_end}",
        "",
        f"训练窗 {config.WF_TRAIN_DAYS} 天，测试窗 {config.WF_TEST_DAYS} 天。选择器在每个训练窗里挑扣费夏普最高的变体，用到下一个测试窗。",
        "",
        "### 3a. 选择器（真正的样本外）",
        "",
        md_table(sel_perf, COLS),
        "",
        "### 3b. 同一时段各固定变体与基准（供对照）",
        "",
        md_table(oos_perf, COLS),
        "",
        "### 3c. 全体选择器每段选中的变体",
        "",
        *[f"- {x}" for x in sel_logs["选择器: 全部15个变体"]],
        "",
        "## 4. 最终候选（按预注册第 7 条机械选出）",
        "",
        f"**{finalist}**：开发期扣费夏普 {fin['夏普']:.2f}，年化 {fin['年化收益']:.1%}，最大回撤 {fin['最大回撤']:.1%}，"
        f"PSR {fin['PSR']:.1%}，DSR {fin['DSR']:.1%}（N={n_trials}）。",
        "",
    ]
    (config.REPORTS_DIR).mkdir(exist_ok=True)
    (config.REPORTS_DIR / "dev-results.md").write_text("\n".join(lines), encoding="utf-8")

    (config.REPORTS_DIR / "finalist.json").write_text(json.dumps({
        "strategy": finalist, "rule": "开发期主设定成本下扣费夏普最高（预注册第 7 条）",
        "dev_sharpe": fin["夏普"], "dev_psr": fin["PSR"], "dev_dsr": fin["DSR"], "n_trials": n_trials,
        "dev_end": dev_end}, ensure_ascii=False, indent=2) + "\n")
    config.PAPER_DIR.mkdir(exist_ok=True)
    (config.PAPER_DIR / "config.json").write_text(json.dumps({
        "strategy": finalist, "start_date": "2026-11-01", "initial_cash": 10000,
        "fee_rate": config.FEE_RATE, "slippage": config.SLIPPAGE, "band": config.REBALANCE_BAND,
        "note": "模拟盘，只用假钱"}, ensure_ascii=False, indent=2) + "\n")

    bh = is_perf["买入持有BTC"]["夏普"]
    trials = {}
    for v, (fam, _, params) in VARIANTS.items():
        m = is_perf[v]
        verdict = "最终候选" if v == finalist else "未入选"
        verdict += "；夏普高于买入持有BTC" if m["夏普"] > bh else "；夏普不如买入持有BTC"
        trials[v] = {"族": fam, "参数": json.dumps(params, ensure_ascii=False), "夏普": m["夏普"],
                     "年化收益": m["年化收益"], "最大回撤": m["最大回撤"], "年换手": m["年换手"],
                     "DSR": m["DSR"], "结果": verdict}
    for i, t in enumerate(EXTRA_TRIALS, 1):
        trials[f"额外-{i}"] = {"结果": t}
    tl = [
        "# 试验记录",
        "",
        "所有试过的变体都在这里，包括失败的。表格由 `scripts/run_dev.py` 生成（开发期样本内、主设定成本）。",
        f"试验总数 N = {n_trials}，用于 DSR 多重检验校正。",
        "",
        md_table(trials, ["族", "参数", "夏普", "年化收益", "最大回撤", "年换手", "DSR", "结果"], key="ID"),
        "",
        f"对照：买入持有BTC 夏普 {bh:.2f}；BTC/ETH等权买入持有 夏普 {is_perf['BTC/ETH等权买入持有']['夏普']:.2f}。",
        "",
        "## 变更与问题记录",
        "",
        *[f"- {n}" for n in NOTES],
        "",
    ]
    (config.ROOT / "docs" / "TRIALS.md").write_text("\n".join(tl), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
