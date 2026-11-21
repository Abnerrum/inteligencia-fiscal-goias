"""Importa o ICMS bruto e a frota do DETRAN-GO por competência mensal."""
import argparse
import io
import json
from pathlib import Path
import re
import sqlite3
from tempfile import NamedTemporaryFile
import unicodedata
import zipfile

import numpy as np
import pandas as pd
import requests

from .database import ROOT, load_database, save_period

RAW = ROOT / "data" / "raw"
MONTH = "2025-07"
PORTAL = "https://dadosabertos.go.gov.br"
IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/52/municipios"
ICMS_2025 = f"{PORTAL}/dataset/cd82f643-f203-41d9-9542-9250df93cd14/resource/2b247d3c-0299-4b50-a7a9-2040f1cf9099/download/repasses_municipios_ano_2025.zip"
MUNICIPAL_ALIASES = {"BOM_JESUS": "BOM_JESUS_DE_GOIAS"}
FROTA_IDS = {
    "202501": "36276936-a3c1-4969-a5bb-e1a1af4edf3f",
    "202502": "59846bf4-1698-47ab-846d-7c388087424b",
    "202503": "a4436a4d-0fe0-4341-895e-e5f2f9b8c2a4",
    "202504": "b0d6fb62-cf6e-462d-9188-184f103c14eb",
    "202505": "f295dbd4-d6b1-4cca-9fb2-8d75f41d208e",
    "202506": "bf411323-a8d1-4f4b-b778-10579e42a02f",
    "202507": "c1bef0cc-f624-4576-9cc8-00ef5b057c5a",
    "202508": "0e69dc91-de3c-465c-8ec8-2bcb1b9d95fc",
    "202510": "878c7c6d-995b-4674-a228-b85627b0f8df",
    "202511": "e0168448-8f70-48c0-9859-1fc29ac489d7",
    "202512": "0037a7ef-35e4-4f34-bcc9-8c7713db7ed5",
}


def clean_key(value):
    if pd.isna(value):
        return ""
    plain = unicodedata.normalize("NFKD", str(value))
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", "_", plain.upper()).strip("_")


def read_table(path, content=None):
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        frame = pd.read_excel(path, dtype=str)
    elif path.suffix.lower() == ".csv":
        content = path.read_bytes() if content is None else content
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = content.decode("cp1252")
        frame = pd.read_csv(io.StringIO(decoded), sep=None, engine="python", dtype=str)
    else:
        raise ValueError("Use um arquivo CSV ou XLSX.")
    frame.columns = frame.columns.map(clean_key)
    if not frame.columns.is_unique or len(frame.columns) < 2 or frame.empty:
        raise ValueError(f"Estrutura inválida em {path.name}. Colunas: {frame.columns.tolist()}")
    return frame


def number(series):
    values = series.astype("string").str.strip().str.replace(r"R\$|\s", "", regex=True)
    brazilian = values.str.contains(",", regex=False, na=False)
    values = values.mask(brazilian, values.str.replace(".", "", regex=False))
    return pd.to_numeric(values.str.replace(",", ".", regex=False), errors="coerce")


def find_column(frame, options):
    for col in options:
        if col in frame:
            return col
    raise ValueError(f"Coluna esperada: {options}. Colunas recebidas: {frame.columns.tolist()}")


