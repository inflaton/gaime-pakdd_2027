#!/usr/bin/env python3
"""Plot the paper's benchmark frontier and the pilot's supplementary loss curves."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

from plot_frontier import INPUT as FRONTIER_INPUT, METADATA as FRONTIER_METADATA, plot as make_frontier


DATA = Path(__file__).resolve().parent / "data" / "figure_inputs.json"
PDF_METADATA = {"Creator": None, "Producer": None, "CreationDate": None}

LOSS_STYLES = {
    "T1": ("T1, seed 42", "#0072B2", "o", "-"),
    "T1-s43": ("T1, seed 43", "#0072B2", "o", "--"),
    "T1-X490": ("T1 + expert labels, seed 42", "#C45111", "^", "-"),
    "T1-X490-s43": ("T1 + expert labels, seed 43", "#C45111", "^", "--"),
}


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
    frontier = make_frontier(json.loads(FRONTIER_INPUT.read_text(encoding="utf-8")))
    frontier.savefig(args.output_dir / "fig_frontier.pdf", metadata=FRONTIER_METADATA)
    plt.close(frontier)
    plot_pilot_losses(inputs["pilot_losses"], args.output_dir / "fig_pilot_losses.pdf")


if __name__ == "__main__":
    main()
