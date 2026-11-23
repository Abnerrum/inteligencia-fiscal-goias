"""Painel Streamlit para exploração dos dados mensais no SQLite."""
import os
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.database import ROOT, load_database
from src.model import fit_linear, interpret_pearson, predict, project_trend
from src.pipeline import IMPORT_ERRORS, import_all

LABELS = {"municipio": "Município", "frota": "Veículos", "icms": "ICMS bruto (R$)", "periodo": "Competência"}


def br(value, decimals=0):
    return f"{value:,.{decimals}f}".translate(str.maketrans(",.", ".,"))


st.set_page_config(page_title="Goiás | Inteligência Fiscal", layout="wide")
st.markdown("""
<style>
.stApp {background:radial-gradient(ellipse at 12% 0%,#133645 0%,#0b1e2d 46%,#081321 100%);}
[data-testid="stSidebar"] {background:#0c2130;border-right:1px solid #245268;}
.block-container {max-width:1440px;padding-top:1.3rem;}
.fiscal-hero {border:1px solid #326575;border-radius:22px;padding:24px 30px;margin-bottom:24px;
 background:linear-gradient(110deg,#103f43,#102d47 65%,#19304b);
 box-shadow:0 16px 40px #0005;animation:appear .8s ease-out both;}
.fiscal-brand {display:flex;gap:22px;align-items:center;flex-wrap:wrap;}
.fiscal-flags {display:flex;gap:13px;align-items:center;}
.fiscal-flag {width:86px;height:58px;display:block;border-radius:5px;overflow:hidden;
 box-shadow:0 7px 20px #0008;transform-origin:10% 50%;
 animation:wave 4.2s ease-in-out infinite;}
.fiscal-flag.go {animation-delay:-1.9s;}
.fiscal-hero h1 {font-weight:800;color:#fff;margin:3px 0;font-size:clamp(1.4rem,3vw,2.3rem);}
.fiscal-hero p {margin:0;color:#c1dde0;}
.fiscal-kicker {font-size:.72rem;letter-spacing:.16em;color:#8aecc2;font-weight:800;}
[data-testid="stMetric"] {background:#123042;border:1px solid #2b5869;border-radius:16px;
 padding:17px 20px;box-shadow:0 8px 24px #0002;transition:transform .25s,border-color .25s;animation:appear .65s both;}
[data-testid="stMetric"]:hover {transform:translateY(-4px);border-color:#36b7a4;}
[data-testid="stMetricValue"] {color:#e8fbfa;}
div[data-testid="stTabs"] button[aria-selected="true"] {color:#69e3c4;}
@keyframes wave {0%,100%{transform:perspective(260px) rotateY(-8deg) skewY(0deg)}
 50%{transform:perspective(260px) rotateY(9deg) skewY(-2deg)}}
@keyframes appear {from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:650px){.fiscal-hero{padding:20px}.fiscal-flag{width:62px;height:43px}}
@media(prefers-reduced-motion:reduce){.fiscal-flag,.fiscal-hero,[data-testid="stMetric"]{animation:none!important;transition:none!important}}
</style>
<div class="fiscal-hero">
  <div class="fiscal-brand">
    <div class="fiscal-flags">
      <svg class="fiscal-flag" viewBox="0 0 100 70" role="img" aria-label="Bandeira do Brasil">
        <rect width="100" height="70" fill="#159447"/>
        <path d="M50 7L94 35 50 63 6 35Z" fill="#f8da28"/>
        <circle cx="50" cy="35" r="20" fill="#194d92"/>
        <path d="M31 31 Q50 23 69 34" stroke="#fff" stroke-width="5" fill="none"/>
        <g fill="#fff"><circle cx="50" cy="38" r="1.5"/><circle cx="60" cy="42" r="1.3"/><circle cx="42" cy="45" r="1.1"/><circle cx="54" cy="47" r="1.1"/></g>
      </svg>
      <svg class="fiscal-flag go" viewBox="0 0 100 70" role="img" aria-label="Bandeira de Goiás">
        <rect width="100" height="70" fill="#07864a"/>
        <path d="M0 9H100V18H0ZM0 27H100V36H0ZM0 45H100V54H0ZM0 63H100V70H0Z" fill="#ffde28"/>
        <rect width="39" height="36" fill="#2059a6"/>
        <g fill="#fff"><circle cx="12" cy="11" r="2"/><circle cx="26" cy="11" r="2"/><circle cx="19" cy="18" r="2"/><circle cx="12" cy="25" r="2"/><circle cx="26" cy="25" r="2"/></g>
      </svg>
    </div>
    <div><div class="fiscal-kicker">BRASIL · ESTADO DE GOIÁS</div>
      <h1>Inteligência Fiscal de Goiás</h1>
      <p>Repasses municipais de ICMS, frota e análise estatística · Dados públicos</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

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
    sample = data[data.periodo.eq(period)] # type: ignore
    cities = st.multiselect("Municípios", sorted(sample.municipio.unique()), key=f"cities_{period}")
    st.caption("A regressão usa todos os municípios cruzados da competência selecionada.")

selected = sample[sample.municipio.isin(cities)] if cities else sample
history = data[data.municipio.isin(cities)] if cities else data

overview, analysis, records, forecast = st.tabs(["Visão geral", "Regressão e simulador", "Registros", "Previsões"])
with overview:
    a, b, c = st.columns(3)
    a.metric("Municípios no recorte", len(selected))
    b.metric("ICMS bruto no mês", f"R$ {br(selected.icms.sum(), 2)}")
    c.metric("Frota no mês", br(selected.frota.sum()))
    indicator = st.radio("Indicador dos gráficos", ["icms", "frota"], format_func=LABELS.get, horizontal=True)
    st.subheader("Municípios com os maiores valores")
    ranking = selected.nlargest(15, indicator).sort_values(indicator)
    fig_rank = px.bar(ranking, x=indicator, y="municipio", orientation="h", labels=LABELS, color_discrete_sequence=["#38bfa8"])
    fig_rank.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=8,r=12,t=16,b=20))
    st.plotly_chart(fig_rank, use_container_width=True)
    st.subheader("Série mensal")
    monthly = history.groupby("periodo", as_index=False).agg(
        icms=("icms", "sum"), frota=("frota", "sum"), municipios=("municipio", "size")
    )
    monthly = pd.DataFrame({"periodo": pd.period_range(periods[-1], periods[0], freq="M").astype(str)}).merge(
        monthly, on="periodo", how="left"
    )
    fig_month = px.line(monthly, x="periodo", y=indicator, markers=True, labels=LABELS,
                            hover_data={"municipios": True}, title=LABELS[indicator])
    fig_month.update_traces(line_color="#35cdb5", line_width=3)
    fig_month.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_month, use_container_width=True)
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
        chart.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(chart, use_container_width=True)
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

with forecast:
    st.subheader("Previsões para os próximos 12 meses")
    scope = "os municípios selecionados" if cities else "o total do estado"
    st.caption(f"Projeção calculada para {scope} com toda a série importada. O filtro de competência não altera este gráfico.")
    try:
        if len(monthly) < 6 or monthly.municipios.nunique(dropna=False) != 1:
            raise ValueError("A projeção requer pelo menos seis meses seguidos com os mesmos municípios.")
        # Mesmos cenários do relatório: a tendência recente descarta os dois primeiros meses.
        recent = f"Tendência desde {monthly.periodo.iloc[2]}"
        scenarios = {
            "frota": [("Tendência (OLS)", project_trend(monthly.frota), "#5aa9ff", "dash")],
            "icms": [
                ("Estável", [monthly.icms.iloc[-1]] * 12, "#5aa9ff", "dash"),
                (recent, project_trend(monthly.icms, skip=2), "#35cdb5", "dashdot"),
                ("Tendência da série completa", project_trend(monthly.icms), "#f6ad55", "dot"),
            ],
        }
    except ValueError as exc:
        st.info(str(exc))
    else:
        last = monthly.periodo.iloc[-1]
        future = pd.period_range(pd.Period(last, freq="M") + 1, periods=12, freq="M").astype(str).tolist()
        summary = []
        for field in ("frota", "icms"):
            fig = go.Figure(go.Scatter(x=monthly.periodo, y=monthly[field], name="Observado", mode="lines+markers",
                                       line={"color": "#e8fbfa", "width": 2}))
            for name, values, color, dash in scenarios[field]:
                # O primeiro ponto repete o último observado para ligar as linhas.
                fig.add_scatter(x=[last, *future], y=[monthly[field].iloc[-1], *values], name=name,
                                mode="lines", line={"color": color, "width": 2, "dash": dash})
                summary.append({"Indicador": LABELS[field], "Cenário": name,
                                f"Valor em {future[-1]}": br(values[-1]),
                                "Soma dos 12 meses": br(sum(values)) if field == "icms" else "—"})
            fig.add_vrect(x0=last, x1=future[-1], fillcolor="#ffffff", opacity=0.06, line_width=0, layer="below")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              title=LABELS[field], hovermode="x unified", separators=",.",
                              legend={"orientation": "h", "y": -0.2})
            fig.update_xaxes(type="category")
            fig.update_yaxes(tickformat=",.0f", hoverformat=",.0f")
            st.plotly_chart(fig, use_container_width=True, key=f"forecast_{field}")
        st.dataframe(pd.DataFrame(summary), hide_index=True)
        st.caption("A área sombreada é a projeção. Os eixos verticais não começam em zero. Uma série de um ano não separa "
                   "sazonalidade de tendência, por isso o ICMS aparece em cenários e o da série completa é um limite alto. "
                   "Valores nominais, para fins acadêmicos, sem caráter de previsão oficial.")

st.caption("Fontes oficiais · Economia de Goiás, DETRAN-GO e IBGE")
