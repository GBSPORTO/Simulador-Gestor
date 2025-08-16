# pages/01_Dashboard.py
import streamlit as st
import pandas as pd
import database as db
import openai
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configura o layout da página para ser largo
st.set_page_config(page_title="Dashboard de Análise", layout="wide")

def init_openai_client():
    """Inicializa cliente OpenAI para análise subjetiva"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["OPENAI_API_KEY"]
        except (KeyError, FileNotFoundError):
            return None
    return openai.Client(api_key=api_key)

def get_user_conversation_history(username):
    """Busca o histórico de conversas do usuário para análise qualitativa"""
    try:
        # Busca mensagens do usuário (apenas as dele, não as do assistente)
        user_messages = db.get_user_history(username)
        
        # Filtra apenas mensagens do usuário e pega as últimas 20
        user_responses = [
            msg['content'] for msg in user_messages 
            if msg['role'] == 'user'
        ][-20:]  # Últimas 20 respostas para análise
        
        return user_responses
    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
        return []

def generate_subjective_analysis(username, user_stats, user_messages, client):
    """Gera análise subjetiva usando seu Assistant da OpenAI"""
    if not client or not user_messages:
        return "Análise subjetiva não disponível."
    
    try:
        # Calcula estatísticas para contexto
        total_decisions = user_stats.get('total_decisoes', 0)
        accuracy = user_stats.get('taxa_acerto', 0)
        
        # Prepara as últimas respostas do usuário
        recent_responses = "\n".join([f"- {msg}" for msg in user_messages[-10:]])
        
        # Prompt específico para análise subjetiva usando seu Assistant
        analysis_prompt = f"""
        Por favor, analise o perfil de liderança do usuário "{username}" baseado em suas interações no simulador.
        
        DADOS QUANTITATIVOS:
        - Total de decisões tomadas: {total_decisions}
        - Taxa de acerto: {accuracy:.1f}%
        
        ÚLTIMAS 10 RESPOSTAS DO USUÁRIO:
        {recent_responses}
        
        Forneça uma análise SUBJETIVA e QUALITATIVA estruturada no seguinte formato:
        
        ## 🎯 PERFIL DE LIDERANÇA
        [Identifique o estilo de liderança predominante baseado nas respostas]
        
        ## 💪 PONTOS FORTES OBSERVADOS
        [Liste 3-4 pontos fortes identificados nas decisões e respostas]
        
        ## 🔄 ÁREAS DE DESENVOLVIMENTO
        [Indique 2-3 áreas que podem ser aprimoradas]
        
        ## 📈 PADRÃO DE TOMADA DE DECISÃO
        [Analise como este usuário costuma tomar decisões - é analítico, impulsivo, colaborativo, etc?]
        
        ## 🎓 RECOMENDAÇÕES PERSONALIZADAS
        [Dê sugestões específicas para desenvolvimento baseadas no perfil identificado]
        
        Base sua análise exclusivamente nas respostas reais fornecidas. Seja construtivo, específico e profissional.
        Máximo de 800 palavras.
        """
        
        # Cria thread para análise (ou use thread existente se preferir)
        thread = client.beta.threads.create()
        
        # Adiciona mensagem à thread
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=analysis_prompt
        )
        
        # Executa o Assistant (use seu ASSISTANT_ID aqui)
        ASSISTANT_ID = "asst_rUreeoWsgwlPaxuJ7J7jYTBC"  # Seu Assistant ID
        
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )
        
        # Aguarda conclusão
        import time
        while run.status in ['queued', 'in_progress', 'cancelling']:
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
        
        if run.status == 'completed':
            # Busca a resposta
            messages = client.beta.threads.messages.list(
                thread_id=thread.id
            )
            
            # Pega a última mensagem (resposta do Assistant)
            assistant_response = messages.data[0].content[0].text.value
            return assistant_response
        else:
            return f"Erro na execução do Assistant: {run.status}"
        
    except Exception as e:
        return f"Erro ao gerar análise subjetiva: {e}"

def show_user_detailed_analysis(username, df_actions, outcome_column):
    """Mostra análise detalhada de um usuário específico"""
    
    user_data = df_actions[df_actions['username'] == username]
    
    if user_data.empty:
        st.warning(f"Não há dados suficientes para análise de {username}")
        return
    
    # Estatísticas básicas
    total_decisions = len(user_data)
    acertos = len(user_data[user_data[outcome_column] == 'acerto'])
    erros = len(user_data[user_data[outcome_column] == 'erro'])
    taxa_acerto = (acertos / total_decisions * 100) if total_decisions > 0 else 0
    
    # Layout em colunas
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader(f"📊 Análise Quantitativa - {username}")
        
        # Métricas
        metrica1, metrica2, metrica3 = st.columns(3)
        metrica1.metric("Decisões", total_decisions)
        metrica2.metric("Acertos", acertos)
        metrica3.metric("Taxa (%)", f"{taxa_acerto:.1f}%")
        
        # Evolução temporal se tiver dados suficientes
        if len(user_data) > 5:
            st.markdown("**Evolução Temporal**")
            user_data['date'] = pd.to_datetime(user_data['timestamp']).dt.date
            daily_performance = user_data.groupby('date').agg({
                outcome_column: lambda x: (x == 'acerto').sum() / len(x) * 100
            }).reset_index()
            daily_performance.columns = ['Data', 'Taxa_Acerto_Diaria']
            
            if len(daily_performance) > 1:
                st.line_chart(daily_performance.set_index('Data'))
        
        # Atividade recente
        st.markdown("**Últimas 5 Ações**")
        recent_actions = user_data.sort_values('timestamp', ascending=False).head(5)
        st.dataframe(recent_actions[['timestamp', outcome_column]], use_container_width=True)
    
    with col2:
        st.subheader(f"🧠 Análise Subjetiva - {username}")
        
        # Inicializa cliente OpenAI
        client = init_openai_client()
        
        if client:
            with st.spinner("Gerando análise qualitativa..."):
                # Busca histórico de conversas
                user_messages = get_user_conversation_history(username)
                
                if user_messages:
                    # Gera análise subjetiva
                    user_stats = {
                        'total_decisoes': total_decisions,
                        'taxa_acerto': taxa_acerto
                    }
                    
                    subjective_analysis = generate_subjective_analysis(
                        username, user_stats, user_messages, client
                    )
                    
                    # Exibe a análise
                    st.markdown(subjective_analysis)
                    
                    # Botão para regenerar análise
                    if st.button(f"🔄 Regenerar Análise para {username}", key=f"regen_{username}"):
                        st.rerun()
                        
                else:
                    st.info("📝 Não há mensagens suficientes do usuário para análise qualitativa.")
        else:
            st.warning("⚙️ OpenAI não configurada. Análise subjetiva indisponível.")

# --- CONTROLE DE ACESSO ---
ADMIN_USERS = ["gbsporto"] 

if st.session_state.get("authentication_status") and st.session_state.get("username") in ADMIN_USERS:
    st.title("📊 Dashboard de Análise Completa")
    
    # Busca todos os registos de ações do banco de dados
    try:
        df_actions = db.get_all_user_actions()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()
    
    if df_actions.empty:
        st.warning("Ainda não há dados de ações de usuários para analisar.")
    else:
        # Converte timestamp
        df_actions['timestamp'] = pd.to_datetime(df_actions['timestamp'])
        
        # Identifica coluna de resultados
        outcome_column = None
        if 'outcome' in df_actions.columns:
            outcome_column = 'outcome'
        elif 'action_data' in df_actions.columns:
            outcome_column = 'action_data'
        else:
            st.error("❌ Coluna de resultados não encontrada.")
            st.stop()
        
        # TABS PRINCIPAIS
        tab1, tab2, tab3 = st.tabs(["📈 Visão Geral", "👤 Análise Individual", "🔍 Detalhes Técnicos"])
        
        with tab1:
            st.header("📈 Visão Geral do Sistema")
            
            # Métricas gerais
            total_decisoes = len(df_actions)
            total_acertos = len(df_actions[df_actions[outcome_column] == 'acerto'])
            total_erros = len(df_actions[df_actions[outcome_column] == 'erro'])
            taxa_acerto_geral = (total_acertos / total_decisoes) * 100 if total_decisoes > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total de Decisões", total_decisoes)
            col2.metric("Total de Acertos", total_acertos)
            col3.metric("Total de Erros", total_erros)
            col4.metric("Taxa de Acerto (%)", f"{taxa_acerto_geral:.2f}%")
            
            st.divider()
            
            # Ranking de usuários
            st.subheader("🏆 Ranking de Performance")
            user_summary = df_actions.groupby('username').agg(
                total_decisoes=(outcome_column, 'count'),
                total_acertos=(outcome_column, lambda x: (x == 'acerto').sum()),
                total_erros=(outcome_column, lambda x: (x == 'erro').sum())
            ).reset_index()
            
            user_summary['taxa_acerto'] = (user_summary['total_acertos'] / user_summary['total_decisoes']) * 100
            user_summary = user_summary.sort_values(by='taxa_acerto', ascending=False)
            
            st.dataframe(user_summary, use_container_width=True)
            
            # Gráfico de barras
            if not user_summary.empty:
                st.subheader("📊 Taxa de Acerto por Usuário")
                chart_data = user_summary.set_index('username')['taxa_acerto']
                st.bar_chart(chart_data)
        
        with tab2:
            st.header("👤 Análise Individual Detalhada")
            
            # Seletor de usuário
            available_users = df_actions['username'].unique().tolist()
            selected_user = st.selectbox(
                "Selecione um usuário para análise detalhada:",
                available_users,
                key="user_selector"
            )
            
            if selected_user:
                st.divider()
                show_user_detailed_analysis(selected_user, df_actions, outcome_column)
        
        with tab3:
            st.header("🔍 Detalhes Técnicos e Debugging")
            
            # Debug info
            if st.checkbox("Mostrar estrutura dos dados"):
                st.write("**Colunas do DataFrame:**", df_actions.columns.tolist())
                st.write("**Tipos de dados:**", df_actions.dtypes)
                st.write("**Primeiras 5 linhas:**")
                st.dataframe(df_actions.head())
            
            # Atividade recente
            st.subheader("📋 Atividade Recente (Últimas 20)")
            recent_actions = df_actions.sort_values(by='timestamp', ascending=False).head(20)
            st.dataframe(recent_actions, use_container_width=True)
            
            # Análise temporal
            st.subheader("📅 Análise por Período")
            df_actions['date'] = df_actions['timestamp'].dt.date
            daily_stats = df_actions.groupby('date').agg(
                total_decisions=('username', 'count'),
                acertos=(outcome_column, lambda x: (x == 'acerto').sum()),
                usuarios_unicos=('username', 'nunique')
            ).reset_index()
            
            daily_stats['taxa_acerto_diaria'] = (daily_stats['acertos'] / daily_stats['total_decisions']) * 100
            
            if len(daily_stats) > 0:
                st.dataframe(daily_stats.tail(10), use_container_width=True)
                
                if len(daily_stats) > 1:
                    st.line_chart(daily_stats.set_index('date')['taxa_acerto_diaria'])

else:
    st.error("Você não tem permissão para acessar esta página. Faça login como administrador.")
