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
        # Garante que os índices estão alinhados e sem duplicatas antes do join
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

    # --- 6. TABELA CONSOLIDADA (LOGICA BLINDADA) ---
    st.subheader("📊 Premissas e Indicadores (Consolidado)")

    df_tab = df_final.copy()
    df_tab['Ano'] = df_tab['Periodo'].dt.year
    df_tab['Mes_Ref'] = df_tab['Periodo'].dt.strftime('%b/%y').str.lower()

    def calcular_anuais_fpa(df):
        anos = [2023, 2024, 2025]
        resultados = {}
        
        for ano in anos:
            # Filtro rigoroso por ano
            df_ano = df[df['Ano'] == ano].copy().dropna(subset=['IPCA', 'IGPM', 'Dólar'])
            
            if not df_ano.empty:
                # IPCA e IGPM: Acumulado Real (Juros Compostos)
                # Formula: (Product(1 + taxa/100) - 1) * 100
                ipca_anual = ((df_ano['IPCA'] / 100 + 1).prod() - 1) * 100
                igpm_anual = ((df_ano['IGPM'] / 100 + 1).prod() - 1) * 100
                
                resultados[str(ano)] = {
                    'IPCA': ipca_anual,
                    'IGPM': igpm_anual,
                    'SELIC': df_ano['SELIC'].mean(),
                    'Dólar': df_ano['Dólar'].mean(),
                    'Brent': df_ano['Brent'].mean()
                }
        return pd.DataFrame(resultados)

    df_anuais = calcular_anuais_fpa(df_tab)

    # Dados Mensais de 2026
    df_2026 = df_tab[df_tab['Ano'] == 2026].copy()
    if not df_2026.empty:
        df_2026 = df_2026.set_index('Mes_Ref').drop(columns=['Periodo', 'Ano']).T
    else:
        df_2026 = pd.DataFrame(index=df_anuais.index)

    # Concatenação final e limpeza de duplicatas
    tabela_viz = pd.concat([df_anuais, df_2026], axis=1)
    tabela_viz = tabela_viz.loc[:, ~tabela_viz.columns.duplicated()]
    tabela_viz.index.name = "Indicadores"

    # --- Estilização Brasileira ---
    def fmt_br(val, is_pct=False):
        if pd.isna(val) or val == 0: return "-"
        if is_pct:
            return f"{val:.2f}%".replace(".", ",")
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Criando o Styler
    styler = tabela_viz.style
    
    # Formata cada linha individualmente pelo nome
    for row_name in tabela_viz.index:
        if row_name in ['IPCA', 'IGPM', 'SELIC']:
            styler = styler.format(lambda v: fmt_br(v, True), subset=pd.IndexSlice[row_name, :])
        else:
            styler = styler.format(lambda v: fmt_br(v, False), subset=pd.IndexSlice[row_name, :])

    st.dataframe(styler.highlight_max(axis=1, color='#e6f3ff'), use_container_width=True)
    st.caption("Fontes: BCB e Yahoo Finance. Inflação anualizada via juros compostos.")

else:
    st.error("Erro ao carregar dados.")