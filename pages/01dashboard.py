# pages/01_Dashboard.py
import streamlit as st
import pandas as pd
import database as db

# Configura o layout da página para ser largo
st.set_page_config(page_title="Dashboard de Análise", layout="wide")

# --- CONTROLE DE ACESSO ---
# Define a lista de nomes de usuário que são considerados administradores.
# Apenas estes usuários poderão ver esta página.
ADMIN_USERS = ["gbsporto"] 

# Verifica se o usuário está logado (authentication_status == True) E
# se o nome de usuário da sessão atual está na lista de administradores.
if st.session_state.get("authentication_status") and st.session_state.get("username") in ADMIN_USERS:
    st.title("📊 Dashboard de Análise de Desempenho")

    # Busca todos os registos de ações do banco de dados
    df_actions = db.get_all_user_actions()

    # Se não houver dados, exibe um aviso
    if df_actions.empty:
        st.warning("Ainda não há dados de ações de usuários para analisar.")
    else:
        # Converte a coluna de timestamp para o formato de data para melhor manipulação
        df_actions['timestamp'] = pd.to_datetime(df_actions['timestamp'])

        st.header("Visão Geral")
        
        # Calcula as métricas gerais de desempenho
        total_decisoes = len(df_actions)
        total_acertos = len(df_actions[df_actions['outcome'] == 'acerto'])
        taxa_acerto_geral = (total_acertos / total_decisoes) * 100 if total_decisoes > 0 else 0
        
        # Exibe as métricas em colunas
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Decisões Registadas", total_decisoes)
        col2.metric("Total de Acertos", total_acertos)
        col3.metric("Taxa de Acerto Geral (%)", f"{taxa_acerto_geral:.2f}%")

        st.divider()

        st.header("Análise por Usuário")
        
        # Agrupa os dados para criar um resumo de desempenho por usuário
        user_summary = df_actions.groupby('username').agg(
            total_decisoes=('outcome', 'count'),
            total_acertos=('outcome', lambda x: (x == 'acerto').sum())
        ).reset_index()
        user_summary['taxa_acerto'] = (user_summary['total_acertos'] / user_summary['total_decisoes']) * 100
        
        # Exibe a tabela de resumo
        st.dataframe(user_summary.sort_values(by='taxa_acerto', ascending=False), use_container_width=True)

        st.subheader("Taxa de Acerto por Usuário (%)")
        # Exibe um gráfico de barras com a taxa de acerto de cada usuário
        st.bar_chart(user_summary.set_index('username')['taxa_acerto'])
        
        st.divider()
        
        st.header("Atividade Recente")
        # Exibe as 10 ações mais recentes registadas no sistema
        st.dataframe(df_actions.sort_values(by='timestamp', ascending=False).head(10), use_container_width=True)
else:
    # Se o usuário não estiver logado ou não for um admin, exibe uma mensagem de erro
    st.error("Você não tem permissão para aceder a esta página. Por favor, faça o login como administrador.")

