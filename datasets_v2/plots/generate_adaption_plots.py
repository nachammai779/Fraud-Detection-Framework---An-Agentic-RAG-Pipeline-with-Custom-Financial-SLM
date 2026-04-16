"""
Generate Adaption Labs quality metric plots.
Shows quality progression, percentile rankings, and per-metric breakdowns.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "datasets_v2"
PLOTS = DATA / "plots"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
COLORS = {"remittance": "#2196F3", "gig_worker": "#FF9800", "unbanked": "#4CAF50", "itin": "#9C27B0"}
LABELS = {"remittance": "Remittance", "gig_worker": "Gig Worker", "unbanked": "Unbanked", "itin": "ITIN"}

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#FAFAFA",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def load_evals():
    evals = {}
    for stage in ["expanded_world", "persona_verification"]:
        evals[stage] = {}
        for arch in ARCHETYPES:
            path = DATA / arch / stage / "evaluation.json"
            if path.exists():
                evals[stage][arch] = json.loads(path.read_text(encoding="utf-8"))
    return evals


# ── Plot 8: Quality Score Before/After — Grouped Bar ────────────────────────

def plot_quality_scores(evals):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax_idx, (stage, title) in enumerate([
        ("expanded_world", "Expand-World (Persona → Schema)"),
        ("persona_verification", "Persona Verification (Coherence Scoring)")
    ]):
        ax = axes[ax_idx]
        x = np.arange(len(ARCHETYPES))
        width = 0.35

        befores = []
        afters = []
        for arch in ARCHETYPES:
            ev = evals[stage].get(arch, {})
            q = ev.get("quality", {})
            befores.append(q.get("score_before") or 0)
            afters.append(q.get("score_after") or 0)

        bars_b = ax.bar(x - width / 2, befores, width, label="Before", color="#BDBDBD", alpha=0.8)
        bars_a = ax.bar(x + width / 2, afters, width, label="After",
                        color=[COLORS[a] for a in ARCHETYPES], alpha=0.85)

        for bar, val in zip(bars_b, befores):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, val + 0.15,
                        f"{val:.1f}", ha="center", fontsize=9, color="gray")
        for bar, val in zip(bars_a, afters):
            ax.text(bar.get_x() + bar.get_width() / 2, val + 0.15,
                    f"{val:.1f}", ha="center", fontsize=9, fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels([LABELS[a] for a in ARCHETYPES])
        ax.set_ylabel("Adaption Quality Score")
        ax.set_ylim(0, 12)
        ax.set_title(title)
        ax.legend()

        # Grade labels
        for i, arch in enumerate(ARCHETYPES):
            ev = evals[stage].get(arch, {})
            q = ev.get("quality", {})
            gb = q.get("grade_before", "?")
            ga = q.get("grade_after", "?")
            ax.text(i, -0.8, f"{gb or '?'} → {ga}", ha="center", fontsize=9,
                    fontweight="bold", color="#333")

    fig.suptitle("Adaption Labs Quality Scores: Before vs After", fontsize=14)
    fig.tight_layout()
    fig.savefig(PLOTS / "08_adaption_quality_scores.png", dpi=150)
    plt.close()
    print("  08_adaption_quality_scores.png")


# ── Plot 9: Percentile Ranking Breakdown ────────────────────────────────────

def plot_percentile_breakdown(evals):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax_idx, (stage, title) in enumerate([
        ("expanded_world", "Expand-World"),
        ("persona_verification", "Persona Verification")
    ]):
        ax = axes[ax_idx]
        x = np.arange(len(ARCHETYPES))
        width = 0.25

        overall = []
        message = []
        completion = []
        for arch in ARCHETYPES:
            ev = evals[stage].get(arch, {})
            raw = ev.get("raw_results", {}).get("metrics", {})
            qa = raw.get("quality_percentile_after", {})
            overall.append(qa.get("percentile_score", 0))
            message.append(qa.get("message_quality_percentile", 0))
            completion.append(qa.get("completion_quality_percentile", 0))

        ax.bar(x - width, overall, width, label="Overall Percentile", color="#1976D2", alpha=0.85)
        ax.bar(x, message, width, label="Message Quality %ile", color="#43A047", alpha=0.85)
        ax.bar(x + width, completion, width, label="Completion Quality %ile", color="#FB8C00", alpha=0.85)

        for i in range(len(ARCHETYPES)):
            ax.text(i - width, overall[i] + 1.5, f"{overall[i]:.0f}", ha="center", fontsize=8)
            ax.text(i, message[i] + 1.5, f"{message[i]:.0f}", ha="center", fontsize=8)
            ax.text(i + width, completion[i] + 1.5, f"{completion[i]:.0f}", ha="center", fontsize=8)

        ax.set_xticks(x)
        ax.set_xticklabels([LABELS[a] for a in ARCHETYPES])
        ax.set_ylabel("Percentile")
        ax.set_ylim(0, 100)
        ax.set_title(title)
        ax.legend(fontsize=9)

    fig.suptitle("Adaption Labs Percentile Rankings (vs Reference Dataset)", fontsize=14)
    fig.tight_layout()
    fig.savefig(PLOTS / "09_adaption_percentile_breakdown.png", dpi=150)
    plt.close()
    print("  09_adaption_percentile_breakdown.png")


# ── Plot 10: Message vs Completion Quality — Before/After Scatter ───────────

def plot_message_vs_completion(evals):
    fig, ax = plt.subplots(figsize=(8, 8))
    stage = "persona_verification"

    for arch in ARCHETYPES:
        ev = evals[stage].get(arch, {})
        raw = ev.get("raw_results", {})
        summary = raw.get("summary", {})
        mq = summary.get("message_quality", {})
        cq = summary.get("completion_quality", {})

        mq_before = mq.get("before", 0)
        mq_after = mq.get("after", 0)
        cq_before = cq.get("before", 0)
        cq_after = cq.get("after", 0)

        # Before point
        ax.scatter(mq_before, cq_before, s=100, color=COLORS[arch], alpha=0.3,
                   marker="s", zorder=3)
        # After point
        ax.scatter(mq_after, cq_after, s=150, color=COLORS[arch], alpha=0.9,
                   marker="o", zorder=4, edgecolors="black", linewidths=0.5)
        # Arrow
        ax.annotate("", xy=(mq_after, cq_after), xytext=(mq_before, cq_before),
                    arrowprops=dict(arrowstyle="->", color=COLORS[arch], lw=1.5, alpha=0.6))
        ax.text(mq_after + 0.05, cq_after + 0.1, LABELS[arch], fontsize=9,
                color=COLORS[arch], fontweight="bold")

    ax.set_xlabel("Message Quality Score")
    ax.set_ylabel("Completion Quality Score")
    ax.set_xlim(0, 11)
    ax.set_ylim(-0.5, 11)
    ax.set_title("Persona Verification: Message vs Completion Quality\n(square = before, circle = after)")
    ax.axhline(y=9.38, color="gray", linestyle=":", alpha=0.5, label="Reference mean (completion)")
    ax.axvline(x=8.36, color="gray", linestyle=":", alpha=0.5, label="Reference mean (message)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(PLOTS / "10_message_vs_completion.png", dpi=150)
    plt.close()
    print("  10_message_vs_completion.png")


# ── Plot 11: Improvement Percentage Radar ────────────────────────────────────

def plot_improvement_radar(evals):
    stage = "persona_verification"
    metrics = ["overall_percentage_gain", "message_quality_percentage_gain",
               "completion_quality_percentage_gain"]
    metric_labels = ["Overall Gain %", "Message Quality Gain %", "Completion Quality Gain %"]

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(ARCHETYPES))
    width = 0.25

    for m_idx, (metric, mlabel) in enumerate(zip(metrics, metric_labels)):
        vals = []
        for arch in ARCHETYPES:
            ev = evals[stage].get(arch, {})
            gains = ev.get("raw_results", {}).get("gains", {})
            vals.append(gains.get(metric, 0))
        colors = ["#1976D2", "#43A047", "#FB8C00"]
        ax.bar(x + (m_idx - 1) * width, vals, width, label=mlabel, color=colors[m_idx], alpha=0.85)
        for i, v in enumerate(vals):
            if v > 0:
                ax.text(i + (m_idx - 1) * width, v + 1, f"{v:.0f}%", ha="center", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[a] for a in ARCHETYPES])
    ax.set_ylabel("Improvement (%)")
    ax.set_title("Adaption Labs Quality Gains — Persona Verification Stage")
    ax.legend()
    fig.tight_layout()
    fig.savefig(PLOTS / "11_adaption_improvement.png", dpi=150)
    plt.close()
    print("  11_adaption_improvement.png")


# ── Plot 12: Completion Quality Distribution (min/median/max/std) ───────────

def plot_completion_quality_dist(evals):
    stage = "persona_verification"
    fig, ax = plt.subplots(figsize=(10, 6))

    for i, arch in enumerate(ARCHETYPES):
        ev = evals[stage].get(arch, {})
        qa = ev.get("raw_results", {}).get("quality_after", {})
        mn = qa.get("min_completion_quality", 0)
        md = qa.get("median_completion_quality", 0)
        mx = qa.get("max_completion_quality", 0)
        avg = qa.get("average_completion_quality", 0)
        std = qa.get("std_completion_quality", 0)

        ax.barh(i, avg, color=COLORS[arch], alpha=0.7, height=0.6)
        ax.errorbar(avg, i, xerr=std, fmt="o", color="black", capsize=5, markersize=6)
        ax.plot([mn, mx], [i, i], color=COLORS[arch], linewidth=3, alpha=0.4)
        ax.scatter([mn, mx], [i, i], color=COLORS[arch], s=40, zorder=5, edgecolors="black", linewidths=0.5)
        ax.text(mx + 0.15, i, f"avg={avg:.2f} std={std:.2f} [{mn}-{mx}]", va="center", fontsize=9)

    ref_mean = 9.38
    ax.axvline(x=ref_mean, color="gray", linestyle=":", alpha=0.7, label=f"Reference mean ({ref_mean})")
    ax.set_yticks(range(len(ARCHETYPES)))
    ax.set_yticklabels([LABELS[a] for a in ARCHETYPES])
    ax.set_xlabel("Completion Quality Score")
    ax.set_title("Adaption Completion Quality Distribution (After Enhancement)")
    ax.set_xlim(0, 12)
    ax.legend()
    fig.tight_layout()
    fig.savefig(PLOTS / "12_completion_quality_dist.png", dpi=150)
    plt.close()
    print("  12_completion_quality_dist.png")


if __name__ == "__main__":
    evals = load_evals()
    print("Generating Adaption metric plots...")
    plot_quality_scores(evals)
    plot_percentile_breakdown(evals)
    plot_message_vs_completion(evals)
    plot_improvement_radar(evals)
    plot_completion_quality_dist(evals)
    print(f"\nAll Adaption plots saved to {PLOTS}/")