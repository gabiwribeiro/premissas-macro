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
    
    # Coleta do Banco Central (SGS)
    for tentativa in range(3):
        try:
            df_sgs = sgs.get(codigos, start='2020-01-01')
            if not df_sgs.empty:
                df_sgs.index = df_sgs.index.map(lambda x: x.replace(day=1))
                break 
        except Exception:
            time.sleep(2)
            continue

    # Coleta do Petróleo Brent (Yahoo Finance)
    try:
        brent_raw = yf.download('BZ=F', start='2020-01-01', progress=False)
        if isinstance(brent_raw.columns, pd.MultiIndex):
            brent_raw.columns = brent_raw.columns.get_level_values(0)
        
        if not brent_raw.empty:
            brent_series = brent_raw['Close'].resample('MS').mean()
            brent_series.name = 'Brent'
        else:
            brent_series = pd.Series(name='Brent', dtype='float64')
    except Exception:
        brent_series = pd.Series(name='Brent', dtype='float64')

    # Merge e Limpeza
    if not df_sgs.empty:
        df = pd.concat([df_sgs, brent_series], axis=1).reset_index()
        df.columns.values[0] = 'Periodo'
        df = df.ffill().bfill()
        return df
    return pd.DataFrame()

# --- 3. EXECUÇÃO ---
with st.spinner('Conectando às APIs financeiras...'):
    df_final = carregar_dados()

if not df_final.empty:
    # --- 4. KPIs (INDICADORES RESUMIDOS) ---
    # Função para garantir que não pegamos um valor 'nan' acidental no topo
    def get_last_valid(df, column):
        valid_series = df[column].dropna()
        return valid_series.iloc[-1] if not valid_series.empty else 0

    val_cambio = get_last_valid(df_final, 'Dólar')
    val_brent = get_last_valid(df_final, 'Brent')
    val_selic = get_last_valid(df_final, 'SELIC')
    val_ipca = get_last_valid(df_final, 'IPCA')

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Câmbio (USD/BRL)", f"R$ {val_cambio:.2f}")
    c2.metric("Petróleo Brent", f"U$ {val_brent:.2f}" if val_brent > 0 else "U$ --")
    c3.metric("SELIC Atual", f"{val_selic:.2f}%")
    c4.metric("IPCA (Mês)", f"{val_ipca:.2f}%")

    st.divider()

    # --- 5. GRÁFICOS ---
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Custos: Brent vs Câmbio")
        fig_custo = make_subplots(specs=[[{"secondary_y": True}]])
        fig_custo.add_trace(go.Scatter(x=df_final['Periodo'], y=df_final['Dólar'], name="Câmbio", line=dict(color='#005291', width=3)), secondary_y=False)
        fig_custo.add_trace(go.Scatter(x=df_final['Periodo'], y=df_final['Brent'], name="Brent", line=dict(color='#008751', width=3)), secondary_y=True)
        fig_custo.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_custo, use_container_width=True)

    with col_b:
        st.subheader("Inflação: IPCA vs IGPM")
        fig_inf = px.area(df_final, x='Periodo', y=['IPCA', 'IGPM'], color_discrete_map={'IPCA': '#005291', 'IGPM': '#FF4B4B'})
        fig_inf.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_inf, use_container_width=True)

    st.divider()

    # --- 6. TABELA CONSOLIDADA (HISTÓRICO + MENSAL 2026) ---
    st.subheader("📊 Premissas e Indicadores (Consolidado)")
    
    df_tab = df_final.copy()
    df_tab['Ano'] = df_tab['Periodo'].dt.year
    df_tab['Mes_Ref'] = df_tab['Periodo'].dt.strftime('%b/%y').str.lower()

    # Médias Anuais (2023-2025)
    df_anuais = df_tab[df_tab['Ano'].isin([2023, 2024, 2025])].groupby('Ano').mean(numeric_only=True).T
    df_anuais.columns = df_anuais.columns.astype(str)

    # Mensal 2026
    df_2026 = df_tab[df_tab['Ano'] == 2026].copy()
    if not df_2026.empty:
        df_2026 = df_2026.set_index('Mes_Ref').drop(columns=['Periodo', 'Ano']).T
    else:
        df_2026 = pd.DataFrame(index=df_anuais.index)

    # União das tabelas
    tabela_viz = pd.concat([df_anuais, df_2026], axis=1)
    tabela_viz.index.name = "Indicadores"

    # Função de formatação para valores financeiros vs taxas
    def formatar_valores(val):
        if pd.isna(val) or val == 0: return "-"
        if abs(val) > 15: return f"{val:,.2f}" # Dólar e Brent
        return f"{val:.2f}%" # IPCA, IGPM, SELIC

    # Exibição com destaque no maior valor de cada linha
    try:
        st.dataframe(
            tabela_viz.style.format(formatar_valores).highlight_max(axis=1, color='#e6f3ff'),
            use_container_width=True
        )
    except:
        st.dataframe(tabela_viz, use_container_width=True)

    st.caption("Fontes: Banco Central do Brasil (SGS) e Yahoo Finance. *Dados de 2026 atualizados conforme disponibilidade.*")

else:
    st.error("Não foi possível carregar os dados das APIs. Verifique sua conexão.")