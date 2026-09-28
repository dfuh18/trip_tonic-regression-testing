"""Figures for the study notebooks (05b–09): one look, one set of helpers.

Colour follows the dataviz reference palette: categorical slots 1 and 2 for
the two rounds (simulation blue, participant orange), always the same round
on the same hue; muted ink for axes and labels; a light grid behind the data.
A single-series chart uses slot 1 and carries no legend.

Every helper takes counts or values, never rows, so nothing here can put a
participant's words or an id into a figure. ``Saver`` writes PDF and PNG
under ``figures/<run_type>/``, which ``notebooks/study/.gitignore`` excludes.
"""

from __future__ import annotations

import pathlib
import statistics
from typing import Iterable, Mapping, Optional, Sequence

import matplotlib.pyplot as plt

ROUND_COLOR = {"simulation": "#2a78d6", "participant": "#eb6834"}
SERIES = "#2a78d6"
MUTED = "#898781"
INK = "#0b0b0b"
GRID = "#e6e5e1"
BAND = ("#f0efec", "#e6e5e1")


def setup() -> None:
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 300, "font.size": 10,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.spines.top": False, "axes.spines.right": False, "axes.titlelocation": "left",
    })


class Saver:
    """``save(fig, name)`` writes ``<dir>/<name>.pdf`` and ``.png`` when enabled."""

    def __init__(self, run_type: str, enabled: bool = True, root: str | pathlib.Path = "figures"):
        self.dir = pathlib.Path(root) / run_type
        self.enabled = enabled

    def __call__(self, fig, name: str) -> None:
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)
            for ext in ("pdf", "png"):
                fig.savefig(self.dir / f"{name}.{ext}", bbox_inches="tight")


def _grid(ax, axis: str = "x") -> None:
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def empty(ax, message: str = "no data yet") -> None:
    """Mark a panel that has nothing to draw, rather than drawing nothing."""
    ax.text(0.5, 0.5, message, ha="center", va="center", color=MUTED, fontstyle="italic", transform=ax.transAxes)
    ax.set_xticks([]); ax.set_yticks([])


def bar_counts(ax, counts: Mapping[str, int], title: str, xlabel: str = "count",
               color: str = SERIES, order: Optional[Sequence[str]] = None,
               labels: Optional[Mapping[str, str]] = None) -> None:
    """Horizontal bars, largest on top unless ``order`` is given, n beside each.

    ``order`` lists the stored values top to bottom; a value in ``counts`` that
    ``order`` does not name is appended after them rather than dropped, so a
    mismatch between the order and the stored codes shows up as an extra bar
    instead of silently lost data. ``labels`` maps a stored value to its
    display text."""
    if order:
        keys = list(order) + sorted(k for k in counts if k not in order)
        items = [(k, counts.get(k, 0)) for k in keys][::-1]
    else:
        items = sorted(counts.items(), key=lambda kv: kv[1])
    ax.set_title(f"{title} (n = {sum(v for _, v in items)})")
    if not items or not sum(v for _, v in items):
        empty(ax)
        return
    labels, values = [str((labels or {}).get(k, k)) for k, _ in items], [v for _, v in items]
    ax.barh(labels, values, color=color, height=0.6)
    for i, v in enumerate(values):
        ax.annotate(str(v), (v, i), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8, color=MUTED)
    ax.set_xlabel(xlabel)
    ax.xaxis.get_major_locator().set_params(integer=True)
    _grid(ax)


def strip(ax, values: Sequence[float], title: str, xlabel: str, color: str = SERIES,
          marker_median: bool = True) -> None:
    """Every value as a dot on one line, jittered; the median as a bar."""
    ax.set_title(f"{title} (n = {len(values)})")
    if not values:
        empty(ax)
        return
    jitter = [((i * 7) % 11 - 5) * 0.03 for i in range(len(values))]
    ax.scatter(values, jitter, s=40, color=color, edgecolor="white", linewidth=1.5, zorder=3)
    if marker_median:
        ax.axvline(statistics.median(values), color=INK, linewidth=2, ymin=0.2, ymax=0.8)
    ax.set_ylim(-0.5, 0.5); ax.set_yticks([])
    ax.set_xlabel(xlabel + ("; bar = median" if marker_median else ""))
    _grid(ax)


