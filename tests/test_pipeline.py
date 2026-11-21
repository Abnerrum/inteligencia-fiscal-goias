import sqlite3

import pandas as pd
import pytest

from src import pipeline
from src.database import load_database


def test_xlsx_csv_import_idempotent_and_rejects_wrong_month(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(pipeline, "RAW", raw)
    catalog = pd.DataFrame({
        "codigo_ibge": [5203500, 5208707, 5201108],
        "municipio": ["Bom Jesus de Goiás", "Goiânia", "Anápolis"],
    })
    catalog["chave"] = catalog.municipio.map(pipeline.clean_key)
    monkeypatch.setattr(pipeline, "load_catalog", lambda download: catalog)
    icms, frota, db = (tmp_path / name for name in ("icms.csv", "frota.xlsx", "test.db"))
    icms.write_text(
        "NOME_MUNICIPIO;VALOR_BRUTO_ICMS;ANO_MES_REPASSE\n"
        "BOM JESUS;1.234,50;202507\nBOM JESUS;1.234,50;202507\n"
        "GOIANIA;2000;202507\nANAPOLIS;1500;202507\n",
        encoding="utf-8",
    )
    pd.DataFrame({
        "MUNICIPIO": ["Bom Jesus", "Bom Jesus", "Goiânia", "Anápolis"],
        "QTD": [5, 5, 40, 20],
    }).to_excel(frota, index=False)

    for _ in range(2):
        pipeline.build_database(icms, frota, False, db_path=db)
    data = load_database(db).set_index("codigo_ibge")
    assert len(data) == 3
    assert data.loc[5203500, "icms"] == 1234.50
    assert data.loc[5203500, "frota"] == 10
    with pytest.raises(ValueError, match="fora de 2025-08"):
        pipeline.build_database(icms, frota, False, month="2025-08", db_path=db)
    pd.testing.assert_frame_equal(load_database(db).set_index("codigo_ibge"), data)
    with sqlite3.connect(db) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_legacy_database_is_readable(tmp_path, monkeypatch):
    from src import database

    old = tmp_path / "goias.db"
    monkeypatch.setattr(database, "LEGACY_DB", old)
    monkeypatch.setattr(database, "DB", tmp_path / "new.db")
    with sqlite3.connect(old) as connection:
        connection.execute("CREATE TABLE indicadores (periodo, municipio, icms, frota)")
        connection.execute("INSERT INTO indicadores VALUES ('2025-07','GOIANIA',100,10)")
    assert load_database().iloc[0].municipio == "GOIANIA"


def test_reconciliation_selects_month_and_icms(tmp_path):
    workbook = tmp_path / "conciliacao.xlsx"
    cities = [f"Município {number}" for number in range(246)]
    frame = pd.DataFrame({
        "Município": cities * 2,
        "Referência": [pd.Timestamp("2025-08-01")] * 246 + [pd.Timestamp("2025-09-01")] * 246,
        "ICMS": [120] * 246 + [220] * 246,
        "IPVA": [999] * 492,
    })
    frame.to_excel(workbook, sheet_name="Agregado", startrow=3, index=False)

    result = pipeline.read_reconciliation(workbook, "2025-08")
    assert len(result) == 246
    assert result.VALOR_BRUTO_ICMS.eq(120).all()
    with pytest.raises(ValueError, match="246 municípios"):
        pipeline.read_reconciliation(workbook, "2025-10")
