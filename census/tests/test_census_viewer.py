"""Tests for census/census_viewer.py, on the made-up tree from test_tree.py."""

from test_tree import STATUSES, build

import census_viewer


def test_viewer_cards() -> None:
    """Shares only on candidate cards, out of all candidates, plus decorated counts.

    The excluded sticker's decorated shape isn't counted under Candidates.
    """
    nodes = {n["label"]: n for n in census_viewer.viewer_nodes(build(), STATUSES)}
    assert "usageShare" not in nodes["Part numbers"]
    assert "shapeShare" not in nodes["Excluded"]
    assert nodes["Candidates"]["usageShare"] == 1.0
    assert nodes["3024"]["usageShare"] == 60 / 286
    assert (nodes["Plates"]["covered"], nodes["Plates"]["inProgress"]) == (1, 1)
    assert nodes["Candidates"]["decorated"] == 2
    assert nodes["3023"]["decorated"] == 2
    assert nodes["3023pr0002"]["usage"] == 5