def download_file(path, url):
    try:
        response = requests.get(url, timeout=(10, 90))
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Falha ao baixar {path.name}. Use a importação manual. {exc}") from exc
    if not response.content or response.content.lstrip().startswith(b"<"):
        raise ValueError(f"A fonte não retornou dados para {path.name}.")
    path.parent.mkdir(exist_ok=True, parents=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        handle.write(response.content)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def load_catalog(download):
    path = RAW / "municipios_go.json"
    if not path.exists() and download:
        download_file(path, IBGE)
    catalog = pd.DataFrame(json.loads(path.read_text(encoding="utf-8-sig")))[["id", "nome"]]
    catalog.columns = ["codigo_ibge", "municipio"]
    catalog["chave"] = catalog.municipio.map(clean_key)
    if len(catalog) != 246 or not catalog.chave.is_unique or not catalog.codigo_ibge.is_unique:
        raise ValueError("O catálogo do IBGE deve conter os 246 municípios de Goiás.")
    return catalog


def get_table(kind, month, explicit, download):
    stamp = month.replace("-", "")
    if explicit:
        return read_table(explicit), str(explicit)
    for suffix in (".csv", ".xlsx"):
        path = RAW / f"{kind}_{stamp}{suffix}"
        if path.exists():
            return read_table(path), path.relative_to(ROOT).as_posix()
    if kind == "icms":
        member = f"RepassesMunicipios{stamp}.csv"
        direct = RAW / f"repasses{stamp[:4]}" / member
        if direct.exists():
            return read_table(direct), direct.relative_to(ROOT).as_posix()
        archive_path = RAW / f"repasses_municipios_ano_{stamp[:4]}.zip"
        if not archive_path.exists() and download and stamp.startswith("2025"):
            download_file(archive_path, ICMS_2025)
        if archive_path.exists():
            with zipfile.ZipFile(archive_path) as archive:
                for name in archive.namelist():
                    if Path(name).name.lower() == member.lower():
                        return read_table(member, archive.read(name)), f"{archive_path.name}/{name}"
    elif download and stamp in FROTA_IDS:
        url = (f"{PORTAL}/dataset/63d3d2c3-d12a-4c70-9706-94814772773e/"
               f"resource/{FROTA_IDS[stamp]}/download/da_frota_{stamp}.csv")
        path = RAW / f"frota_{stamp}.csv"
        download_file(path, url)
        return read_table(path), url
    raise FileNotFoundError(f"Informe --{kind} ou adicione data/raw/{kind}_{stamp}.csv ou .xlsx.")


def prepare_month(frame, catalog, month, kind):
    for col in ("ANO_MES_REPASSE", "NUMR_ANO_MES", "ANO_MES", "PERIODO", "COMPETENCIA"):
        if col in frame:
            periods = frame[col].astype("string").str.strip().str.replace("-", "", regex=False)
            if not periods.eq(month.replace("-", "")).fillna(False).all():
                raise ValueError(f"{kind}: {col} contém registros fora de {month} ou sem competência.")


    value_col = find_column(frame, ("VALOR_BRUTO_ICMS", "VALOR_BRUTO_DO_ICMS") if kind == "icms"
                            else ("QTD", "QUANTIDADE", "TOTAL"))
    name_col = find_column(frame, ("NOME_MUNICIPIO", "MUNICIPIO", "NOME_DO_MUNICIPIO", "DESC_MUN"))
    # The fleet source has repeated visible attributes and no source record ID.
    rows = frame.drop_duplicates() if kind == "icms" else frame
    keys = rows[name_col].map(clean_key).replace(MUNICIPAL_ALIASES)
    codes = keys.map(catalog.set_index("chave").codigo_ibge)
    unknown = sorted(keys[codes.isna()].unique())
    print(f"{kind}: {len(frame) - len(rows)} duplicatas removidas; municípios sem código: {unknown}")

    values = number(rows[value_col])
    valid = np.isfinite(values.fillna(np.nan))
    if kind == "frota":
        valid &= values.ge(0) & values.mod(1).eq(0)
    if (~valid & codes.notna()).any():
        raise ValueError(f"{kind}: há valores ausentes ou inválidos em municípios de Goiás.")
    records = pd.DataFrame({"codigo_ibge": codes[codes.notna()].astype(int), kind: values[codes.notna()]})
    if kind == "frota":
        records[kind] = records[kind].astype("int64")
    return records.groupby("codigo_ibge", as_index=False)[kind].sum()


def build_database(icms_file=None, frota_file=None, download=True, *, month=MONTH, db_path=None):
    if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("Informe a competência no formato AAAA-MM.")
    catalog = load_catalog(download)
    a, source_a = get_table("icms", month, icms_file, download)
    icms = prepare_month(a, catalog, month, "icms")
    b, source_b = get_table("frota", month, frota_file, download)
    frota = prepare_month(b, catalog, month, "frota")
    joined = icms.merge(frota, on="codigo_ibge", validate="one_to_one")
    if len(joined) < 3:
        raise ValueError(f"Cruzamento insuficiente: {len(joined)} municípios em {month}.")
    save_period(month, catalog, icms, frota, (source_a, source_b), **({"db_path": db_path} if db_path else {}))
    print(f"{month}: {len(icms)} municípios com ICMS, {len(frota)} com frota, {len(joined)} cruzados.")
    joined.insert(0, "periodo", month)
    return joined.merge(catalog[["codigo_ibge", "municipio"]], on="codigo_ibge", validate="one_to_one")


IMPORT_ERRORS = (ValueError, OSError, sqlite3.Error, zipfile.BadZipFile)


def available_periods(download=True):
    """Lista competências do catálogo de 2025 e dos arquivos de repasses locais."""
    stamps = {f"2025{month:02d}" for month in range(1, 13)} if download else set()
    names = [path.name for path in RAW.glob("icms_*")]
    names.extend(path.name for path in RAW.glob("repasses*/RepassesMunicipios*.csv"))
    for path in RAW.glob("repasses_municipios_ano_*.zip"):
        try:
            with zipfile.ZipFile(path) as archive:
                names.extend(Path(name).name for name in archive.namelist())
        except zipfile.BadZipFile as exc:
            raise ValueError(f"ZIP de repasses inválido: {path.name}") from exc
    for name in names:
        match = re.fullmatch(r"(?:icms_|RepassesMunicipios)([0-9]{4}(?:0[1-9]|1[0-2]))\.(?:csv|xlsx)",
                             name, flags=re.IGNORECASE)
        if match:
            stamps.add(match[1])
    return [f"{stamp[:4]}-{stamp[4:]}" for stamp in sorted(stamps)]


def import_all(download=True):
    periods = available_periods(download)
    if not periods:
        raise ValueError("Nenhum arquivo de repasses encontrado para importar.")
    for period in periods:
        try:
            records = build_database(download=download, month=period)
        except IMPORT_ERRORS as exc:
            yield period, None, str(exc)
        else:
            yield period, len(records), ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--periodo")
    selection.add_argument("--todos", action="store_true", help="Importa as competências oficiais de 2025 e os repasses locais.")
    parser.add_argument("--icms", type=Path)
    parser.add_argument("--frota", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.todos and (args.icms or args.frota):
        parser.error("Com --todos, coloque os arquivos mensais em data/raw usando os nomes do README.")
    try:
        if args.todos:
            imported = 0
            skipped = 0
            for period, count, reason in import_all(not args.offline):
                if count is None:
                    print(f"{period} não importado: {reason}")
                    skipped += 1
                else:
                    imported += 1
            print(f"{imported} competências importadas; {skipped} não importadas.")
            if not imported:
                parser.exit(1)
        else:
            build_database(args.icms, args.frota, not args.offline, month=args.periodo or MONTH)
    except IMPORT_ERRORS as exc:
        parser.exit(1, f"Erro de importação: {exc}\n")


if __name__ == "__main__":
    main()


