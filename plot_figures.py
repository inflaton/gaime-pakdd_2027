#!/usr/bin/env python3
"""Plot the paper's benchmark frontier and the pilot's supplementary loss curves."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter, MultipleLocator, NullLocator


DATA = Path(__file__).resolve().parent / "data" / "figure_inputs.json"
PDF_METADATA = {"Creator": None, "Producer": None, "CreationDate": None}

# Offsets and alignments place text relative to the corresponding measured point.
FRONTIER_LABELS = {
    "PROD": ("120B production", "reference", (0, -9), "center"),
    "ZS": ("12B base,\nzero-shot", "reference", (0, 8), "center"),
    "T1": ("T1", "student", (-5, -1), "right"),
    "T1s43": ("T1, seed 43", "student", (5, -2), "left"),
    "T1_fp8": ("fp8", "no retraining", (5, 1), "left"),
    "T1_nvfp4": ("NVFP4", "no retraining", (5, -1), "left"),
    "T1_w4a16": ("W4A16", "no retraining", (-5, 2), "right"),
    "T1_think": ("thinking", "no retraining", (-5, 0), "right"),
    "T1_27B": ("27B", "changes the model", (-5, -1), "right"),
    "T1_27B_think": ("27B + thinking", "changes the model", (-5, -6), "right"),
    "A42": ("+expert labels", "changes the model", (5, -3), "left"),
    "A43": ("+expert, s43", "changes the model", (5, 0), "left"),
    "A42_think": ("+expert\n+ thinking", "changes the model", (5, 6), "left"),
}
FRONTIER_STYLES = {
    "reference": ("#7a7974", "D"),
    "student": ("#7a7974", "o"),
    "no retraining": ("#2a78d6", "s"),
    "changes the model": ("#eb6834", "^"),
}
LOSS_STYLES = {
    "T1": ("T1, seed 42", "#0072B2", "o", "-"),
    "T1-s43": ("T1, seed 43", "#0072B2", "o", "--"),
    "T1-X490": ("T1 + expert labels, seed 42", "#C45111", "^", "-"),
    "T1-X490-s43": ("T1 + expert labels, seed 43", "#C45111", "^", "--"),
}


def plot_frontier(points, output):
    plt.rcParams.update({"font.size": 7.5, "axes.linewidth": 0.6})
    fig, ax = plt.subplots(figsize=(3.05, 2.3), dpi=300)
    ax.grid(True, color="#e6e5e0", lw=0.5, zorder=0)
    x_values, y_values = [], []
    for arm, (label, group, offset, alignment) in FRONTIER_LABELS.items():
        x = points[arm]["no_match_false_match_rate_pct"]
        y = points[arm]["match_recall_pct"]
        x_values.append(x)
        y_values.append(y)
        color, marker = FRONTIER_STYLES[group]
        ax.scatter(x, y, s=20, c=color, marker=marker, edgecolors="white",
                   linewidths=0.7, zorder=3)
        ax.annotate(label, (x, y), xytext=offset, textcoords="offset points",
                    ha=alignment, va="center", fontsize=6, color="#2b2b2a", linespacing=0.95)

    x_min, x_max = min(x_values) * 0.8, max(x_values) * 1.35
    ax.set_xscale("log")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(min(y_values) - 1.2, max(y_values) + 1.6)
    ticks = [tick for tick in (1, 2, 3, 5, 8, 13) if x_min <= tick <= x_max]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([str(tick) for tick in ticks])
    ax.set_xlabel("False-match rate on no-match queries, N-FMR (%, log scale)")
    ax.set_ylabel("Match recall $R_m$ (%)")
    ax.spines[["top", "right"]].set_visible(False)
    handles = [
        Line2D([], [], ls="", marker=marker, color=color, markersize=4.2, label=group)
        for group, (color, marker) in FRONTIER_STYLES.items()
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=6,
              handletextpad=0.2, borderaxespad=0.2)
    fig.tight_layout(pad=0.3)
    fig.savefig(output, metadata=PDF_METADATA)
    plt.close(fig)


def plot_pilot_losses(curves, output):
    plt.rcParams.update({"font.size": 8.5, "axes.linewidth": 0.65})
    fig, (train, validation) = plt.subplots(1, 2, sharex=True, figsize=(4.8, 2.45))
    handles = []
    for arm, (label, color, marker, linestyle) in LOSS_STYLES.items():
        style = dict(color=color, marker=marker, linestyle=linestyle, markerfacecolor="white")
        train.plot(*zip(*curves[arm]["training"]), linewidth=0.85, markersize=2.2,
                   markeredgewidth=0.6, **style)
        line, = validation.plot(*zip(*curves[arm]["validation"]), label=label,
                                linewidth=1.1, markersize=3.7, markeredgewidth=0.85, **style)
        handles.append(line)

    train.set_title("(a) Training", loc="left", fontweight="bold")
    train.set_ylabel("Loss (log scale)")
    train.set_yscale("log")
    validation.set_title("(b) Validation", loc="left", fontweight="bold")
    validation.set_ylabel(r"Loss ($\times 10^{-3}$)")
    validation.yaxis.set_major_locator(MultipleLocator(0.001))
    validation.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{1_000 * value:g}"))
    for ax in (train, validation):
        ax.set_xlim(0, 166)
        ax.xaxis.set_major_locator(MultipleLocator(40))
        ax.grid(axis="y", color="#dedede", linewidth=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(width=0.6, length=2.5, pad=2)
        ax.spines[["top", "right"]].set_visible(False)

    fig.subplots_adjust(left=0.135, right=0.98, bottom=0.29, top=0.88, wspace=0.39)
    fig.supxlabel("Optimizer updates", y=0.17, fontsize=8.5)
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, fontsize=8,
               handlelength=2.6, columnspacing=2.2, borderaxespad=0.5)
    fig.savefig(output, metadata=PDF_METADATA)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("figures"),
                        help="directory for the two PDFs (default: figures)")
    args = parser.parse_args()
    inputs = json.loads(DATA.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Liberation Serif", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "pdf.fonttype": 42,
    })
    plot_frontier(inputs["frontier"], args.output_dir / "fig_frontier.pdf")
    plot_pilot_losses(inputs["pilot_losses"], args.output_dir / "fig_pilot_losses.pdf")


if __name__ == "__main__":
    main()
