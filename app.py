import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bcb import sgs
import yfinance as yf
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Macro FP&A - Vibra", layout="wide")

st.title("📊 Monitor de Indicadores Macroeconômicos")
st.markdown("Automated Data Pipeline | **MBA IA, Ciência de Dados e Big Data para Negócios**")

# --- 2. FUNÇÃO DE COLETA OTIMIZADA ---
@st.cache_data(ttl=3600)
def carregar_dados():
    # Coleta SGS - Banco Central
    codigos = {'IPCA': 433, 'SELIC': 432, 'Dólar': 10813, 'IGPM': 189}
    df_sgs = pd.DataFrame()
    
    for tentativa in range(3):
        try:
            df_sgs = sgs.get(codigos, start='2020-01-01')
            if not df_sgs.empty:
                df_sgs.index = df_sgs.index.map(lambda x: x.replace(day=1))
                break 
        except Exception as e:
            if tentativa < 2:
                time.sleep(2)
                continue
            else:
                st.error(f"O Banco Central está instável no momento.")
                return pd.DataFrame()

    # Coleta Brent (Yahoo Finance)
    try:
        brent_raw = yf.download('BZ=F', start='2020-01-01', progress=False)
        if isinstance(brent_raw.columns, pd.MultiIndex):
            brent_raw.columns = brent_raw.columns.get_level_values(0)
        
        ultimo_brent_real = brent_raw['Close'].dropna().iloc[-1]
        brent_series = brent_raw['Close'].resample('MS').mean()
        brent_series.name = 'Brent'
    except Exception:
        ultimo_brent_real = 0
        brent_series = pd.Series(name='Brent', dtype='float64')

    # Merge e padronização
    if not df_sgs.empty:
        df = pd.concat([df_sgs, brent_series], axis=1).reset_index()
        df.columns.values[0] = 'Periodo'
        df = df.ffill().bfill()
        
        if pd.isna(df.iloc[-1]['Brent']) and ultimo_brent_real > 0:
            df.loc[df.index[-1], 'Brent'] = ultimo_brent_real
        return df
    
    return pd.DataFrame()

# --- 3. EXECUÇÃO ---
with st.spinner('Conectando às APIs financeiras...'):
    df_final = carregar_dados()

if not df_final.empty:
    # --- KPIs ---
    ultimos = df_final.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Câmbio (USD/BRL)", f"R$ {ultimos['Dólar']:.2f}")
    c2.metric("Petróleo Brent", f"U$ {ultimos.get('Brent', 0):.2f}")
    c3.metric("SELIC Atual", f"{ultimos['SELIC']:.2f}%")
    c4.metric("IPCA (Mês)", f"{ultimos['IPCA']:.2f}%")

    st.divider()

    # --- GRÁFICOS ---
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Custos: Brent vs Câmbio (Eixos Distintos)")
        
        # Criar subplots com um eixo secundário
        fig_custo = make_subplots(specs=[[{"secondary_y": True}]])

        # Adicionar a linha do Dólar (Eixo Esquerdo)
        fig_custo.add_trace(
            go.Scatter(x=df_final['Periodo'], y=df_final['Dólar'], name="Câmbio (R$/US$)",
                       line=dict(color='#005291', width=3)),
            secondary_y=False,
        )

        # Adicionar a linha do Brent (Eixo Direito)
        fig_custo.add_trace(
            go.Scatter(x=df_final['Periodo'], y=df_final['Brent'], name="Brent (US$/bbl)",
                       line=dict(color='#008751', width=3)),
            secondary_y=True,
        )

        # Configurar títulos e legendas
        fig_custo.update_xaxes(title_text="Período")
        fig_custo.update_yaxes(title_text="<b>Câmbio</b> (R$/US$)", secondary_y=False)
        fig_custo.update_yaxes(title_text="<b>Brent</b> (US$/bbl)", secondary_y=True)
        fig_custo.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

        st.plotly_chart(fig_custo, use_container_width=True)

    with col_b:
        st.subheader("Inflação: IPCA vs IGPM")
        fig_inf = px.area(df_final, x='Periodo', y=['IPCA', 'IGPM'],
                          labels={'value': 'Variação %', 'Periodo': 'Período'},
                          color_discrete_map={'IPCA': '#005291', 'IGPM': '#FF4B4B'})
        fig_inf.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_inf, use_container_width=True)

    # --- TABELA ---
    with st.expander("Visualizar Dados Brutos"):
        st.dataframe(df_final.sort_values('Periodo', ascending=False), use_container_width=True)
else:
    st.error("Não foi possível carregar os dados. Verifique a conexão com as APIs.")