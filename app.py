import pandas as pd

# Lendo o arquivo enviado pelo usuário para garantir que estamos editando a versão mais recente
with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Preparando a nova lógica de download para ser inserida ao final do código.
# Utilizaremos o st.download_button do Streamlit.
# O dado precisa ser convertido para CSV com separador ';' e vírgula decimal para Excel BR.

download_logic = """
    # --- 7. EXPORTAÇÃO DE DADOS ---
    st.divider()
    st.subheader("📥 Exportar Dados")
    
    # Preparamos o CSV para download (Padrão Excel Brasil: separador ; e vírgula decimal)
    @st.cache_data
    def converter_csv(df):
        return df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

    csv_data = converter_csv(df_final)

    st.download_button(
        label="Download Dados Completos (CSV)",
        data=csv_data,
        file_name=f'indicadores_macro_{datetime.now().strftime("%Y%m%d")}.csv',
        mime='text/csv',
    )
"""

# Verificamos se o arquivo termina com a mensagem de erro do 'else' e inserimos antes disso
# ou simplesmente ao final do bloco 'if not df_final.empty:'

if "st.caption" in code:
    # Inserimos logo após o caption final da tabela
    new_code = code.replace('st.caption("Fontes: BCB e Yahoo Finance. *SELIC reflete a taxa no fechamento do período.*")', 
                            'st.caption("Fontes: BCB e Yahoo Finance. *SELIC reflete a taxa no fechamento do período.*")' + download_logic)
else:
    # Fallback caso a string tenha mudado levemente
    new_code = code + download_logic

with open('app_v2.py', 'w', encoding='utf-8') as f:
    f.write(new_code)