import streamlit as st
import pandas as pd
import plotly.express as px
from bcb import sgs, Expectativas
import yfinance as yf

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Dashboard Macro FP&A - Vibra", layout="wide")

st.title("📊 Monitor de Indicadores Macroeconômicos")
st.markdown("Automated Data Pipeline | **MBA IA, Ciência de Dados e Big Data para Negócios**")

# --- 2. FUNÇÃO DE COLETA COM TRATAMENTO DE ERROS ---
@st.cache_data(ttl=3600)
def carregar_dados():
    # 1. Coleta SGS - Banco Central
    codigos = {'IPCA': 433, 'SELIC': 432, 'Dólar': 10813, 'IGPM': 189, 'PIB': 4380}
    try:
        df_sgs = sgs.get(codigos, start='2020-01-01')
        df_sgs.index = df_sgs.index.map(lambda x: x.replace(day=1))
    except Exception:
        return pd.DataFrame()

    # 2. Coleta Brent (Ajustado para ser mais resiliente na nuvem)
    try:
        # Pedimos um período maior (1mo) para garantir que o 'Close' mais recente venha
        brent_raw = yf.download('BZ=F', period='1mo', interval='1d', progress=False)
        
        if isinstance(brent_raw.columns, pd.MultiIndex):
            brent_raw.columns = brent_raw.columns.get_level_values(0)
        
        # Pegamos o último fechamento válido (não nulo)
        ultimo_brent = brent_raw['Close'].dropna().iloc[-1]
        
        # Criamos a série mensal para o gráfico, mas garantimos o valor do KPI
        brent_hist = yf.download('BZ=F', start='2020-01-01', progress=False)
        if isinstance(brent_hist.columns, pd.MultiIndex):
            brent_hist.columns = brent_hist.columns.get_level_values(0)
            
        brent_series = brent_hist['Close'].resample('MS').mean()
        brent_series.name = 'Brent'
    except Exception:
        brent_series = pd.Series(name='Brent', dtype='float64')

    # Merge e padronização
    df = pd.concat([df_sgs, brent_series], axis=1).reset_index()
    df.columns.values[0] = 'Periodo'
    df = df.ffill()
    
    # Se o valor do último mês no merge ficar vazio, forçamos o último valor real do Brent
    if pd.isna(df.iloc[-1]['Brent']) and 'ultimo_brent' in locals():
        df.loc[df.index[-1], 'Brent'] = ultimo_brent
        
    return df

# --- 3. PROCESSAMENTO ---
df_final = carregar_dados()

if not df_final.empty:
    # KPIs de topo
    ultimos = df_final.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Câmbio (USD/BRL)", f"R$ {ultimos['Dólar']:.2f}")
    c2.metric("Petróleo Brent", f"U$ {ultimos['Brent']:.2f}")
    c3.metric("SELIC Atual", f"{ultimos['SELIC']:.2f}%")
    c4.metric("IPCA (Mês)", f"{ultimos['IPCA']:.2f}%")

    st.divider()

    # --- 4. GRÁFICOS INTERATIVOS ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Custos: Brent vs Câmbio")
        fig_custo = px.line(df_final, x='Periodo', y=['Brent', 'Dólar'],
                            labels={'value': 'Valor', 'Periodo': 'Mês/Ano'},
                            color_discrete_map={'Brent': '#008751', 'Dólar': '#005291'})
        st.plotly_chart(fig_custo, use_container_width=True)

    with col_b:
        st.subheader("Inflação: IPCA vs IGPM")
        # Criamos o gráfico de área e depois ajustamos o layout para overlay
        fig_inf = px.area(df_final, x='Periodo', y=['IPCA', 'IGPM'],
                          labels={'value': 'Variação %', 'Periodo': 'Mês/Ano'})
        
        # O pulo do gato: barmode='overlay' no update_layout para não dar erro de TypeError
        fig_inf.update_layout(barmode='overlay')
        st.plotly_chart(fig_inf, use_container_width=True)

    # --- 5. TABELA E EXPORTAÇÃO ---
    with st.expander("Ver base de dados completa e exportar"):
        st.dataframe(df_final.sort_values('Periodo', ascending=False), use_container_width=True)
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Planilha (CSV)", csv, "dados_macro.csv", "text/csv")
else:
    st.warning("Aguardando conexão com as APIs...")