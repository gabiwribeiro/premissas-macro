import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bcb import sgs
from datetime import datetime

# =====================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# =====================================================
st.set_page_config(
    page_title="Dashboard Macro FP&A - Vibra",
    layout="wide"
)

st.title("📊 Monitor de Indicadores Macroeconômicos")
st.markdown("""
Automated Data Pipeline  
**MBA IA, Ciência de Dados e Big Data para Negócios**
""")

# =====================================================
# 2. FUNÇÃO DE COLETA DE DADOS
# =====================================================
@st.cache_data(ttl=3600)
def carregar_dados():
    codigos = {
        "IPCA": 433,
        "IGPM": 189,
        "SELIC": 432,
        "Dólar": 10813
    }

    inicio = "2015-01-01"
    df = sgs.get(codigos, start=inicio)

    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    return df

df = carregar_dados()

if df.empty:
    st.error("Erro ao carregar dados do Banco Central.")
    st.stop()

# =====================================================
# 3. FUNÇÕES DE CÁLCULO CORRETAS
# =====================================================
def inflacao_anual_composta(df, coluna):
    """
    Calcula inflação anual corretamente usando capitalização composta.
    Retorna série em % anual.
    """
    return (
        (1 + df[coluna] / 100)
        .resample("Y")
        .prod()
        .sub(1)
        .mul(100)
    )

def inflacao_12m(df, coluna):
    """
    Inflação acumulada em 12 meses (YoY móvel).
    """
    return (
        (1 + df[coluna] / 100)
        .rolling(12)
        .apply(lambda x: x.prod() - 1)
        * 100
    )

def ultimo_valor(df, coluna):
    serie = df[coluna].dropna()
    return round(serie.iloc[-1], 2) if not serie.empty else None

# =====================================================
# 4. CÁLCULOS
# =====================================================
ipca_12m = inflacao_12m(df, "IPCA")
igpm_12m = inflacao_12m(df, "IGPM")

ipca_anual = inflacao_anual_composta(df, "IPCA")
igpm_anual = inflacao_anual_composta(df, "IGPM")

selic_atual = ultimo_valor(df, "SELIC")
dolar_atual = ultimo_valor(df, "Dólar")

# =====================================================
# 5. KPIs
# =====================================================
st.subheader("📌 Indicadores-Chave")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "IPCA 12 meses (%)",
    f"{ipca_12m.dropna().iloc[-1]:.2f}"
)

col2.metric(
    "IGP-M 12 meses (%)",
    f"{igpm_12m.dropna().iloc[-1]:.2f}"
)

col3.metric(
    "Taxa Selic (%)",
    f"{selic_atual:.2f}"
)

col4.metric(
    "Dólar (R$)",
    f"{dolar_atual:.2f}"
)

# =====================================================
# 6. GRÁFICO – INFLAÇÃO 12 MESES
# =====================================================
st.subheader("📈 Inflação acumulada em 12 meses")

fig1 = go.Figure()

fig1.add_trace(go.Scatter(
    x=ipca_12m.index,
    y=ipca_12m,
    name="IPCA 12m",
    line=dict(color="red")
))

fig1.add_trace(go.Scatter(
    x=igpm_12m.index,
    y=igpm_12m,
    name="IGP-M 12m",
    line=dict(color="blue")
))

fig1.update_layout(
    yaxis_title="%",
    template="plotly_white",
    legend_title="Indicador"
)

st.plotly_chart(fig1, use_container_width=True)

# =====================================================
# 7. GRÁFICO – INFLAÇÃO ANUAL CORRETA
# =====================================================
st.subheader("📊 Inflação Anual (cálculo correto)")

df_anual = pd.DataFrame({
    "IPCA": ipca_anual,
    "IGPM": igpm_anual
})

fig2 = px.bar(
    df_anual,
    barmode="group",
    labels={"value": "%", "index": "Ano"},
)

fig2.update_layout(
    template="plotly_white",
    legend_title="Indicador"
)

st.plotly_chart(fig2, use_container_width=True)

# =====================================================
# 8. TABELA DE DADOS
# =====================================================
st.subheader("📄 Base de dados")

st.dataframe(
    df.tail(15),
    use_container_width=True
)