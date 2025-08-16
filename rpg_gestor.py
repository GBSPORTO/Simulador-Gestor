def show_dashboard():
    """Exibe o dashboard com estatísticas de todos os usuários"""
    st.title("📊 Dashboard de Análise")
    st.markdown("---")
    
    try:
        # Obtém dados de avaliação de todos os usuários
        user_stats = db.get_all_user_evaluations()  # Você precisará implementar esta função no database.py
        
        if not user_stats:
            st.info("📝 Ainda não há dados de avaliação disponíveis.")
            return
        
        # Métricas gerais
        col1, col2, col3, col4 = st.columns(4)
        
        total_decisions = sum(user['total_decisions'] for user in user_stats)
        total_hits = sum(user['acertos'] for user in user_stats)
        total_misses = sum(user['erros'] for user in user_stats)
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
        
        # Tabela de usuários
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
        
        # Gráficos
        if len(df_data) > 0:
            st.markdown("---")
            st.subheader("📊 Visualizações")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Distribuição de Acertos vs Erros**")
                chart_data = pd.DataFrame({
                    'Usuário': [user['username'] for user in user_stats],
                    'Acertos': [user['acertos'] for user in user_stats],
                    'Erros': [user['erros'] for user in user_stats]
                })
                st.bar_chart(chart_data.set_index('Usuário'))
            
            with col2:
                st.markdown("**Taxa de Acerto por Usuário**")
                accuracy_data = pd.DataFrame({
                    'Usuário': [user['username'] for user in user_stats],
                    'Taxa de Acerto (%)': [(user['acertos'] / user['total_decisions'] * 100) if user['total_decisions'] > 0 else 0 for user in user_stats]
                })
                st.bar_chart(accuracy_data.set_index('Usuário'))
        
    except Exception as e:
        st.error(f"Erro ao carregar dashboard: {e}")
        st.info("🔧 Certifique-se de que a função `get_all_user_evaluations()` está implementada no database.py")# rpg_gestor.py
import streamlit as st
import openai
import time
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.hasher import Hasher
import database as db
from dotenv import load_dotenv, find_dotenv
import os

# --- INICIALIZAÇÃO E CONFIGURAÇÃO ---
@st.cache_resource
def init_openai_client():
    """Inicializa o cliente OpenAI de forma cached"""
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
EVALUATION_MODEL = "gpt-4-turbo"  # Mantendo GPT-4 para avaliação consistente

# --- INICIALIZAÇÃO ---
client = init_openai_client()
db.init_db()

# --- FUNÇÕES AUXILIARES ---
def get_formatted_credentials():
    """
    Obtém as credenciais do banco de dados e as formata corretamente
    para o streamlit-authenticator
    """
    try:
        raw_credentials = db.get_user_credentials()
        
        # Verifica se as credenciais estão no formato correto
        if not raw_credentials or 'usernames' not in raw_credentials:
            return {
                'usernames': {},
                'names': [],
                'emails': []
            }
        
        # Garante que a estrutura está correta
        formatted_credentials = {
            'usernames': raw_credentials.get('usernames', {}),
            'names': list(raw_credentials.get('usernames', {}).keys()),
            'emails': [user_data.get('email', '') for user_data in raw_credentials.get('usernames', {}).values()]
        }
        
        return formatted_credentials
        
    except Exception as e:
        st.error(f"Erro ao obter credenciais: {e}")
        return {
            'usernames': {},
            'names': [],
            'emails': []
        }

def create_authenticator():
    """Cria o autenticador com as credenciais atuais"""
    credentials = get_formatted_credentials()
    
    return stauth.Authenticate(
        credentials,
        'mestre_gestor_cookie',
        'mestre_gestor_key',
        30
    )

def evaluate_user_response_background(username, conversation_history, client):
    """
    Usa um modelo de IA para avaliar a última resposta do usuário e a classifica
    como 'acerto' ou 'erro', registando-a no banco de dados.
    Esta função roda em background sem mostrar feedback direto ao usuário.
    """
    try:
        # Pega apenas as últimas 4 mensagens para contexto
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
            return evaluation
        else:
            return None
            
    except Exception as e:
        # Silencioso - não mostra erro para o usuário na simulação
        return None

def initialize_session_state(username):
    """Inicializa o estado da sessão para o usuário"""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = db.get_or_create_thread_id(username, client)
    if "messages" not in st.session_state:
        st.session_state.messages = db.get_user_history(username)

