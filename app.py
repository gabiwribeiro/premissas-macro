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
            brent_series = brent_raw['Close'].resample('MS').mean()
            brent_series.name = 'Brent'
        else:
            brent_series = pd.Series(name='Brent', dtype='float64')
    except Exception:
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
    # --- 4. KPIs (INDICADORES RESUMIDOS) ---
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

    # --- 5. GRÁFICOS (MANTIDOS) ---
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

    # --- 6. TABELA CONSOLIDADA (CORREÇÃO IPCA ANUAL E DÓLAR %) ---
    st.subheader("📊 Premissas e Indicadores (Consolidado)")

    df_tab = df_final.copy()
    df_tab['Ano'] = df_tab['Periodo'].dt.year
    df_tab['Mes_Ref'] = df_tab['Periodo'].dt.strftime('%b/%y').str.lower()

    # Médias Anuais para Preços e SOMAS para Inflação
    def consolidar_ano(group):
        return pd.Series({
            'IPCA': group['IPCA'].sum(),   # Inflação se soma no ano
            'IGPM': group['IGPM'].sum(),   # Inflação se soma no ano
            'SELIC': group['SELIC'].mean(), # Juros se tira média
            'Dólar': group['Dólar'].mean(), # Câmbio se tira média
            'Brent': group['Brent'].mean()  # Brent se tira média
        })

    df_anuais = df_tab[df_tab['Ano'].isin([2023, 2024, 2025])].groupby('Ano').apply(consolidar_ano).T
    df_anuais.columns = df_anuais.columns.astype(str)

    # Mensal 2026 (Valores reais mensais)
    df_2026 = df_tab[df_tab['Ano'] == 2026].copy()
    if not df_2026.empty:
        df_2026 = df_2026.set_index('Mes_Ref').drop(columns=['Periodo', 'Ano']).T
    else:
        df_2026 = pd.DataFrame(index=df_anuais.index)

    tabela_viz = pd.concat([df_anuais, df_2026], axis=1)
    tabela_viz = tabela_viz.loc[:, ~tabela_viz.columns.duplicated()]
    
    # FORMATADOR BASEADO NO NOME DA LINHA (INDEX)
    def formatar_final(val):
        if pd.isna(val) or val == 0: return "-"
        
        # Obtemos o nome do indicador que estamos formatando
        # O styler passa o valor, mas precisamos saber de qual linha ele é
        return val # Fallback

    # Aplicando a formatação linha a linha para evitar erro de dólar com %
    styler = tabela_viz.style.format(lambda v: f"{v:.2f}".replace(".", ","))
    
    # Aplicar sufixo % apenas nas linhas de taxas
    taxas = ['IPCA', 'IGPM', 'SELIC']
    for taxa in taxas:
        if taxa in tabela_viz.index:
            styler = styler.format(lambda v: f"{v:.2f}%".replace(".", ","), subset=pd.IndexSlice[taxa, :])
    
    # Aplicar formato de moeda/valor nas linhas de preços
    precos = ['Dólar', 'Brent']
    for preco in precos:
        if preco in tabela_viz.index:
            styler = styler.format(lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), subset=pd.IndexSlice[preco, :])

    try:
        st.dataframe(styler.highlight_max(axis=1, color='#e6f3ff'), use_container_width=True)
    except:
        st.dataframe(tabela_viz, use_container_width=True)

    st.caption("Fontes: BCB (SGS) e Yahoo Finance. *IPCA/IGPM anuais representam o acumulado (soma) do período.*")

else:
    st.error("Erro ao carregar dados.")