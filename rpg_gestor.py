import streamlit as st
import openai
from dotenv import load_dotenv, find_dotenv
import os
import time

# Carrega as variáveis de ambiente do arquivo .env
_=load_dotenv(find_dotenv())
client = openai.Client()
api_key = os.getenv("OPENAI_API_KEY")

# ID do seu assistente específico
ASSISTANT_ID = "asst_rUreeoWsgwlPaxuJ7J7jYTBC"

# --- INÍCIO DAS ALTERAÇÕES ---

# MUDANÇA 1: Inicializa o histórico de mensagens e o thread no estado da sessão
if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    try:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    except Exception as e:
        st.error(f"Erro ao criar a thread da OpenAI: {e}")
        st.stop()

# Função para gerar a resposta com streaming
def obter_resposta_openai(pergunta, thread_id):
    """
    Função para enviar a pergunta para o Assistant e gerar a resposta via streaming.
    """
    if not api_key:
        st.error("Chave de API da OpenAI não encontrada. Verifique seu arquivo .env")
        return

    try:
        # Adiciona a mensagem do usuário à thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=pergunta
        )

        # Usa a helper 'stream' para criar o run e lidar com os eventos
        with client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
        ) as stream:
            for text in stream.text_deltas:
                yield text
                time.sleep(0.01) # Pequeno delay para melhorar a fluidez da exibição

    except Exception as e:
        st.error(f"Ocorreu um erro ao contatar a API da OpenAI: {e}")

# --- FIM DAS ALTERAÇÕES ---

# Configura o título da página e o layout
st.set_page_config(page_title="Mestre Gestor", layout="wide")
st.title("Simulador Gestor - Assistente de casos")

# MUDANÇA 2: Exibe o histórico do chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Área para o usuário digitar a pergunta (usando st.chat_input)
if prompt := st.chat_input("Vamos iniciar a simulação, digite algo para começar:"):
    # Adiciona a mensagem do usuário ao histórico e exibe na tela
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Exibe a resposta do assistente usando o modo de streaming
    with st.chat_message("assistant"):
        # st.write_stream lida com o gerador e exibe o conteúdo em tempo real
        response = st.write_stream(obter_resposta_openai(prompt, st.session_state.thread_id))

    # Adiciona a resposta completa do assistente ao histórico
    st.session_state.messages.append({"role": "assistant", "content": response})