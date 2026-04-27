import streamlit as st
import pandas as pd
import plotly.express as px
from bcb import sgs
import yfinance as yf
from datetime import datetime, timedelta

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Dashboard Macro FP&A - Vibra", layout="wide")

st.title("📊 Monitor de Indicadores Macroeconômicos")
st.markdown("Automated Data Pipeline | **MBA IA, Ciência de Dados e Big Data para Negócios**")

# --- 2. FUNÇÃO DE COLETA OTIMIZADA ---
@st.cache_data(ttl=3600)
def carregar_dados():
    # Coleta SGS - Banco Central
    codigos = {'IPCA': 433, 'SELIC': 432, 'Dólar': 10813, 'IGPM': 189}
    
    try:
        # Buscamos dados desde 2020
        df_sgs = sgs.get(codigos, start='2020-01-01')
        df_sgs.index = df_sgs.index.map(lambda x: x.replace(day=1))
    except Exception as e:
        st.error(f"Erro ao acessar Banco Central: {e}")
        return pd.DataFrame()

    # Coleta Brent - Yahoo Finance (Com lógica de Fallback para Nuvem)
    try:
        # Tentativa 1: Histórico completo
        brent_raw = yf.download('BZ=F', start='2020-01-01', progress=False)
        
        if isinstance(brent_raw.columns, pd.MultiIndex):
            brent_raw.columns = brent_raw.columns.get_level_values(0)
        
        if not brent_raw.empty:
            brent_series = brent_raw['Close'].resample('MS').mean()
            brent_series.name = 'Brent'
            
            # Garantia do último preço disponível (Spot Price)
            ultimo_preço_valido = brent_raw['Close'].dropna().iloc[-1]
        else:
            brent_series = pd.Series(name='Brent', dtype='float64')
    except Exception:
        brent_series = pd.Series(name='Brent', dtype='float64')

    # Merge Final
    df = pd.concat([df_sgs, brent_series], axis=1).reset_index()
    df.columns.values[0] = 'Periodo'
    
    # Preenchimento de lacunas (Data Wrangling)
    df = df.ffill().bfill()
    
    # Ajuste Técnico: Se o Brent do último mês falhou no merge, usamos o Spot Price
    if 'ultimo_preço_valido' in locals() and pd.isna(df.iloc[-1]['Brent']):
        df.loc[df.index[-1], 'Brent'] = ultimo_preço_valido
        
    return df

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

    # Gráficos
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Custos: Brent vs Câmbio")
        fig_custo = px.line(df_final, x='Periodo', y=['Brent', 'Dólar'],
                            labels={'value': 'Valor', 'Periodo': 'Período'},
                            color_discrete_map={'Brent': '#008751', 'Dólar': '#005291'})
        st.plotly_chart(fig_custo, use_container_width=True)

    with col_b:
        st.subheader("Inflação: IPCA vs IGPM")
        fig_inf = px.area(df_final, x='Periodo', y=['IPCA', 'IGPM'],
                          labels={'value': 'Variação %', 'Periodo': 'Período'})
        fig_inf.update_layout(barmode='overlay')
        st.plotly_chart(fig_inf, use_container_width=True)

    # Tabela
    with st.expander("Dados Consolidados"):
        st.dataframe(df_final.sort_values('Periodo', ascending=False), use_container_width=True)
else:
    st.error("Não foi possível carregar os dados. Verifique a conexão com as APIs.")