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
            time.sleep(1)
            continue

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

    if not df_sgs.empty:
        df = pd.concat([df_sgs, brent_series], axis=1)
        df = df[~df.index.duplicated(keep='first')]
        df = df.reset_index().rename(columns={'index': 'Periodo', 'Date': 'Periodo'})
        df = df.ffill().bfill()
        return df
    return pd.DataFrame()

# --- 3. EXECUÇÃO ---
df_final = carregar_dados()

if not df_final.empty:
    # --- 4. KPIs ---
    def get_last_valid(df, column):
        valid_series = df[column].dropna()
        return valid_series.iloc[-1] if not valid_series.empty else 0

    val_cambio = get_last_valid(df_final, 'Dólar')
    val_brent = get_last_valid(df_final, 'Brent')
    val_selic = get_last_valid(df_final, 'SELIC')
    val_ipca = get_last_valid(df_final, 'IPCA')

    def pbr(valor, pct=False):
        texto = f"{valor:.2f}".replace(".", ",")
        return texto + "%" if pct else texto

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Câmbio (USD/BRL)", f"R$ {pbr(val_cambio)}")
    with c2: st.metric("Petróleo Brent", f"U$ {pbr(val_brent)}" if val_brent > 0 else "U$ --")
    with c3: st.metric("SELIC Atual", pbr(val_selic, pct=True))
    with c4: st.metric("IPCA (Mês)", pbr(val_ipca, pct=True))

    st.divider()

    # --- 5. GRÁFICOS ---
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Custos: Brent vs Câmbio")
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=df_final['Periodo'], y=df_final['Dólar'], name="Câmbio", line=dict(color='#005291')), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_final['Periodo'], y=df_final['Brent'], name="Brent", line=dict(color='#008751')), secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        st.subheader("Inflação: IPCA vs IGPM")
        fig_inf = px.area(df_final, x='Periodo', y=['IPCA', 'IGPM'], color_discrete_map={'IPCA': '#005291', 'IGPM': '#FF4B4B'})
        st.plotly_chart(fig_inf, use_container_width=True)

    st.divider()

    # --- 6. TABELA CONSOLIDADA (CÁLCULO RIGOROSO) ---
    st.subheader("📊 Premissas e Indicadores (Consolidado)")

    df_tab = df_final.copy()
    df_tab['Ano'] = df_tab['Periodo'].dt.year
    df_tab['Mes_Ref'] = df_tab['Periodo'].dt.strftime('%b/%y').str.lower()

    def calcular_anuais_v2(df):
        anos = [2023, 2024, 2025]
        resultados = {}
        for ano in anos:
            df_ano = df[df['Ano'] == ano].copy()
            if not df_ano.empty:
                # IPCA e IGPM: Multiplicação geométrica (1 + r1/100) * (1 + r2/100)...
                # Usamos .prod() mas garantimos que não há NaNs
                ipca_acum = ((df_ano['IPCA'].fillna(0) / 100 + 1).prod() - 1) * 100
                igpm_acum = ((df_ano['IGPM'].fillna(0) / 100 + 1).prod() - 1) * 100
                
                resultados[str(ano)] = {
                    'IPCA': ipca_acum,
                    'IGPM': igpm_acum,
                    'SELIC': df_ano['SELIC'].iloc[-1], # Última do ano
                    'Dólar': df_ano['Dólar'].mean(),
                    'Brent': df_ano['Brent'].mean()
                }
        return pd.DataFrame(resultados)

    df_anuais = calcular_anuais_v2(df_tab)
    df_2026 = df_tab[df_tab['Ano'] == 2026].set_index('Mes_Ref').drop(columns=['Periodo', 'Ano']).T

    tabela_viz = pd.concat([df_anuais, df_2026], axis=1)
    tabela_viz = tabela_viz.loc[:, ~tabela_viz.columns.duplicated()]

    # Formatação Visual
    def formatar_br(val, ind):
        if pd.isna(val) or val == 0: return "-"
        if ind in ['IPCA', 'IGPM', 'SELIC']:
            return f"{val:.2f}%".replace(".", ",")
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    styler = tabela_viz.style
    for idx in tabela_viz.index:
        styler = styler.format(lambda v, i=idx: formatar_br(v, i), subset=pd.IndexSlice[idx, :])

    st.dataframe(styler.highlight_max(axis=1, color='#e6f3ff'), use_container_width=True)

    # --- 7. BOTÃO DE DOWNLOAD ---
    st.divider()
    st.subheader("📥 Exportar Dados")
    
    @st.cache_data
    def converter_csv(df):
        return df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

    csv_data = converter_csv(df_final)
    st.download_button(
        label="Download Dados Completos (CSV)",
        data=csv_data,
        file_name=f'indicadores_macro_vibra_{datetime.now().strftime("%Y%m%d")}.csv',
        mime='text/csv',
    )
    st.caption("Fontes: BCB e Yahoo Finance. Valores anuais: Inflação (acumulada), SELIC (fecho), Outros (média).")

else:
    st.error("Dados não encontrados. Verifique a ligação às APIs.")