def rate_plot(ax, rounds: Mapping[str, Sequence], title: str, xlabel: str,
              colors: Optional[Mapping[str, str]] = None, order: Optional[Sequence[str]] = None,
              x_max: Optional[float] = None, missing: str = "not observed") -> None:
    """A rate per class for each round: a dot at the rate, k/n beside it. No
    interval (D104): the counts are shown so a reader sees how little a rate
    over few calls says. ``rounds`` maps a round name to a list of
    ``analysis.Rate``; ``colors`` maps the same names to a hue (default
    ``ROUND_COLOR``); ``order`` lists the classes top to bottom (default
    alphabetical), and a class it does not name is appended. A class a round
    never met is labelled so. ``x_max`` defaults to a little above the largest
    rate."""
    colors = colors or ROUND_COLOR
    seen = {r.group for rates in rounds.values() for r in rates}
    groups = (list(order) + sorted(seen - set(order))) if order else sorted(seen)
    groups = [g for g in groups if g in seen][::-1]  # the first class is drawn on top
    ax.set_title(title)
    if not groups:
        empty(ax)
        return
    offsets = {name: (i - (len(rounds) - 1) / 2) * 0.3 for i, name in enumerate(rounds)}
    for rnd, rates in rounds.items():
        by = {r.group: r for r in rates}
        first = True
        for j, g in enumerate(groups):
            yv = j + offsets[rnd]
            if g not in by:
                ax.annotate(f"{rnd}: {missing}", (0, yv), xytext=(4, 0), textcoords="offset points",
                            va="center", fontsize=7, color=MUTED, fontstyle="italic")
                continue
            r = by[g]
            ax.plot(r.rate, yv, "o", markersize=8, color=colors[rnd], markeredgecolor="white",
                    markeredgewidth=2, label=rnd if first else None)
            first = False
            ax.annotate(f"{r.failures}/{r.n}", (r.rate, yv), xytext=(8, 0), textcoords="offset points",
                        va="center", fontsize=8, color=MUTED)
    ax.set_yticks(range(len(groups)), groups)
    ax.set_ylim(-0.5, len(groups) - 0.5)
    if x_max is None:
        top = max((r.rate for rates in rounds.values() for r in rates if r.rate == r.rate), default=0)
        x_max = min(1.0, max(0.1, top * 1.25 + 0.05))
    ax.set_xlim(0, x_max)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel(xlabel)
    _grid(ax)
    if any(h for h in ax.get_legend_handles_labels()[1]):
        # Inside the axes where the marks leave room: an anchor below the axes
        # drifts away from the plot as the figure gets taller.
        ax.legend(frameon=True, facecolor="white", edgecolor="none", framealpha=0.9, loc="best")


#: Cell states for ``execution_grid``: face colour and edge colour.
GRID_CELL = {
    "pass": (SERIES, SERIES),
    "draw": ("#b7d3f6", SERIES),  # passed only as a position draw (D88)
    "fail": ("white", MUTED),
    "structural": ("white", MUTED),  # failed a structural check: drawn with a cross
}


