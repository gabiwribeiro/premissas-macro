import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bcb import sgs
import yfinance as yf
from datetime import datetime
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Macro FP&A - Vibra", layout="wide")

st.title("📊 Monitor de Indicadores Macroeconômicos")
st.markdown("Automated Data Pipeline | **MBA IA, Ciência de Dados e Big Data para Negócios**")

# --- 2. FUNÇÃO DE COLETA ---
@st.cache_data(ttl=3600)
def carregar_dados():
    codigos = {'IPCA': 433, 'SELIC': 432, 'Dólar': 10813, 'IGPM': 189}
    df_sgs = pd.DataFrame()
    
    for tentativa in range(3):
        try:
            df_sgs = sgs.get(codigos, start='2020-01-01')
            if not df_sgs.empty:
                df_sgs.index = df_sgs.index.map(lambda x: x.replace(day=1))
                break 
        except Exception:
            time.sleep(2)
            continue

    try:
        brent_raw = yf.download('BZ=F', start='2020-01-01', progress=False)
        if isinstance(brent_raw.columns, pd.MultiIndex):
            brent_raw.columns = brent_raw.columns.get_level_values(0)
        
        if not brent_raw.empty:
            ultimo_val = brent_raw['Close'].dropna().iloc[-1]
            brent_series = brent_raw['Close'].resample('MS').mean()
            brent_series.name = 'Brent'
        else:
            ultimo_val = 0
            brent_series = pd.Series(name='Brent', dtype='float64')
    except Exception:
        ultimo_val = 0
        brent_series = pd.Series(name='Brent', dtype='float64')

    if not df_sgs.empty:
        df = pd.concat([df_sgs, brent_series], axis=1).reset_index()
        df.columns.values[0] = 'Periodo'
        df = df.ffill().bfill()
        return df
    return pd.DataFrame()

# --- 3. EXECUÇÃO ---
df_final = carregar_dados()

if not df_final.empty:
    # Gráficos (mantendo a lógica anterior)
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Custos: Brent vs Câmbio")
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=df_final['Periodo'], y=df_final['Dólar'], name="Dólar"), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_final['Periodo'], y=df_final['Brent'], name="Brent"), secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
    
    with col_b:
        st.subheader("Inflação: IPCA vs IGPM")
        fig_inf = px.area(df_final, x='Periodo', y=['IPCA', 'IGPM'])
        st.plotly_chart(fig_inf, use_container_width=True)

    st.divider()

    # --- 4. CONSTRUÇÃO DA TABELA (AJUSTE PARA EVITAR KEYERROR) ---
    st.subheader("📊 Premissas e Indicadores (Consolidado)")

    df_tab = df_final.copy()
    df_tab['Ano'] = df_tab['Periodo'].dt.year
    df_tab['Mes_Ref'] = df_tab['Periodo'].dt.strftime('%b/%y').str.lower()

    # Criando as médias anuais
    df_anuais = df_tab[df_tab['Ano'].isin([2023, 2024, 2025])].groupby('Ano').mean(numeric_only=True).T
    df_anuais.columns = df_anuais.columns.astype(str)

    # Criando o mensal de 2026
    df_2026 = df_tab[df_tab['Ano'] == 2026].copy()
    if not df_2026.empty:
        df_2026 = df_2026.set_index('Mes_Ref').drop(columns=['Periodo', 'Ano']).T
    else:
        df_2026 = pd.DataFrame(index=df_anuais.index)

    # Concatenando
    tabela_viz = pd.concat([df_anuais, df_2026], axis=1)
    
    # TRUQUE DE SEGURANÇA: Resetar o nome dos índices para evitar conflitos no Styler
    tabela_viz.index.name = None
    tabela_viz.columns.name = None

    # Função de formatação robusta
    def formatar_estilo(val):
        if pd.isna(val) or val == 0: return "-"
        if abs(val) > 15: return f"{val:,.2f}" # Brent e Dólar
        return f"{val:.2f}%" # Índices

    # Aplicação do Style com tratamento de erro
    try:
        styler = tabela_viz.style.format(formatar_estilo).highlight_max(axis=1, color='#e6f3ff')
        st.dataframe(styler, use_container_width=True)
    except Exception:
        # Caso o Style ainda dê erro de índice, mostra a tabela pura para não travar o app
        st.dataframe(tabela_viz, use_container_width=True)

    st.caption("Fontes: Banco Central do Brasil (SGS) e Yahoo Finance.")