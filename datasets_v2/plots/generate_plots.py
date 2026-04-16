"""
Generate visualization plots for v2 persona-conditioned dataset pipeline.
Outputs PNG files to datasets_v2/plots/.
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

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


# ── Plot 1: Coherence progression across rounds ─────────────────────────────

def plot_coherence_progression():
    rounds = ["v1\n(random)", "v2 R1\n(anchored)", "v2 R2\n(tightened)", "v2 R3\n(joint)"]
    data = {
        "remittance": [0.090, 0.426, 0.589, 0.516],
        "gig_worker": [0.168, 0.370, 0.402, 0.399],
        "unbanked":   [0.145, 0.543, 0.540, 0.609],
        "itin":       [0.097, 0.720, 0.718, 0.798],
    }

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(rounds))
    for arch in ARCHETYPES:
        ax.plot(x, data[arch], marker="o", linewidth=2.5, markersize=8,
                color=COLORS[arch], label=LABELS[arch])
        ax.annotate(f"{data[arch][-1]:.3f}", (x[-1], data[arch][-1]),
                    textcoords="offset points", xytext=(10, 0), fontsize=9,
                    color=COLORS[arch], fontweight="bold")

    ax.axhline(y=0.6, color="red", linestyle="--", alpha=0.5, label="Pass threshold (0.6)")
    ax.set_xticks(x)
    ax.set_xticklabels(rounds)
    ax.set_ylabel("Mean Coherence Score")
    ax.set_title("Persona Coherence Progression Across Verification Rounds")
    ax.set_ylim(0, 1.0)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(PLOTS / "01_coherence_progression.png", dpi=150)
    plt.close()
    print("  01_coherence_progression.png")


# ── Plot 2: Score distributions (violin/box) per archetype — R3 ─────────────

def plot_score_distributions():
    fig, axes = plt.subplots(1, 4, figsize=(14, 5), sharey=True)
    for i, arch in enumerate(ARCHETYPES):
        df = pd.read_parquet(DATA / arch / "persona_verification" / "coherence_report.parquet")
        scores = df["coherence_score"].dropna().values
        ax = axes[i]
        parts = ax.violinplot(scores, positions=[0], showmedians=True, showextrema=False)
        for pc in parts["bodies"]:
            pc.set_facecolor(COLORS[arch])
            pc.set_alpha(0.6)
        parts["cmedians"].set_color("black")
        ax.scatter(np.zeros_like(scores) + np.random.normal(0, 0.03, len(scores)),
                   scores, alpha=0.4, s=15, color=COLORS[arch], zorder=3)
        ax.axhline(y=0.6, color="red", linestyle="--", alpha=0.4)
        ax.set_title(f"{LABELS[arch]}\nmean={scores.mean():.3f}")
        ax.set_xticks([])
        ax.set_ylim(-0.05, 1.05)
    axes[0].set_ylabel("Coherence Score")
    fig.suptitle("Round 3 Coherence Score Distributions (n=50 per archetype)", fontsize=13)
    fig.tight_layout()
    fig.savefig(PLOTS / "02_score_distributions.png", dpi=150)
    plt.close()
    print("  02_score_distributions.png")


# ── Plot 3: Per-persona coherence heatmap (R3) ──────────────────────────────

def plot_persona_heatmap():
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for idx, arch in enumerate(ARCHETYPES):
        ax = axes[idx // 2][idx % 2]
        df = pd.read_parquet(DATA / arch / "persona_verification" / "coherence_report.parquet")
        persona_scores = df.groupby("persona_id")["coherence_score"].agg(["mean", "count"]).sort_values("mean", ascending=True)
        colors = [COLORS[arch] if m >= 0.6 else "#EF5350" for m in persona_scores["mean"]]
        bars = ax.barh(range(len(persona_scores)), persona_scores["mean"], color=colors, alpha=0.8)
        ax.set_yticks(range(len(persona_scores)))
        ax.set_yticklabels(persona_scores.index, fontsize=8)
        ax.axvline(x=0.6, color="red", linestyle="--", alpha=0.5)
        ax.set_xlim(0, 1.0)
        ax.set_title(f"{LABELS[arch]}")
        ax.set_xlabel("Mean Coherence")
        for j, (mean, count) in enumerate(zip(persona_scores["mean"], persona_scores["count"])):
            ax.text(mean + 0.02, j, f"{mean:.2f} (n={int(count)})", va="center", fontsize=7)
    fig.suptitle("Per-Persona Mean Coherence — Round 3", fontsize=13)
    fig.tight_layout()
    fig.savefig(PLOTS / "03_persona_heatmap.png", dpi=150)
    plt.close()
    print("  03_persona_heatmap.png")


# ── Plot 4: v1 vs v2 transaction distributions (amount, hour, cadence) ──────

def plot_v1_v2_distributions():
    fig, axes = plt.subplots(3, 4, figsize=(16, 10))
    metrics = [
        ("transaction_amount_usd", "Amount (USD)", (0, 1500)),
        ("hour_of_day", "Hour of Day", (0, 24)),
        ("days_since_last_txn", "Days Since Last Txn", (0, 40)),
    ]
    for col_idx, arch in enumerate(ARCHETYPES):
        v2 = pd.read_parquet(DATA / arch / "synthetic" / "transactions.parquet")
        v1_path = ROOT / "datasets" / arch / "synthetic" / "transactions.parquet"
        v1 = pd.read_parquet(v1_path) if v1_path.exists() else None

        for row_idx, (metric, label, xlim) in enumerate(metrics):
            ax = axes[row_idx][col_idx]
            if v1 is not None and metric in v1.columns:
                ax.hist(v1[metric].dropna().clip(xlim[0], xlim[1]), bins=30, alpha=0.5,
                        color="gray", label="v1", density=True)
            ax.hist(v2[metric].dropna().clip(xlim[0], xlim[1]), bins=30, alpha=0.6,
                    color=COLORS[arch], label="v2", density=True)
            ax.set_xlim(xlim)
            if row_idx == 0:
                ax.set_title(LABELS[arch])
            if col_idx == 0:
                ax.set_ylabel(label)
            if row_idx == 0 and col_idx == 0:
                ax.legend(fontsize=8)
    fig.suptitle("V1 vs V2 Transaction Distributions", fontsize=13)
    fig.tight_layout()
    fig.savefig(PLOTS / "04_v1_v2_distributions.png", dpi=150)
    plt.close()
    print("  04_v1_v2_distributions.png")


# ── Plot 5: Instrument diversity — v2 per archetype ─────────────────────────

def plot_instrument_diversity():
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for idx, arch in enumerate(ARCHETYPES):
        ax = axes[idx // 2][idx % 2]
        df = pd.read_parquet(DATA / arch / "synthetic" / "transactions.parquet")
        counts = df["instrument"].value_counts().head(10)
        bars = ax.barh(range(len(counts)), counts.values, color=COLORS[arch], alpha=0.8)
        ax.set_yticks(range(len(counts)))
        ax.set_yticklabels(counts.index, fontsize=8)
        ax.invert_yaxis()
        ax.set_title(f"{LABELS[arch]} — Top Instruments")
        ax.set_xlabel("Transaction Count")
        for j, v in enumerate(counts.values):
            ax.text(v + 10, j, str(v), va="center", fontsize=8)
    fig.suptitle("V2 Instrument Distribution per Archetype (5,000 txns each)", fontsize=13)
    fig.tight_layout()
    fig.savefig(PLOTS / "05_instrument_diversity.png", dpi=150)
    plt.close()
    print("  05_instrument_diversity.png")


# ── Plot 6: Fraud vs legit comparison per archetype ──────────────────────────

def plot_fraud_vs_legit():
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    for col_idx, arch in enumerate(ARCHETYPES):
        df = pd.read_parquet(DATA / arch / "synthetic" / "transactions.parquet")
        legit = df[df.is_fraud == 0]
        fraud = df[df.is_fraud == 1]

        ax1 = axes[0][col_idx]
        ax1.hist(legit["transaction_amount_usd"].clip(0, 2000), bins=30, alpha=0.6,
                 color=COLORS[arch], label="Legit", density=True)
        ax1.hist(fraud["transaction_amount_usd"].clip(0, 2000), bins=30, alpha=0.5,
                 color="#EF5350", label="Fraud", density=True)
        ax1.set_title(LABELS[arch])
        if col_idx == 0:
            ax1.set_ylabel("Amount (USD)")
            ax1.legend(fontsize=8)

        ax2 = axes[1][col_idx]
        ax2.hist(legit["hour_of_day"], bins=24, alpha=0.6, color=COLORS[arch],
                 label="Legit", density=True)
        ax2.hist(fraud["hour_of_day"], bins=24, alpha=0.5, color="#EF5350",
                 label="Fraud", density=True)
        if col_idx == 0:
            ax2.set_ylabel("Hour of Day")

    fig.suptitle("Fraud vs Legitimate: Amount & Hour Distributions", fontsize=13)
    fig.tight_layout()
    fig.savefig(PLOTS / "06_fraud_vs_legit.png", dpi=150)
    plt.close()
    print("  06_fraud_vs_legit.png")


# ── Plot 7: Pass rate improvement waterfall ──────────────────────────────────

def plot_pass_rate_waterfall():
    rounds = ["v1", "R1", "R2", "R3"]
    pass_rates = {
        "remittance": [0, 24, 56, 44],
        "gig_worker": [0, 20, 20, 24],
        "unbanked":   [0, 46, 46, 58],
        "itin":       [0, 74, 80, 90],
    }

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(rounds))
    width = 0.2
    for i, arch in enumerate(ARCHETYPES):
        offset = (i - 1.5) * width
        ax.bar(x + offset, pass_rates[arch], width, label=LABELS[arch],
               color=COLORS[arch], alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(rounds)
    ax.set_ylabel("Pass Rate (>= 0.6)")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_title("Coherence Pass Rate (>=0.6) Across Verification Rounds")
    ax.legend()
    ax.set_ylim(0, 100)
    fig.tight_layout()
    fig.savefig(PLOTS / "07_pass_rate_waterfall.png", dpi=150)
    plt.close()
    print("  07_pass_rate_waterfall.png")


if __name__ == "__main__":
    print("Generating plots...")
    plot_coherence_progression()
    plot_score_distributions()
    plot_persona_heatmap()
    plot_v1_v2_distributions()
    plot_instrument_diversity()
    plot_fraud_vs_legit()
    plot_pass_rate_waterfall()
    print(f"\nAll plots saved to {PLOTS}/")