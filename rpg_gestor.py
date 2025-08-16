# rpg_gestor.py
import streamlit as st
import openai
import time
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.hasher import Hasher
import database as db
from dotenv import load_dotenv, find_dotenv
import os
import pandas as pd

# --- INICIALIZAÇÃO E CONFIGURAÇÃO ---
@st.cache_resource
def init_openai_client():
    """Inicializa o cliente OpenAI de forma cached para não o recriar a cada rerun."""
    load_dotenv(find_dotenv())
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        try:
            api_key = st.secrets["OPENAI_API_KEY"]
        except (KeyError, FileNotFoundError):
            st.error("Chave de API da OpenAI não encontrada. Configure-a no .env ou nos segredos do Streamlit.")
            st.stop()
    
    return openai.Client(api_key=api_key)

# --- CONSTANTES ---
ASSISTANT_ID = "asst_rUreeoWsgwlPaxuJ7J7jYTBC"
EVALUATION_MODEL = "gpt-4-turbo"

# --- INICIALIZAÇÃO ---
client = init_openai_client()
db.init_db()

# --- FUNÇÕES AUXILIARES ---
# A função create_authenticator foi removida para ser chamada diretamente no main()

def evaluate_user_response_background(username, conversation_history, client):
    """Usa um modelo de IA para avaliar a resposta do usuário em background."""
    try:
        history_for_eval = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in conversation_history[-4:]
        ]
        system_prompt = """
        Você é um avaliador especialista em simulações de gestão. Sua tarefa é analisar a última resposta do usuário no contexto da conversa e classificá-la como 'acerto' ou 'erro'.
        - 'acerto' significa que o usuário tomou uma decisão de gestão boa, lógica ou estratégica.
        - 'erro' significa que a decisão foi fraca, ilógica ou prejudicial.
        Responda APENAS com a palavra 'acerto' ou 'erro', em minúsculas e sem nenhuma outra explicação ou pontuação.
        """
        eval_prompt = [{"role": "system", "content": system_prompt}] + history_for_eval
        response = client.chat.completions.create(
            model=EVALUATION_MODEL,
            messages=eval_prompt,
            max_tokens=10,
            temperature=0.1
        )
        evaluation = response.choices[0].message.content.strip().lower()
        if evaluation in ['acerto', 'erro']:
            db.log_user_action(username, "avaliacao_automatica", evaluation)
    except Exception:
        pass # Silencioso para não interromper o usuário

