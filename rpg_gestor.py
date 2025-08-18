# rpg_gestor.py
import streamlit as st
import openai
import time
import database as db
from dotenv import load_dotenv, find_dotenv
import os

@st.cache_resource
def init_openai_client():
    load_dotenv(find_dotenv())
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["OPENAI_API_KEY"]
        except (KeyError, FileNotFoundError):
            st.error("Chave de API da OpenAI não encontrada. Configure-a no .env ou nos segredos do Streamlit.")
            st.stop()
    return openai.Client(api_key=api_key)

ASSISTANT_ID = "asst_rUreeoWsgwlPaxuJ7J7jYTBC"
EVALUATION_MODEL = "gpt-4-turbo"
client = init_openai_client()

def initialize_session_state(username):
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = db.get_or_create_thread_id(username, client)
    if "messages" not in st.session_state:
        st.session_state.messages = db.get_user_history(username)

def handle_chat_interaction(username, prompt):
    st.session_state.messages.append({"role": "user", "content": prompt})
    db.add_message_to_history(username, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)
    # (opcional) Avaliação automática desabilitada temporariamente.

    with st.chat_message("assistant"):
        try:
            client.beta.threads.messages.create(
                thread_id=st.session_state.thread_id,
                role="user",
                content=prompt
            )
            def stream_generator():
                try:
                    with client.beta.threads.runs.stream(
                        thread_id=st.session_state.thread_id,
                        assistant_id=ASSISTANT_ID,
                    ) as stream:
                        for text in stream.text_deltas:
                            yield text
                            time.sleep(0.01)
                except Exception as e:
                    yield f"❌ Erro na comunicação com o assistente: {str(e)}"
            response = st.write_stream(stream_generator)
        except Exception as e:
            st.error(f"❌ Erro ao comunicar com o assistente: {str(e)}")
            st.info("🔧 Verifique se o ASSISTANT_ID está correto e se a API Key está configurada.")
            return
    if response:
        st.session_state.messages.append({"role": "assistant", "content": response})
        db.add_message_to_history(username, "assistant", response)

def show_dashboard():
    st.title("📊 Dashboard de Análise")
    st.markdown("---")
    try:
        user_stats = db.get_all_user_evaluations()
        if not user_stats:
            st.info("📝 Ainda não há dados de avaliação disponíveis.")
            return
        col1, col2, col3, col4 = st.columns(4)
        total_decisions = sum(user['total_decisions'] for user in user_stats)
        total_hits = sum(user['acertos'] for user in user_stats)
        avg_accuracy = (total_hits / total_decisions * 100) if total_decisions > 0 else 0
        with col1: st.metric("Total de Usuários", len(user_stats))
        with col2: st.metric("Total de Decisões", total_decisions)
        with col3: st.metric("Taxa de Acerto Geral", f"{avg_accuracy:.1f}%")
        with col4: st.metric("Usuários Ativos", len([u for u in user_stats if u['total_decisions'] > 0]))
        st.markdown("---")
        st.subheader("📈 Performance por Usuário")
        import pandas as pd
        df_data = []
        for user in user_stats:
            accuracy = (user['acertos'] / user['total_decisions'] * 100) if user['total_decisions'] > 0 else 0
            df_data.append({
                'Usuário': user['username'],
                'Nome': user.get('name', 'N/A'),
                'Total Decisões': user['total_decisions'],
                'Acertos': user['acertos'],
                'Erros': user['erros'],
                'Taxa de Acerto (%)': f"{accuracy:.1f}%",
                'Última Atividade': user.get('last_activity', 'N/A')
            })
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        if len(df_data) > 0 and total_decisions > 0:
            st.markdown("---")
            st.subheader("📊 Visualizações")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Distribuição de Acertos vs Erros**")
                chart_data = pd.DataFrame({
                    'Usuário': [user['username'] for user in user_stats if user['total_decisions'] > 0],
                    'Acertos': [user['acertos'] for user in user_stats if user['total_decisions'] > 0],
                    'Erros': [user['erros'] for user in user_stats if user['total_decisions'] > 0]
                })
                if not chart_data.empty:
                    st.bar_chart(chart_data.set_index('Usuário'))
            with col2:
                st.markdown("**Taxa de Acerto por Usuário**")
                accuracy_data = pd.DataFrame({
                    'Usuário': [user['username'] for user in user_stats if user['total_decisions'] > 0],
                    'Taxa de Acerto (%)': [(user['acertos'] / user['total_decisions'] * 100) for user in user_stats if user['total_decisions'] > 0]
                })
                if not accuracy_data.empty:
                    st.bar_chart(accuracy_data.set_index('Usuário'))
    except Exception as e:
        st.error(f"Erro ao carregar dashboard: {e}")

def main():
    st.set_page_config(
        page_title="Simulador de Casos",
        page_icon="🎯",
        layout="wide"
    )
    # --- NOVO FLUXO: SEM LOGIN ---
    st.sidebar.title("Bem-vindo!")
    st.sidebar.info("O login foi DESABILITADO temporariamente para livre acesso. Todas as funções estão disponíveis.")
    # Nome de usuário genérico para a sessão (pode personalizar, se quiser)
    if "username" not in st.session_state:
        st.session_state["username"] = "visitante"
    if "name" not in st.session_state:
        st.session_state["name"] = "Visitante"
    st.sidebar.markdown("---")
    page_choice = st.sidebar.selectbox(
        "📋 Menu Principal:",
        ['🎯 Simulação', '📊 Dashboard'],
        key="main_menu"
    )
    if page_choice == '🎯 Simulação':
        initialize_session_state(st.session_state['username'])
        st.title("🎯 Simulador de Casos - Treinamento")
        st.markdown("---")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        if prompt := st.chat_input("Digite sua resposta para continuar a simulação:"):
            handle_chat_interaction(st.session_state['username'], prompt)
            st.rerun()
    elif page_choice == '📊 Dashboard':
        show_dashboard()

if __name__ == "__main__":
    main()
