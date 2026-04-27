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
    # Coleta SGS - Banco Central
    codigos = {'IPCA': 433, 'SELIC': 432, 'Dólar': 10813, 'IGPM': 189, 'PIB': 4380}
    try:
        df_sgs = sgs.get(codigos, start='2020-01-01')
        # Padroniza o índice para o primeiro dia do mês
        df_sgs.index = df_sgs.index.map(lambda x: x.replace(day=1))
    except Exception as e:
        st.error(f"Erro no Banco Central: {e}")
        return pd.DataFrame()

    # Coleta Brent - Yahoo Finance
    try:
        brent_raw = yf.download('BZ=F', start='2020-01-01', progress=False)
        # Ajuste para MultiIndex (Caso o yfinance traga colunas duplas)
        if isinstance(brent_raw.columns, pd.MultiIndex):
            brent_raw.columns = brent_raw.columns.get_level_values(0)
        
        brent_series = brent_raw['Close'].resample('MS').mean()
        brent_series.name = 'Brent'
    except Exception:
        brent_series = pd.Series(name='Brent', dtype='float64')

    # Merge e Reset do Índice
    df = pd.concat([df_sgs, brent_series], axis=1).reset_index()
    
    # FORÇAR PADRONIZAÇÃO DA COLUNA DE DATA
    # Renomeia a primeira coluna (independente se veio como 'Date' ou 'Data') para 'Periodo'
    df.columns.values[0] = 'Periodo'
    
    # Data Cleaning: Preenche buracos causados por feriados (Forward Fill)
    df = df.ffill()
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