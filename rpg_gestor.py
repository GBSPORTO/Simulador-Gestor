import streamlit as st
import openai
import time
import streamlit_authenticator as stauth
import database as db
from dotenv import load_dotenv, find_dotenv
import os

# --- INICIALIZAÇÃO E CONFIGURAÇÃO ---
# Carrega variáveis de ambiente (sua chave da OpenAI)
load_dotenv(find_dotenv())
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    client = openai.Client(api_key=api_key)
else:
    st.error("Chave de API da OpenAI não encontrada. Crie um arquivo .env ou configure nos segredos do Streamlit.")

# ID do seu assistente
ASSISTANT_ID = "asst_rUreeoWsgwlPaxuJ7J7jYTBC"

# Inicializa o banco de dados
db.init_db()

# Carrega as credenciais do banco de dados para o autenticador
credentials = db.get_user_credentials()
authenticator = stauth.Authenticate(
    credentials,
    'mestre_gestor_cookie',
    'mestre_gestor_key',
    30
)

# --- NAVEGAÇÃO E PÁGINAS ---
choice = st.sidebar.radio("Navegação", ['Login', 'Registrar'])

# --- PÁGINA DE LOGIN ---
if choice == 'Login':
    authenticator.login('main')

    if st.session_state["authentication_status"]:
        # --- SE O LOGIN FOR BEM-SUCEDIDO, MOSTRA O CHAT ---
        username = st.session_state['username']
        
        authenticator.logout('Logout', 'sidebar')
        st.sidebar.title(f"Bem-vindo(a) {st.session_state['name']}!")
        
        # Carrega ou cria a thread do usuário
        if "thread_id" not in st.session_state:
            st.session_state.thread_id = db.get_or_create_thread_id(username, client)
        
        # Carrega o histórico de mensagens do usuário
        if "messages" not in st.session_state:
            st.session_state.messages = db.get_user_history(username)

        st.title("Simulador Gestor - Assistente de casos")

        # Exibe o histórico de mensagens
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Input do usuário
        if prompt := st.chat_input("Vamos iniciar a simulação, digite algo para começar:"):
            # Adiciona e salva a mensagem do usuário
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            db.add_message_to_history(username, "user", prompt)

            # Exibe a resposta do assistente com streaming
            with st.chat_message("assistant"):
                # Função geradora para o streaming
                def stream_generator():
                    with client.beta.threads.runs.stream(
                        thread_id=st.session_state.thread_id,
                        assistant_id=ASSISTANT_ID,
                    ) as stream:
                        for text in stream.text_deltas:
                            yield text
                            time.sleep(0.01)
                
                # Adiciona a mensagem do usuário à thread antes de executar o stream
                client.beta.threads.messages.create(
                    thread_id=st.session_state.thread_id,
                    role="user",
                    content=prompt
                )
                
                response = st.write_stream(stream_generator)

            # Adiciona e salva a resposta completa do assistente
            st.session_state.messages.append({"role": "assistant", "content": response})
            db.add_message_to_history(username, "assistant", response)
            
            # Força o rerender para mostrar os botões de feedback
            st.rerun()

        # --- BOTÕES DE FEEDBACK ---
        # Só mostra os botões se a última mensagem for do assistente
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
            st.divider()
            st.write("A resposta do assistente foi útil?")
            col1, col2 = st.columns(2)
            if col1.button("Sim, foi um acerto 👍"):
                db.log_user_action(username, "avaliacao_resposta", "acerto")
                st.success("Feedback registrado!")
                time.sleep(1)
                st.rerun()

            if col2.button("Não, foi um erro 👎"):
                db.log_user_action(username, "avaliacao_resposta", "erro")
                st.error("Feedback registrado.")
                time.sleep(1)
                st.rerun()

    elif st.session_state["authentication_status"] is False:
        st.error('Usuário ou senha incorretos')
    elif st.session_state["authentication_status"] is None:
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
                    hashed_password = stauth.Hasher([new_password]).generate()[0]
                    if db.add_user(new_username, new_name, new_email, hashed_password):
                        st.success("Usuário registrado com sucesso! Volte para a tela de Login para entrar.")
                    else:
                        st.error("Nome de usuário ou e-mail já existe.")
                else:
                    st.error("As senhas não coincidem ou estão em branco.")
    except Exception as e:
        st.error(e)