def grid_legend(ax, labels: Mapping[str, str], **kwargs) -> None:
    """A legend for ``execution_grid``: one entry per state in ``labels``
    (state → text), each drawn as the grid draws it, the cross included."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = []
    for state in labels:
        face, edge = GRID_CELL[state]
        square = Patch(facecolor=face, edgecolor=edge)
        handles.append((square, Line2D([], [], marker="x", color=MUTED, linestyle="", markersize=6))
                       if state == "structural" else square)
    ax.legend(handles, list(labels.values()), frameon=False, **kwargs)


def execution_grid(ax, rows: Sequence[Mapping], title: str) -> None:
    """One row per case, one square per execution.

    ``rows`` are dicts with ``label``, ``group`` (a heading, e.g. the
    function), ``cells`` (a list of ``"pass" | "draw" | "fail" | "structural"``,
    one per repetition; ``structural`` is a failure a structural check
    detected, drawn as an empty square with a cross), ``verdict`` (``"pass" | "fail"``) and ``indent`` (a
    follow-up drawn under its seed). Rows are drawn top to bottom in the given
    order; a heading starts wherever ``group`` changes. Identity is never
    colour alone: a failed execution is an empty square, a failing case is
    also written out and set in bold, and a follow-up is marked "↳"."""
    from matplotlib.patches import Rectangle

    ax.set_title(title)
    if not rows:
        empty(ax)
        return
    width = max(len(r["cells"]) for r in rows)

    def draw(r, y):
        for i, state in enumerate(r["cells"]):
            face, edge = GRID_CELL[state]
            ax.add_patch(Rectangle((i + 0.1, y - 0.4), 0.8, 0.8, facecolor=face, edgecolor=edge, linewidth=1))
            if state == "structural":
                ax.plot([i + 0.3, i + 0.7], [y - 0.25, y + 0.25], color=MUTED, linewidth=1.2)
                ax.plot([i + 0.3, i + 0.7], [y + 0.25, y - 0.25], color=MUTED, linewidth=1.2)
        passed = sum(1 for c in r["cells"] if c not in ("fail", "structural"))
        failing = r["verdict"] != "pass"
        ax.text(width + 0.4, y, f"{passed}/{len(r['cells'])}  {'FAIL' if failing else 'pass'}", va="center",
                fontsize=8, color=INK if failing else MUTED, fontweight="bold" if failing else "normal")

    bottom = _grouped_rows(ax, rows, draw)
    ax.set_xlim(0, width + 2.2)
    ax.set_ylim(bottom, -0.8)
    ax.set_xticks([])


def _grouped_rows(ax, rows: Sequence[Mapping], draw_row) -> float:
    """Shared layout for the per-case figures: a bold heading wherever
    ``group`` changes, follow-ups marked "↳" in muted ink, failing cases in
    bold. ``draw_row(row, y)`` draws one row's marks. Returns the bottom y."""
    y, last_group, ticks, labels, styles = 0.0, None, [], [], []
    for r in rows:
        if r["group"] != last_group:
            y += 0.6 if last_group is not None else 0
            ax.text(-0.3, y, r["group"], ha="right", va="center", fontsize=9, fontweight="bold", color=INK)
            y += 1
            last_group = r["group"]
        draw_row(r, y)
        ticks.append(y)
        labels.append(("↳ " if r.get("indent") else "") + r["label"])
        styles.append((r.get("verdict") not in (None, "pass"), bool(r.get("indent"))))
        y += 1
    ax.set_yticks(ticks, labels, fontsize=8)
    for tick, (failing, follow_up) in zip(ax.get_yticklabels(), styles):
        tick.set_fontweight("bold" if failing else "normal")
        tick.set_color(INK if failing or not follow_up else MUTED)
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    return y


