import pandas as pd
import pytest

from src.model import fit_linear, interpret_pearson, predict


def test_known_linear_relationship():
    result = fit_linear(pd.DataFrame({"frota": [10, 20, 30], "icms": [25, 45, 65]}))
    assert result["inclinacao"] == pytest.approx(2)
    assert result["intercepto"] == pytest.approx(5)
    assert result["pearson"] == pytest.approx(1)
    assert result["r2"] == pytest.approx(1)
    assert result["mae"] == pytest.approx(0, abs=1e-10)
    assert result["rmse"] == pytest.approx(0, abs=1e-10)
    assert predict(result, 15) == pytest.approx(35)
    assert interpret_pearson(-0.8) == "associação linear forte e negativa"


@pytest.mark.parametrize("x,y", [([1, 1, 1], [5, 6, 7]), ([1, 2, 3], [5, 5, 5]), ([1, 2], [5, 6])])
def test_rejects_degenerate_samples(x, y):
    with pytest.raises(ValueError):
        fit_linear(pd.DataFrame({"frota": x, "icms": y}))
