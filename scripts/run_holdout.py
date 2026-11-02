"""留出期评估：只运行一次。要求预注册与最终候选都已提交，且之前没有运行过。"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qpl import config, data  # noqa: E402
from qpl.backtest import BENCHMARKS, buy_and_hold, simulate  # noqa: E402
from qpl.metrics import perf  # noqa: E402
from qpl.report import md_table  # noqa: E402
from qpl.strategies import VARIANTS, target_weights  # noqa: E402

COLS = ["年化收益", "累计收益", "年化波动", "夏普", "最大回撤", "年换手", "平均仓位"]
OUT_JSON = config.REPORTS_DIR / "holdout-results.json"


def committed(path: str) -> bool:
    log = subprocess.run(["git", "log", "--format=%H", "--", path], cwd=config.ROOT, capture_output=True, text=True)
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path], cwd=config.ROOT)
    return bool(log.stdout.strip()) and clean.returncode == 0


def main():
    for p in ["docs/PREREGISTRATION.md", "reports/finalist.json"]:
        if not committed(p):
            sys.exit(f"拒绝运行：{p} 尚未提交或有未提交改动")
    if OUT_JSON.exists() and "--force" not in sys.argv:
        sys.exit("拒绝运行：留出期已经评估过一次。若确需重跑，在 docs/TRIALS.md 写明原因后加 --force")

    finalist = json.loads((config.REPORTS_DIR / "finalist.json").read_text())["strategy"]
    px = data.load_daily_close(end=config.HOLDOUT_END)
    s, e = config.HOLDOUT_START, config.HOLDOUT_END
    results = {}
    for label, c in config.COST_SENSITIVITY.items():
        res = {v: perf(simulate(px, target_weights(v, px), s, e, c)) for v in VARIANTS}
        res.update({b: perf(buy_and_hold(px, w, s, e, c)) for b, w in BENCHMARKS.items()})
        results[label] = res
    main_res = results["主设定(0.65%)"]
    f = main_res[finalist]
    beats = {b: bool(f["夏普"] > main_res[b]["夏普"] and f["累计收益"] > main_res[b]["累计收益"]) for b in BENCHMARKS}
    edge = bool(all(beats.values()))

    ordered = {f"★ {finalist}（最终候选）": f, **{b: main_res[b] for b in BENCHMARKS},
               **{v: main_res[v] for v in VARIANTS if v != finalist}}
    sens = {k: {f"累计收益@{lbl}": results[lbl][k]["累计收益"] for lbl in results} for k in [finalist, *BENCHMARKS]}
    lines = [
        "# 留出期结果（自动生成，只运行一次）",
        "",
        f"区间 {s} 至 {e}（{f['天数']} 天），所有策略和基准都在 {s} 前一日收盘从空仓建仓。成本主设定每边 {config.COST_RATE:.2%}。",
        "",
        "## 判定（按预注册第 8 条）",
        "",
        *[f"- 最终候选 {finalist} 对 {b}：夏普 {f['夏普']:.2f} vs {main_res[b]['夏普']:.2f}，"
          f"累计收益 {f['累计收益']:.1%} vs {main_res[b]['累计收益']:.1%} → {'领先' if ok else '未领先'}"
          for b, ok in beats.items()],
        f"- 结论：**{'留出期领先两个基准' if edge else '没有发现优势'}**",
        "",
        "## 全部结果（主设定成本）",
        "",
        "其余 14 个变体仅为透明起见列出，不能用来改写结论。",
        "",
        md_table(ordered, COLS),
        "",
        "## 成本敏感性（累计收益）",
        "",
        md_table(sens, list(next(iter(sens.values())).keys())),
        "",
    ]
    (config.REPORTS_DIR / "holdout-results.md").write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps({"finalist": finalist, "beats": beats, "edge": edge, "results": results},
                                   ensure_ascii=False, indent=2, default=float) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
