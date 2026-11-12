#!/usr/bin/env python3
"""Plot the selected benchmark operating points from bundled aggregates.

Requires Matplotlib. Inputs are bundled aggregates; no production data or
full-repository imports are needed. Labels identify configurations directly.
The nearly coincident T1 fp8 point is omitted for readability and remains in
the benchmark table.
"""

import argparse
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator


HERE = Path(__file__).resolve().parent
INPUT = HERE / "data/frontier_inputs.json"
OUTPUT = HERE / "fig_frontier.pdf"
METADATA = {"Creator": None, "Producer": None, "CreationDate": None}

# Text locations are in data coordinates so leader lines stay clear of nearby
# operating points. All labels and markers remain inside the plot margins.
LABELS = {
    "PROD": ("120B production", (12.0, 91.5), "right"),
    "ZS": ("12B base, zero-shot", (14.6, 93.65), "right"),
    "T1": ("T1 bf16, off", (2.02, 85.95), "left"),
    "T1_w4a16": ("T1 W4A16", (1.35, 89.15), "left"),
    "T1_nvfp4": ("T1 NVFP4", (2.25, 91.45), "right"),
    "T1_27B": ("27B student, off", (1.14, 84.45), "left"),
    "T1_27B_think": ("27B student, low", (1.1, 94.65), "left"),
    "T1_think": ("T1 bf16, on", (6.25, 95.3), "left"),
    "cascade": ("T1 selective thinking (replay)", (5.0, 97.15), "center"),
}


def plot(inputs):
    points = inputs["points"]
    if set(points) != set(LABELS):
        raise ValueError("The figure labels and bundled points must agree")
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Liberation Serif", "DejaVu Serif"],
        "font.size": 10,
        "mathtext.fontset": "stix",
        "pdf.fonttype": 42,
        "axes.linewidth": 0.65,
    })
    fig, ax = plt.subplots(figsize=(4.7, 3.3))
    ax.set_xscale("log")
    ax.set_xlim(0.93, 18.0)
    ax.set_ylim(83.6, 98.0)
    ax.xaxis.set_major_locator(FixedLocator([1, 2, 3, 5, 8, 13]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels(["1", "2", "3", "5", "8", "13"])
    ax.set_yticks([85, 90, 95])
    ax.grid(color="#e5e5e5", linewidth=0.55, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(width=0.6, length=3, pad=3)
    ax.set_xlabel("No-match false-match rate (%) - log scale", labelpad=6)
    ax.set_ylabel(r"Match recall $R_m$ (%)", labelpad=6)
    annotations = []
    for key, (label, position, align) in LABELS.items():
        point = points[key]
        x, y = point["nfmr_pct"], point["recall_pct"]
        if not 0 < x < 100 or not 0 <= y <= 100:
            raise ValueError(f"Invalid metric for {key}")
        color = "#1768a0" if key == "T1_think" else "#ad5a00" if key == "cascade" else "#333333"
        ax.scatter(x, y, s=30, c=color, marker="o", edgecolors="white", linewidths=0.6, zorder=3)
        annotation = ax.annotate(
            label, (x, y), xytext=position, textcoords="data",
            fontsize=9.5, ha=align, va="center", color=color,
            arrowprops={"arrowstyle": "-", "color": "#777777", "lw": 0.55,
                        "shrinkA": 3, "shrinkB": 4},
            annotation_clip=False, zorder=4,
        )
        annotations.append(annotation)
    fig.subplots_adjust(left=0.14, right=0.98, bottom=0.20, top=0.96)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    # Validate text rectangles independently of the leader-line extents.
    boxes = [plt.Text.get_window_extent(label, renderer=renderer) for label in annotations]
    figure_box = fig.bbox
    for index, box in enumerate(boxes):
        if not figure_box.contains(box.x0, box.y0) or not figure_box.contains(box.x1, box.y1):
            raise ValueError(f"Clipped label: {list(LABELS)[index]}")
        for offset, other in enumerate(boxes[index + 1:], index + 1):
            if box.overlaps(other):
                raise ValueError(f"Configuration labels overlap: {list(LABELS)[index]} and {list(LABELS)[offset]}")
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check the bundled figure without writing")
    args = parser.parse_args()
    figure = plot(json.loads(INPUT.read_text(encoding="utf-8")))
    buffer = io.BytesIO()
    figure.savefig(buffer, format="pdf", metadata=METADATA)
    plt.close(figure)
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != buffer.getvalue():
            raise SystemExit("fig_frontier.pdf differs from the bundled inputs or rendering environment")
        print("Frontier figure matches bundled inputs; labels are unclipped and non-overlapping.")
    else:
        OUTPUT.write_bytes(buffer.getvalue())
        print("Wrote fig_frontier.pdf from bundled aggregate inputs.")


if __name__ == "__main__":
    main()
