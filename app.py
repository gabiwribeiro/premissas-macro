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
    # 1. Coleta SGS - Banco Central (Com Lógica de Re-tentativa e Timeout)
    codigos = {'IPCA': 433, 'SELIC': 432, 'Dólar': 10813, 'IGPM': 189}
    df_sgs = pd.DataFrame()
    
    # Tentamos até 3 vezes antes de desistir
    for tentativa in range(3):
        try:
            # Puxamos os dados - O banco central às vezes demora a responder na nuvem
            df_sgs = sgs.get(codigos, start='2020-01-01')
            if not df_sgs.empty:
                df_sgs.index = df_sgs.index.map(lambda x: x.replace(day=1))
                break # Sucesso! Sai do loop de tentativas
        except Exception as e:
            if tentativa < 2: # Se não for a última tentativa, espera 2 segundos e tenta de novo
                import time
                time.sleep(2)
                continue
            else:
                st.error(f"O Banco Central está instável no momento (Timeout). Tentaremos novamente em breve.")
                return pd.DataFrame()

    # 2. Coleta Brent (Yahoo Finance) - Geralmente mais estável
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

    # Merge e padronização (Só faz se o SGS trouxe dados)
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