def show_chat_interface(username):
    """Exibe a interface principal da simulação de chat."""
    st.title("🎯 Simulador de Casos - Treinamento")
    st.markdown("---")
    
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = db.get_or_create_thread_id(username, client)
    if "messages" not in st.session_state:
        st.session_state.messages = db.get_user_history(username)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input("Digite sua resposta para continuar a simulação:"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        db.add_message_to_history(username, "user", prompt)
        
        evaluate_user_response_background(username, st.session_state.messages, client)
        
        with st.chat_message("assistant"):
            try:
                client.beta.threads.messages.create(
                    thread_id=st.session_state.thread_id,
                    role="user",
                    content=prompt
                )
                def stream_generator():
                    with client.beta.threads.runs.stream(
                        thread_id=st.session_state.thread_id,
                        assistant_id=ASSISTANT_ID,
                    ) as stream:
                        for text in stream.text_deltas:
                            yield text
                            time.sleep(0.01)
                response = st.write_stream(stream_generator)
                
                if response:
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    db.add_message_to_history(username, "assistant", response)
            except Exception as e:
                st.error(f"❌ Erro ao comunicar com o assistente: {str(e)}")
        st.rerun()

def show_dashboard():
    """Exibe o dashboard com estatísticas de todos os usuários."""
    st.title("📊 Dashboard de Análise")
    st.markdown("---")
    
    user_stats = db.get_all_user_evaluations()
        
    if not user_stats:
        st.info("📝 Ainda não há dados de avaliação disponíveis.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    total_decisions = sum(user['total_decisions'] for user in user_stats)
    total_hits = sum(user['acertos'] for user in user_stats)
    avg_accuracy = (total_hits / total_decisions * 100) if total_decisions > 0 else 0
    
    with col1:
        st.metric("Total de Usuários", len(user_stats))
    with col2:
        st.metric("Total de Decisões", total_decisions)
    with col3:
        st.metric("Taxa de Acerto Geral", f"{avg_accuracy:.1f}%")
    with col4:
        st.metric("Usuários Ativos", len([u for u in user_stats if u['total_decisions'] > 0]))
    
    st.markdown("---")
    
    st.subheader("📈 Performance por Usuário")
    df_data = []
    for user in user_stats:
        accuracy = (user['acertos'] / user['total_decisions'] * 100) if user['total_decisions'] > 0 else 0
        df_data.append({
            'Usuário': user['username'],
            'Nome': user.get('name', 'N/A'),
            'Total Decisões': user['total_decisions'],
            'Acertos': user['acertos'],
            'Erros': user['erros'],
            'Taxa de Acerto (%)': f"{accuracy:.1f}",
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
            chart_data = df[['Usuário', 'Acertos', 'Erros']].set_index('Usuário')
            st.bar_chart(chart_data)
        with col2:
            st.markdown("**Taxa de Acerto por Usuário**")
            accuracy_data = df[['Usuário', 'Taxa de Acerto (%)']].set_index('Usuário')
            accuracy_data['Taxa de Acerto (%)'] = accuracy_data['Taxa de Acerto (%)'].astype(float)
            st.bar_chart(accuracy_data)

# --- APLICAÇÃO PRINCIPAL ---
def main():
    st.set_page_config(page_title="Simulador de Casos", page_icon="🎯", layout="wide")
    
    # --- CORREÇÃO: Cria o autenticador a cada execução ---
    # Isto garante que ele sempre tem a lista de usuários mais recente do banco de dados.
    credentials = db.get_user_credentials()
    authenticator = stauth.Authenticate(
        credentials,
        'mestre_gestor_cookie',
        'mestre_gestor_key',
        30
    )
    
    # Se o usuário já estiver logado
    if st.session_state.get("authentication_status"):
        authenticator.logout('Logout', 'sidebar')
        st.sidebar.title(f"Bem-vindo(a) {st.session_state['name']}!")
        st.sidebar.markdown("---")
        
        page_choice = st.sidebar.selectbox(
            "Escolha uma opção:",
            ['🎯 Simulação', '📊 Dashboard'],
            key="main_menu"
        )
        
        if page_choice == '🎯 Simulação':
            show_chat_interface(st.session_state['username'])
        elif page_choice == '📊 Dashboard':
            show_dashboard()
            
    # Se o usuário não estiver logado
    else:
        choice = st.sidebar.selectbox(
            "Navegação:",
            ['🔐 Login', '📝 Registrar'],
            key="auth_menu"
        )
        
        if choice == '🔐 Login':
            st.title("🔐 Login")
            name, authentication_status, username = authenticator.login('main')
            if authentication_status:
                st.session_state.update({'name': name, 'username': username, 'authentication_status': authentication_status})
                st.rerun()
            elif authentication_status is False:
                st.error('❌ Usuário ou senha incorretos')
        
        elif choice == '📝 Registrar':
            st.title("📝 Crie sua Conta")
            with st.form("register_form", clear_on_submit=True):
                new_name = st.text_input("Nome Completo")
                new_username = st.text_input("Nome de Usuário")
                new_email = st.text_input("E-mail")
                new_password = st.text_input("Senha", type="password")
                confirm_password = st.text_input("Confirme a Senha", type="password")
                submitted = st.form_submit_button("🚀 Registrar")

                if submitted:
                    if not all([new_name, new_email, new_username, new_password]):
                        st.error("❌ Por favor, preencha todos os campos.")
                    elif new_password != confirm_password:
                        st.error("❌ As senhas não coincidem.")
                    else:
                        hashed_password = Hasher([new_password]).generate()[0]
                        if db.add_user(new_username, new_name, new_email, hashed_password):
                            st.success("✅ Usuário registrado com sucesso! Por favor, faça o login.")
                            time.sleep(2)
                            st.rerun() # Apenas faz o rerun para limpar o formulário e mostrar a tela de login
                        else:
                            st.error("❌ Nome de usuário ou e-mail já existe.")

if __name__ == "__main__":
    main()
