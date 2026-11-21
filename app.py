"""Painel Streamlit para exploração dos dados mensais no SQLite."""
import os
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from src.database import ROOT, load_database
from src.model import fit_linear, interpret_pearson, predict
from src.pipeline import IMPORT_ERRORS, import_all

LABELS = {"municipio": "Município", "frota": "Veículos", "icms": "ICMS bruto (R$)", "periodo": "Competência"}


def br(value, decimals=0):
    return f"{value:,.{decimals}f}".translate(str.maketrans(",.", ".,"))


st.set_page_config(page_title="Goiás | Inteligência Fiscal", layout="wide")
st.title("Inteligência Fiscal de Goiás")
st.caption("Repasses municipais de ICMS e frota de veículos")

published = os.environ.get("FISCAL_PUBLICADO") == "1"
if published:
    st.caption("Base oficial consolidada para demonstração.")
else:
    with st.sidebar:
        with st.expander("Importação de dados"):
            st.caption("Busca os arquivos oficiais de 2025 e usa também os repasses locais em data/raw.")
            offline = st.checkbox("Usar apenas arquivos locais")
            if st.button("Puxar todos os dados", key="import_all"):
                try:
                    with st.spinner("Buscando e cruzando os dados. O primeiro download pode levar alguns minutos."):
                        st.session_state.import_results = list(import_all(download=not offline))
                except IMPORT_ERRORS as exc:
                    st.session_state.import_results = []
                    st.error(str(exc))
            results = st.session_state.get("import_results", [])
            if results:
                imported = sum(count is not None for _, count, _ in results)
                st.write(f"{imported} de {len(results)} competências importadas.")
                for month, count, reason in results:
                    if count is None:
                        st.warning(f"{month} · {reason}")
                    else:
                        st.caption(f"{month} · {count} municípios")

try:
    data = load_database(ROOT / "data" / "demonstracao.sqlite3" if published else None)
except (OSError, sqlite3.Error, pd.errors.DatabaseError) as exc:
    st.warning(str(exc))
    st.stop()
if data.empty:
    st.warning("O banco está vazio. Execute a importação pelo terminal.")
    st.stop()

periods = sorted(data.periodo.unique(), reverse=True)
with st.sidebar:
    st.header("Filtros")
    period = st.selectbox("Competência", periods)
    sample = data[data.periodo.eq(period)]
    cities = st.multiselect("Municípios", sorted(sample.municipio.unique()), key=f"cities_{period}")
    st.caption("A regressão usa todos os municípios cruzados da competência selecionada.")

selected = sample[sample.municipio.isin(cities)] if cities else sample
history = data[data.municipio.isin(cities)] if cities else data

overview, analysis, records = st.tabs(["Visão geral", "Regressão e simulador", "Registros"])
with overview:
    a, b, c = st.columns(3)
    a.metric("Municípios no recorte", len(selected))
    b.metric("ICMS bruto no mês", f"R$ {br(selected.icms.sum(), 2)}")
    c.metric("Frota no mês", br(selected.frota.sum()))
    indicator = st.radio("Indicador dos gráficos", ["icms", "frota"], format_func=LABELS.get, horizontal=True)
    st.subheader("Municípios com os maiores valores")
    ranking = selected.nlargest(15, indicator).sort_values(indicator)
    st.plotly_chart(px.bar(ranking, x=indicator, y="municipio", orientation="h", labels=LABELS))
    st.subheader("Série mensal")
    monthly = history.groupby("periodo", as_index=False).agg(
        icms=("icms", "sum"), frota=("frota", "sum"), municipios=("municipio", "size")
    )
    monthly = pd.DataFrame({"periodo": pd.period_range(periods[-1], periods[0], freq="M").astype(str)}).merge(
        monthly, on="periodo", how="left"
    )
    st.plotly_chart(px.line(monthly, x="periodo", y=indicator, markers=True, labels=LABELS,
                            hover_data={"municipios": True}, title=LABELS[indicator]))
    st.caption("Cada ponto soma os municípios disponíveis no recorte. Meses sem importação aparecem como lacunas.")

with analysis:
    st.subheader(f"Frota e repasses de ICMS em {period}")
    try:
        result = fit_linear(sample)
    except ValueError as exc:
        st.warning(str(exc))
    else:
        a, b, c, d = st.columns(4)
        a.metric("Pearson", br(result["pearson"], 3))
        b.metric("R²", br(result["r2"], 3))
        c.metric("MAE (R$)", br(result["mae"], 2))
        d.metric("RMSE (R$)", br(result["rmse"], 2))
        st.caption(f"{result['n']} municípios · {interpret_pearson(result['pearson'])} · Erros calculados no ajuste.")
        chart = px.scatter(sample, x="frota", y="icms", hover_name="municipio", labels=LABELS)
        endpoints = [result["x_min"], result["x_max"]]
        chart.add_scatter(x=endpoints, y=[predict(result, x) for x in endpoints], mode="lines",
                          name="Reta OLS", line={"color": "#f6ad55", "width": 3})
        st.plotly_chart(chart)
        slope = result["inclinacao"]
        sign = "+" if slope >= 0 else "−"
        st.write(f"Ŷ = {br(result['intercepto'], 2)} {sign} {br(abs(slope), 4)} × X")
        st.caption("X representa veículos e Ŷ representa o ICMS bruto estimado em reais. A associação observada não estabelece causalidade.")
        st.subheader("Simulador de ICMS")
        with st.form(f"simulation_{period}"):
            vehicles = st.number_input("Quantidade de veículos", min_value=0, value=int(sample.frota.median()))
            st.form_submit_button("Calcular estimativa")
        st.metric(f"ICMS estimado para {br(vehicles)} veículos", f"R$ {br(predict(result, vehicles), 2)}")
        if not result["x_min"] <= vehicles <= result["x_max"]:
            st.warning(f"Extrapolação. A amostra contém de {br(endpoints[0])} a {br(endpoints[1])} veículos.")
        st.caption("Estimativa estatística para fins acadêmicos, sem caráter de previsão oficial.")

with records:
    st.subheader(f"Registros integrados de {period}")
    st.dataframe(selected, hide_index=True, column_config={
        "periodo": "Competência", "codigo_ibge": st.column_config.NumberColumn("Código IBGE", format="%d"),
        "municipio": "Município", "icms": st.column_config.NumberColumn("ICMS bruto (R$)", format="%.2f"),
        "frota": "Frota",
    })
    st.download_button("Baixar CSV do recorte", selected.to_csv(index=False).encode("utf-8-sig"),
                       f"indicadores_{period}.csv", "text/csv")

st.caption("Fontes oficiais · Economia de Goiás, DETRAN-GO e IBGE")
