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
    try:
        df_actions = db.get_all_user_actions()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()
    
    # Se não houver dados, exibe um aviso
    if df_actions.empty:
        st.warning("Ainda não há dados de ações de usuários para analisar.")
    else:
        # Debug: Mostra as colunas disponíveis (remover depois de corrigir)
        if st.checkbox("🔍 Mostrar colunas disponíveis (Debug)"):
            st.write("Colunas do DataFrame:", df_actions.columns.tolist())
            st.write("Primeiras 3 linhas:", df_actions.head(3))
        
        # Converte a coluna de timestamp para o formato de data para melhor manipulação
        df_actions['timestamp'] = pd.to_datetime(df_actions['timestamp'])
        
        st.header("Visão Geral")
        
        # Identifica qual coluna contém os resultados (outcome/action_data)
        outcome_column = None
        if 'outcome' in df_actions.columns:
            outcome_column = 'outcome'
        elif 'action_data' in df_actions.columns:
            outcome_column = 'action_data'
        else:
            st.error("❌ Coluna de resultados não encontrada. Verifique a função `get_all_user_actions()` no database.py")
            st.stop()
        
        # Calcula as métricas gerais de desempenho
        total_decisoes = len(df_actions)
        total_acertos = len(df_actions[df_actions[outcome_column] == 'acerto'])
        total_erros = len(df_actions[df_actions[outcome_column] == 'erro'])
        taxa_acerto_geral = (total_acertos / total_decisoes) * 100 if total_decisoes > 0 else 0
        
        # Exibe as métricas em colunas
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Decisões", total_decisoes)
        col2.metric("Total de Acertos", total_acertos)
        col3.metric("Total de Erros", total_erros)
        col4.metric("Taxa de Acerto (%)", f"{taxa_acerto_geral:.2f}%")
        
        st.divider()
        st.header("Análise por Usuário")
        
        # Agrupa os dados para criar um resumo de desempenho por usuário
        try:
            user_summary = df_actions.groupby('username').agg(
                total_decisoes=(outcome_column, 'count'),
                total_acertos=(outcome_column, lambda x: (x == 'acerto').sum()),
                total_erros=(outcome_column, lambda x: (x == 'erro').sum())
            ).reset_index()
            
            # Calcula a taxa de acerto
            user_summary['taxa_acerto'] = (user_summary['total_acertos'] / user_summary['total_decisoes']) * 100
            
            # Exibe a tabela de resumo ordenada por taxa de acerto
            st.dataframe(
                user_summary.sort_values(by='taxa_acerto', ascending=False), 
                use_container_width=True
            )
            
            st.subheader("Taxa de Acerto por Usuário (%)")
            
            # Verifica se há dados para o gráfico
            if not user_summary.empty:
                # Exibe um gráfico de barras com a taxa de acerto de cada usuário
                chart_data = user_summary.set_index('username')['taxa_acerto']
                if len(chart_data) > 0:
                    st.bar_chart(chart_data)
                else:
                    st.info("Não há dados suficientes para o gráfico.")
            else:
                st.info("Não há dados de usuários para exibir.")
                
        except Exception as e:
            st.error(f"Erro ao processar dados por usuário: {e}")
            st.write("Dados disponíveis:", df_actions.head())
        
        st.divider()
        
        st.header("Atividade Recente")
        # Exibe as 10 ações mais recentes registadas no sistema
        recent_actions = df_actions.sort_values(by='timestamp', ascending=False).head(10)
        
        # Renomeia colunas para melhor exibição
        display_actions = recent_actions.copy()
        if outcome_column == 'action_data':
            display_actions = display_actions.rename(columns={'action_data': 'Resultado'})
        
        st.dataframe(display_actions, use_container_width=True)
        
        # Seção adicional: Estatísticas por período
        st.divider()
        st.header("📈 Análise Temporal")
        
        try:
            # Agrupa por data
            df_actions['date'] = df_actions['timestamp'].dt.date
            daily_stats = df_actions.groupby('date').agg(
                total_decisions=('username', 'count'),
                acertos=(outcome_column, lambda x: (x == 'acerto').sum()),
                erros=(outcome_column, lambda x: (x == 'erro').sum())
            ).reset_index()
            
            daily_stats['taxa_acerto_diaria'] = (daily_stats['acertos'] / daily_stats['total_decisions']) * 100
            
            # Últimos 7 dias
            if len(daily_stats) > 0:
                st.subheader("Últimos 7 dias")
                recent_days = daily_stats.tail(7)
                st.dataframe(recent_days, use_container_width=True)
                
                # Gráfico de linha da taxa de acerto ao longo do tempo
                if len(recent_days) > 1:
                    st.line_chart(recent_days.set_index('date')['taxa_acerto_diaria'])
            
        except Exception as e:
            st.warning(f"Não foi possível gerar análise temporal: {e}")

else:
    # Se o usuário não estiver logado ou não for um admin, exibe uma mensagem de erro
    st.error("Você não tem permissão para aceder a esta página. Por favor, faça o login como administrador.")
