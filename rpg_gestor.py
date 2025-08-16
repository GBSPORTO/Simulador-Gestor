# rpg_gestor.py
import streamlit as st
import openai
import time
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.hasher import Hasher
import database as db
from dotenv import load_dotenv, find_dotenv
import os

# --- INICIALIZAÇÃO E CONFIGURAÇÃO ---
load_dotenv(find_dotenv())
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    client = openai.Client(api_key=api_key)
else:
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
        client = openai.Client(api_key=api_key)
    except (KeyError, FileNotFoundError):
        st.error("Chave de API da OpenAI não encontrada. Configure-a no .env ou nos segredos do Streamlit.")
        st.stop()

ASSISTANT_ID = "asst_rUreeoWsgwlPaxuJ7J7jYTBC"

db.init_db()

# --- CORREÇÃO: Lógica para recarregar credenciais após o registo ---
# Carrega as credenciais do banco de dados. Esta é a fonte da verdade.
credentials = db.get_user_credentials()

# Se um registo acabou de acontecer, o estado da sessão terá esta flag.
# Forçamos a recriação do autenticador com as novas credenciais.
if 'just_registered' in st.session_state and st.session_state['just_registered']:
    # Limpa a flag para não entrar neste loop novamente
    del st.session_state['just_registered']
    # Recarrega as credenciais para garantir que o novo usuário está incluído
    credentials = db.get_user_credentials()

authenticator = stauth.Authenticate(
    credentials,
    'mestre_gestor_cookie',
    'mestre_gestor_key',
    30
)

# --- FUNÇÃO DE AVALIAÇÃO AUTOMÁTICA ---
def evaluate_user_response(username, conversation_history, client):
    """
    Usa um modelo de IA para avaliar a última resposta do usuário e a classifica
    como 'acerto' ou 'erro', registando-a no banco de dados.
    """
    history_for_eval = [
        {"role": msg["role"], "content": msg["content"]} for msg in conversation_history[-4:]
    ]

    system_prompt = """
    Você é um avaliador especialista em simulações de gestão. Sua tarefa é analisar a última resposta do usuário no contexto da conversa e classificá-la como 'acerto' ou 'erro'.
    - 'acerto' significa que o usuário tomou uma decisão de gestão boa, lógica ou estratégica.
    - 'erro' significa que a decisão foi fraca, ilógica ou prejudicial.
    Responda APENAS com a palavra 'acerto' ou 'erro', em minúsculas e sem nenhuma outra explicação ou pontuação.
    """
    
    eval_prompt = [{"role": "system", "content": system_prompt}] + history_for_eval

    try:
        response = client.chat.completions.create(
            model=EVALUATION_MODEL,
            messages=eval_prompt,
            max_tokens=5,
            temperature=0
        )
        evaluation = response.choices[0].message.content.strip().lower()
        
        if evaluation in ['acerto', 'erro']:
            db.log_user_action(username, "avaliacao_automatica", evaluation)
            return evaluation
        else:
            return None
            
    except Exception as e:
        st.warning(f"Erro na avaliação automática: {e}")
        return None

# --- NAVEGAÇÃO E PÁGINAS ---
choice = st.sidebar.radio("Navegação", ['Login', 'Registrar'])

# --- PÁGINA DE LOGIN ---
if choice == 'Login':
    name, authentication_status, username = authenticator.login('main')

    if authentication_status:
        st.session_state['name'] = name
        st.session_state['username'] = username
        st.session_state['authentication_status'] = authentication_status
        
        authenticator.logout('Logout', 'sidebar')
        st.sidebar.title(f"Bem-vindo(a) {st.session_state['name']}!")
        
        if "thread_id" not in st.session_state:
            st.session_state.thread_id = db.get_or_create_thread_id(username, client)
        if "messages" not in st.session_state:
            st.session_state.messages = db.get_user_history(username)

        st.title("Simulador Gestor - Assistente de casos")

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Vamos iniciar a simulação, digite algo para começar:"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            db.add_message_to_history(username, "user", prompt)

            with st.spinner("A avaliar a sua decisão..."):
                evaluation_result = evaluate_user_response(username, st.session_state.messages, client)
            
            if evaluation_result:
                if evaluation_result == 'acerto':
                    st.toast("✅ Boa decisão!")
                else:
                    st.toast("⚠️ Decisão questionável.")

            with st.chat_message("assistant"):
                def stream_generator():
                    with client.beta.threads.runs.stream(
                        thread_id=st.session_state.thread_id,
                        assistant_id=ASSISTANT_ID,
                    ) as stream:
                        for text in stream.text_deltas:
                            yield text
                            time.sleep(0.01)
                
                client.beta.threads.messages.create(
                    thread_id=st.session_state.thread_id,
                    role="user",
                    content=prompt
                )
                
                response = st.write_stream(stream_generator)

            st.session_state.messages.append({"role": "assistant", "content": response})
            db.add_message_to_history(username, "assistant", response)
            st.rerun()

    elif authentication_status is False:
        st.error('Usuário ou senha incorretos')
    elif authentication_status is None:
        st.warning('Por favor, insira seu usuário e senha')

# --- PÁGINA DE REGISTRO ---
elif choice == 'Registrar':
    st.title("Crie sua Conta")
    try:
        with st.form("register_form"):
            new_name = st.text_input("Nome Completo")
            new_email = st.text_input("E-mail")
            new_username = st.text_input("Nome de Usuário")
            new_password = st.text_input("Senha", type="password")
            confirm_password = st.text_input("Confirme a Senha", type="password")
            submitted = st.form_submit_button("Registrar")

            if submitted:
                if new_password == confirm_password and new_password != "":
                    hashed_password = Hasher([new_password]).generate()[0]
                    if db.add_user(new_username, new_name, new_email, hashed_password):
                        st.success("Usuário registrado com sucesso! Por favor, volte para a tela de Login.")
                        # --- CORREÇÃO: Define a flag para forçar a recarga na próxima execução ---
                        st.session_state['just_registered'] = True
                        time.sleep(2) # Dá tempo para o usuário ler a mensagem
                        st.rerun() # Força a reexecução do script
                    else:
                        st.error("Nome de usuário ou e-mail já existe.")
                else:
                    st.error("As senhas não coincidem ou estão em branco.")
    except Exception as e:
        st.error(f"Ocorreu um erro durante o registro: {e}")
