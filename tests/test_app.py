from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from src import database


def test_panel_filters_and_simulation(tmp_path, monkeypatch):
    db = tmp_path / "painel.db"
    monkeypatch.setattr(database, "DB", db)
    catalog = pd.DataFrame({"codigo_ibge": [1, 2, 3], "municipio": ["Anápolis", "Goiânia", "Jussara"]})
    for month, shift in (("2025-06", 0), ("2025-07", 10)):
        icms = catalog[["codigo_ibge"]].assign(icms=[25 + shift, 45 + shift, 65 + shift])
        fleet = catalog[["codigo_ibge"]].assign(frota=[10, 20, 30])
        database.save_period(month, catalog, icms, fleet, ("fixture", "fixture"), db)

    path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(path)).run()
    assert not app.exception
    assert app.selectbox[0].value == "2025-07"

    app.selectbox[0].select("2025-06").run()
    app.multiselect[0].select("Goiânia").run()
    assert app.dataframe[0].value.municipio.tolist() == ["Goiânia"]
    assert app.metric[0].value == "1"
    assert app.metric[3].value == "1,000"

    app.number_input[0].set_value(100)
    app.button(key="FormSubmitter:simulation_2025-06-Calcular estimativa").click().run()
    assert not app.exception
    assert app.metric[-1].value == "R$ 205,00"
    assert "Extrapolação" in app.warning[0].value


def test_batch_import_button(tmp_path, monkeypatch):
    from src import pipeline

    monkeypatch.setattr(database, "DB", tmp_path / "missing.db")
    monkeypatch.setattr(database, "LEGACY_DB", tmp_path / "legacy.db")
    monkeypatch.setattr(pipeline, "import_all", lambda download: iter([
        ("2025-07", 246, ""),
        ("2025-08", None, "Sem ICMS bruto"),
    ]))
    path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(path)).run()
    app.button(key="import_all").click().run()
    assert not app.exception
    assert any("1 de 2 competências" in item.value for item in app.markdown)
    assert any("Sem ICMS bruto" in item.value for item in app.warning)
