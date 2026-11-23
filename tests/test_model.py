import pandas as pd
import pytest

from src.model import fit_linear, interpret_pearson, predict, project_trend


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


def test_trend_projection():
    assert project_trend([10, 12, 14, 16], steps=2) == pytest.approx([18, 20])
    assert project_trend([99, 12, 14, 16], steps=2, skip=1) == pytest.approx([18, 20])


@pytest.mark.parametrize("values", [[1, 2], [1, float("nan"), 3, 4]])
def test_trend_rejects_short_or_gapped_series(values):
    with pytest.raises(ValueError):
        project_trend(values)