def count_grid(ax, rows: Sequence[Mapping], columns: Sequence, title: str, xlabel: str,
               mark_column=None, right: Optional[Sequence[str]] = None) -> None:
    """Rows of counts over ordered columns: each cell shows its count, shaded
    in one hue by its **share of the row**, blank when zero, so rows of
    different sizes (8 vs 4 repetitions) read alike. ``rows`` as for
    ``execution_grid`` but with ``counts`` (column → count) instead of
    ``cells``; ``mark_column`` gets a guide line; ``right`` is one note per row."""
    from matplotlib.patches import Rectangle

    ax.set_title(title)
    if not rows:
        empty(ax)
        return
    ramp = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95")  # palette steps 100–600

    def draw(r, y):
        total = sum(r["counts"].values()) or 1
        for i, col in enumerate(columns):
            n = r["counts"].get(col, 0)
            if not n:
                continue
            shade = ramp[min(len(ramp) - 1, int((n / total) * (len(ramp) - 1) + 0.5))]
            ax.add_patch(Rectangle((i + 0.06, y - 0.42), 0.88, 0.84, facecolor=shade, edgecolor="white", linewidth=1))
            ax.text(i + 0.5, y, str(n), ha="center", va="center", fontsize=7,
                    color="white" if ramp.index(shade) >= 3 else INK)

    bottom = _grouped_rows(ax, rows, draw)
    if mark_column is not None and mark_column in columns:
        x = list(columns).index(mark_column) + 0.5
        ax.axvline(x, color=MUTED, linewidth=0.8, zorder=0)
    if right:
        for (r, note), y in zip(zip(rows, right), [t for t in ax.get_yticks()]):
            ax.text(len(columns) + 0.3, y, note, va="center", fontsize=8,
                    color=INK if r.get("verdict") not in (None, "pass") else MUTED)
    ax.set_xticks([i + 0.5 for i in range(len(columns))], [f"{c:+d}" if isinstance(c, int) and c else str(c) for c in columns])
    ax.xaxis.set_ticks_position("top")
    ax.tick_params(axis="x", length=0, labelsize=8, colors=MUTED)
    ax.set_xlim(0, len(columns) + (1.6 if right else 0))
    ax.set_ylim(bottom, -0.8)
    ax.set_xlabel(xlabel, fontsize=8, color=MUTED)


def paired_shares(ax, shares: Mapping[str, Mapping[str, float]], title: str, xlabel: str = "share") -> None:
    """Grouped horizontal bars: per class, one bar per round, as shares."""
    classes = sorted({c for s in shares.values() for c in s},
                     key=lambda c: max(s.get(c, 0) for s in shares.values()))
    ax.set_title(title)
    if not classes:
        empty(ax)
        return
    h = 0.8 / len(shares)
    for i, (rnd, s) in enumerate(shares.items()):
        ax.barh([j + (i - (len(shares) - 1) / 2) * h for j in range(len(classes))],
                [s.get(c, 0) for c in classes], height=h - 0.04, color=ROUND_COLOR[rnd], label=rnd)
    ax.set_yticks(range(len(classes)), classes)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel(xlabel)
    _grid(ax)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], frameon=False, loc="lower right")


def grade_band(ax, values: Sequence[float], grades: Iterable[tuple[float, str]], title: str,
               xlabel: str, x_min: float = 40, color: str = SERIES) -> None:
    """Values against labelled bands (the curved grading scale); bar = mean."""
    ax.set_title(f"{title} (n = {len(values)})")
    bounds = sorted(grades)
    edges = [b for b, _ in bounds] + [100]
    for k, ((lo, g), hi) in enumerate(zip(bounds, edges[1:])):
        ax.axvspan(lo, hi, color=BAND[k % 2], linewidth=0)
        shown_lo = max(lo, x_min)
        if hi - shown_lo >= 3:
            ax.text((shown_lo + hi) / 2, 1.35, g, ha="center", va="center", fontsize=8, color=MUTED)
    if values:
        ax.scatter(values, [1] * len(values), s=64, color=color, edgecolor="white", linewidth=2, zorder=3)
        ax.axvline(sum(values) / len(values), color=INK, linewidth=2, ymin=0.2, ymax=0.8)
    else:
        ax.text(70, 1, "no data yet", ha="center", va="center", color=MUTED, fontstyle="italic")
    ax.set_xlim(x_min, 100); ax.set_ylim(0.5, 1.6); ax.set_yticks([])
    ax.set_xlabel(xlabel + "; bar = mean")
