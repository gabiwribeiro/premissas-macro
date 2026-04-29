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

# --- 2. FUNÇÃO DE COLETA OTIMIZADA ---
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
        
        # Garantir que temos dados antes de prosseguir
        if not brent_raw.empty:
            ultimo_brent_real = brent_raw['Close'].dropna().iloc[-1]
            brent_series = brent_raw['Close'].resample('MS').mean()
            brent_series.name = 'Brent'
        else:
            ultimo_brent_real = 0
            brent_series = pd.Series(name='Brent', dtype='float64')
    except Exception:
        ultimo_brent_real = 0
        brent_series = pd.Series(name='Brent', dtype='float64')

    if not df_sgs.empty:
        df = pd.concat([df_sgs, brent_series], axis=1).reset_index()
        df.columns.values[0] = 'Periodo'
        df = df.ffill().bfill()
        if 'Brent' in df.columns and pd.isna(df.iloc[-1]['Brent']) and ultimo_brent_real > 0:
            df.loc[df.index[-1], 'Brent'] = ultimo_brent_real
        return df
    return pd.DataFrame()

# --- 3. EXECUÇÃO ---
with st.spinner('Conectando às APIs financeiras...'):
    df_final = carregar_dados()

if not df_final.empty:
    # KPIs
    ultimos = df_final.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Câmbio (USD/BRL)", f"R$ {ultimos['Dólar']:.2f}")
    c2.metric("Petróleo Brent", f"U$ {ultimos.get('Brent', 0):.2f}")
    c3.metric("SELIC Atual", f"{ultimos['SELIC']:.2f}%")
    c4.metric("IPCA (Mês)", f"{ultimos['IPCA']:.2f}%")

    st.divider()

    # --- 4. GRÁFICOS ---
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Custos: Brent vs Câmbio")
        fig_custo = make_subplots(specs=[[{"secondary_y": True}]])
        fig_custo.add_trace(go.Scatter(x=df_final['Periodo'], y=df_final['Dólar'], name="Câmbio", line=dict(color='#005291', width=3)), secondary_y=False)
        fig_custo.add_trace(go.Scatter(x=df_final['Periodo'], y=df_final['Brent'], name="Brent", line=dict(color='#008751', width=3)), secondary_y=True)
        st.plotly_chart(fig_custo, use_container_width=True)

    with col_b:
        st.subheader("Inflação: IPCA vs IGPM")
        fig_inf = px.area(df_final, x='Periodo', y=['IPCA', 'IGPM'], color_discrete_map={'IPCA': '#005291', 'IGPM': '#FF4B4B'})
        st.plotly_chart(fig_inf, use_container_width=True)

    st.divider()

    # --- 5. TABELA DE VISUALIZAÇÃO (CORRIGIDA) ---
    st.subheader("📊 Premissas e Indicadores (Consolidado)")
    
    df_tab = df_final.copy()
    df_tab['Ano'] = df_tab['Periodo'].dt.year
    df_tab['Mes_Ref'] = df_tab['Periodo'].dt.strftime('%b/%y').str.lower()

    # Médias Anuais e Mensais de 2026
    df_anuais = df_tab[df_tab['Ano'].isin([2023, 2024, 2025])].groupby('Ano').mean(numeric_only=True).T
    df_anuais.columns = [str(col) for col in df_anuais.columns]
    
    df_2026 = df_tab[df_tab['Ano'] == 2026].set_index('Mes_Ref').drop(columns=['Periodo', 'Ano']).T
    
    tabela_final = pd.concat([df_anuais, df_2026], axis=1)

    def formatar_valores(val):
        if pd.isna(val): return "-"
        if abs(val) > 30: return f"{val:,.2f}" # Dólar e Brent
        return f"{val:.2f}%" # Taxas

    # Aplicação segura do estilo
    styler = tabela_final.style.format(formatar_valores)
    
    # Só destaca o máximo se houver dados na tabela
    if not tabela_final.empty:
        styler = styler.highlight_max(axis=1, color='#e6f3ff')

    st.dataframe(styler, use_container_width=True)

    st.caption("Fontes: Banco Central do Brasil (SGS) e Yahoo Finance.")

else:
    st.error("Não foi possível carregar os dados. Verifique a conexão com as APIs.")