def handle_chat_interaction(username, prompt):
    """Lida com a interação do chat"""
    # Adiciona mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    db.add_message_to_history(username, "user", prompt)
    
    # Exibe mensagem do usuário
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Avalia a resposta do usuário em background (sem feedback visual)
    try:
        evaluate_user_response_background(username, st.session_state.messages, client)
    except:
        pass  # Silencioso - não afeta a experiência do usuário
    
    # Gera resposta do assistente
    with st.chat_message("assistant"):
        def stream_generator():
            try:
                # Usando a API Assistants v2 (compatível com v4.1)
                with client.beta.threads.runs.stream(
                    thread_id=st.session_state.thread_id,
                    assistant_id=ASSISTANT_ID,
                ) as stream:
                    for text in stream.text_deltas:
                        yield text
                        time.sleep(0.01)
            except Exception as e:
                yield f"Erro na comunicação com o assistente: {e}"
        
        # Cria mensagem no thread usando a API v2
        try:
            client.beta.threads.messages.create(
                thread_id=st.session_state.thread_id,
                role="user",
                content=prompt
            )
        except Exception as e:
            st.error(f"Erro ao comunicar com o assistente: {e}")
            return
        
        response = st.write_stream(stream_generator)
    
    # Salva resposta do assistente
    st.session_state.messages.append({"role": "assistant", "content": response})
    db.add_message_to_history(username, "assistant", response)

# --- APLICAÇÃO PRINCIPAL ---
def main():
    st.set_page_config(
        page_title="Simulador de Casos",
        page_icon="🎯",
        layout="wide"
    )
    
    # Recarrega credenciais se necessário
    if 'just_registered' in st.session_state and st.session_state['just_registered']:
        st.session_state['just_registered'] = False
        st.cache_resource.clear()  # Limpa cache se necessário
    
    # Cria autenticador
    authenticator = create_authenticator()
    
    # --- NAVEGAÇÃO ---
    choice = st.sidebar.radio("Navegação", ['Login', 'Registrar'])
    
    # --- PÁGINA DE LOGIN ---
    if choice == 'Login':
        try:
            name, authentication_status, username = authenticator.login('main')
        except Exception as e:
            st.error("Erro no sistema de login. Tente novamente ou registre-se.")
            return

        if authentication_status:
            # Usuário autenticado
            st.session_state.update({
                'name': name,
                'username': username,
                'authentication_status': authentication_status
            })
            
            authenticator.logout('Logout', 'sidebar')
            st.sidebar.title(f"Bem-vindo(a) {name}!")
            
            # --- SUBMENU APÓS LOGIN ---
            page_choice = st.sidebar.radio("Simulador de Casos", ['Simulação', 'Dashboard'])
            
            if page_choice == 'Simulação':
                # Inicializa estado da sessão
                initialize_session_state(username)
                
                # Interface principal
                st.title("🎯 Simulador de Casos - Treinamento")
                st.markdown("---")
                
                # Exibe histórico de mensagens
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
                
                # Input do usuário
                if prompt := st.chat_input("Digite sua resposta para continuar a simulação:"):
                    handle_chat_interaction(username, prompt)
                    st.rerun()
            
            elif page_choice == 'Dashboard':
                show_dashboard()

        elif authentication_status is False:
            st.error('❌ Usuário ou senha incorretos')
        elif authentication_status is None:
            st.warning('⚠️ Por favor, insira seu usuário e senha')

    # --- PÁGINA DE REGISTRO ---
    elif choice == 'Registrar':
        st.title("📝 Crie sua Conta")
        st.markdown("---")
        
        with st.form("register_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                new_name = st.text_input("Nome Completo", placeholder="João Silva")
                new_username = st.text_input("Nome de Usuário", placeholder="joao_silva")
            
            with col2:
                new_email = st.text_input("E-mail", placeholder="joao@email.com")
                
            new_password = st.text_input("Senha", type="password", placeholder="Digite uma senha segura")
            confirm_password = st.text_input("Confirme a Senha", type="password", placeholder="Confirme sua senha")
            
            submitted = st.form_submit_button("🚀 Registrar", use_container_width=True)

            if submitted:
                if not all([new_name, new_email, new_username, new_password]):
                    st.error("❌ Por favor, preencha todos os campos.")
                elif new_password != confirm_password:
                    st.error("❌ As senhas não coincidem.")
                elif len(new_password) < 6:
                    st.error("❌ A senha deve ter pelo menos 6 caracteres.")
                else:
                    try:
                        hashed_password = Hasher([new_password]).generate()[0]
                        
                        if db.add_user(new_username, new_name, new_email, hashed_password):
                            st.success("✅ Usuário registrado com sucesso! Redirecionando para o login...")
                            st.session_state['just_registered'] = True
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Nome de usuário ou e-mail já existe.")
                            
                    except Exception as e:
                        st.error(f"❌ Ocorreu um erro durante o registro: {e}")

if __name__ == "__main__":
    main()
