"""Tests for ``src.figures`` — what a chart shows, not how it looks."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src import figures  # noqa: E402


def bars(counts, **kwargs):
    fig, ax = plt.subplots()
    figures.bar_counts(ax, counts, "t", **kwargs)
    shown = {t.get_text(): p.get_width() for t, p in zip(ax.get_yticklabels(), ax.patches)}
    plt.close(fig)
    return shown, ax.get_title()


def test_a_value_the_order_does_not_name_is_kept_not_dropped():
    # The pilot's education panel showed only "bachelor": the order used display
    # wording while the column stores codes, and every unmatched code vanished.
    shown, title = bars({"bachelor": 2, "master_or_higher": 1, "high_school": 2},
                        order=["compulsory", "bachelor", "master or higher"])
    assert shown["master_or_higher"] == 1 and shown["high_school"] == 2
    assert "n = 5" in title


def test_labels_map_codes_to_display_text_in_the_given_order():
    order = {"high_school": "matura or high school", "bachelor": "bachelor"}
    shown, _ = bars({"bachelor": 2, "high_school": 1}, order=order, labels=order)
    assert list(shown) == ["bachelor", "matura or high school"]  # bottom to top: order is top to bottom
    assert shown["matura or high school"] == 1


def test_an_empty_count_says_so():
    shown, title = bars({})
    assert shown == {} and "n = 0" in title
