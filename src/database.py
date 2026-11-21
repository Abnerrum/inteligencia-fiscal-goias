"""Armazenamento transacional dos indicadores mensais."""
from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "inteligencia_fiscal.db"
LEGACY_DB = ROOT / "data" / "goias.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS municipios (
    codigo_ibge INTEGER PRIMARY KEY,
    municipio TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS repasses_icms (
    periodo TEXT NOT NULL,
    codigo_ibge INTEGER REFERENCES municipios NOT NULL,
    icms REAL NOT NULL,
    PRIMARY KEY (periodo, codigo_ibge)
);
CREATE TABLE IF NOT EXISTS frota_veiculos (
    periodo TEXT NOT NULL,
    codigo_ibge INTEGER REFERENCES municipios NOT NULL,
    frota INTEGER NOT NULL CHECK (frota >= 0),
    PRIMARY KEY (periodo, codigo_ibge)
);
CREATE TABLE IF NOT EXISTS importacoes (
    periodo TEXT PRIMARY KEY,
    origem_icms TEXT NOT NULL,
    origem_frota TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS indicadores AS
SELECT periodo, codigo_ibge, municipio, icms, frota
FROM repasses_icms JOIN frota_veiculos USING (periodo, codigo_ibge)
JOIN municipios USING (codigo_ibge);
"""


def save_period(period, catalog, icms, frota, sources, db_path=DB):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(SCHEMA)
        with con:
            con.executemany(
                "INSERT INTO municipios VALUES (?, ?) ON CONFLICT(codigo_ibge) "
                "DO UPDATE SET municipio = excluded.municipio",
                catalog[["codigo_ibge", "municipio"]].itertuples(index=False, name=None),
            )
            for table, frame in (("repasses_icms", icms), ("frota_veiculos", frota)):
                con.execute(f"DELETE FROM {table} WHERE periodo = ?", (period,))
                con.executemany(
                    f"INSERT INTO {table} VALUES (?, ?, ?)",
                    ((period, code, value) for code, value in frame.itertuples(index=False, name=None)),
                )
            con.execute("INSERT OR REPLACE INTO importacoes VALUES (?, ?, ?)", (period, *sources))


def load_database(db_path=None):
    if db_path is None:
        db_path = DB if DB.exists() else LEGACY_DB
    if not db_path.exists():
        raise FileNotFoundError("Banco não encontrado. Execute python -m src.pipeline.")
    with closing(sqlite3.connect(db_path)) as con:
        return pd.read_sql_query("SELECT * FROM indicadores ORDER BY periodo, municipio", con)
