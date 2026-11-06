from __future__ import annotations

import pandas as pd
import pytest

from menuiq import basket


@pytest.mark.unit
def test_lift_of_perfectly_associated_pair():
    # A and B always together (4/10 orders); C alone in the rest.
    rows = [{"A": True, "B": True, "C": False}] * 4 + [{"A": False, "B": False, "C": True}] * 6
    pairs = basket.pair_rules(pd.DataFrame(rows), min_support=0.01)
    ab = pairs[(pairs["item_a"] == "A") & (pairs["item_b"] == "B")].iloc[0]
    assert ab["support"] == pytest.approx(0.4)
    assert ab["confidence_a_to_b"] == pytest.approx(1.0)
    assert ab["lift"] == pytest.approx(0.4 / (0.4 * 0.4))


@pytest.mark.unit
def test_min_support_filters_rare_pairs():
    rows = [{"A": True, "B": True}] + [{"A": True, "B": False}] * 99
    assert basket.pair_rules(pd.DataFrame(rows), min_support=0.05).empty
