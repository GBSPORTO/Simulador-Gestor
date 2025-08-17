# rpg_gestor.py
import streamlit as st
import openai
import time
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.hasher import Hasher
import database as db
from dotenv import load_dotenv, find_dotenv
import os
import hashlib

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
EVALUATION_MODEL = "gpt-4-turbo"

# --- INICIALIZAÇÃO ---
client = init_openai_client()

# --- FUNÇÕES DE AUTENTICAÇÃO MELHORADAS ---
def manual_login(username, password):
    """
    Sistema de login manual que funciona independente de cookies
    """
    try:
        success, user_data = db.authenticate_user(username, password)
        
        if success:
            # Armazena dados do usuário no session_state
            st.session_state.update({
                'authentication_status': True,
                'username': user_data['username'],
                'name': user_data['name'],
                'email': user_data['email'],
                'is_admin': user_data.get('is_admin', False),
                'manual_login': True
            })
            return True, user_data
        else:
            return False, user_data
            
    except Exception as e:
        return False, f"Erro no login: {str(e)}"

def manual_logout():
    """Logout manual limpando session_state"""
    keys_to_clear = [
        'authentication_status', 'username', 'name', 'email', 
        'is_admin', 'manual_login', 'thread_id', 'messages'
    ]
    
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()

def check_user_exists_for_registration(username, email):
    """
    Verifica se usuário já existe, mas com mensagens mais específicas
    """
    try:
        user_exists, email_exists = db.check_user_exists(username, email)
        
        if user_exists and email_exists:
            return True, "Este usuário e e-mail já estão registrados. Tente fazer login."
        elif user_exists:
            return True, f"O usuário '{username}' já existe. Escolha outro nome de usuário."
        elif email_exists:
            return True, f"O e-mail '{email}' já está registrado. Use outro e-mail ou faça login."
        else:
            return False, "OK"
            
    except Exception as e:
        return True, f"Erro ao verificar usuário: {e}"

def create_authenticator():
    """Cria o autenticador com configuração otimizada para múltiplos dispositivos"""
    credentials = get_formatted_credentials()
    
    # Configuração com cookie mais específico
    config = {
        'credentials': credentials,
        'cookie': {
            'name': f'simulator_auth_{hashlib.md5("leadership_sim".encode()).hexdigest()[:8]}',
            'key': 'leadership_simulator_secret_key_2024', 
            'expiry_days': 7  # Reduzido para evitar problemas
        }
    }
    
    try:
        return stauth.Authenticate(
            config['credentials'],
            config['cookie']['name'],
            config['cookie']['key'],
            config['cookie']['expiry_days']
        )
    except Exception as e:
        st.error(f"Erro ao criar autenticador: {e}")
        return None

def get_formatted_credentials():
    """Obtém credenciais formatadas para o streamlit-authenticator"""
    try:
        return db.get_formatted_credentials_for_auth()
    except Exception as e:
        st.error(f"Erro ao obter credenciais: {e}")
        return {'usernames': {}}

# --- FUNÇÕES EXISTENTES (mantidas) ---
def evaluate_user_response_background(username, conversation_history, client):
    """Avaliação em background da resposta do usuário"""
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
            return evaluation
        else:
            return None
            
    except Exception as e:
        return None

def initialize_session_state(username):
    """Inicializa o estado da sessão para o usuário"""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = db.get_or_create_thread_id(username, client)
    if "messages" not in st.session_state:
        st.session_state.messages = db.get_user_history(username)

def handle_chat_interaction(username, prompt):
    """Lida com a interação do chat"""
    st.session_state.messages.append({"role": "user", "content": prompt})
    db.add_message_to_history(username, "user", prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    try:
        evaluate_user_response_background(username, st.session_state.messages, client)
    except:
        pass
    
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
    """Dashboard com estatísticas"""
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

def register_user(name, username, email, password):
    """Registra novo usuário"""
    try:
        success, message = db.create_user(
            username=username,
            email=email,
            password=password,
            is_admin=False,
            name=name
        )
        return success, message
    except Exception as e:
        return False, f"Erro no registro: {str(e)}"

# --- APLICAÇÃO PRINCIPAL REFORMULADA ---
def main():
    st.set_page_config(
        page_title="Simulador de Casos",
        page_icon="🎯",
        layout="wide"
    )
    
    # CSS para melhorar a aparência
    st.markdown("""
    <style>
    .auth-info {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Verifica se o usuário está logado (manual ou por cookie)
    is_logged_in = st.session_state.get('authentication_status', False)
    
    if is_logged_in:
        # === USUÁRIO LOGADO ===
        st.sidebar.title(f"👋 Olá, {st.session_state.get('name', 'Usuário')}!")
        st.sidebar.markdown("---")
        
        # Informações do usuário
        with st.sidebar.expander("ℹ️ Informações da Conta"):
            st.write(f"**Usuário:** {st.session_state.get('username', 'N/A')}")
            st.write(f"**Nome:** {st.session_state.get('name', 'N/A')}")
            st.write(f"**Email:** {st.session_state.get('email', 'N/A')}")
        
        # Botão de logout
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            manual_logout()
        
        st.sidebar.markdown("---")
        
        # Menu principal
        page_choice = st.sidebar.selectbox(
            "📋 Menu Principal:",
            ['🎯 Simulação', '📊 Dashboard'],
            key="main_menu"
        )
        
        if page_choice == '🎯 Simulação':
            initialize_session_state(st.session_state['username'])
            
            st.title("🎯 Simulador de Casos - Treinamento")
            st.markdown("---")
            
            # Exibe histórico
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
            
            # Input do usuário
            if prompt := st.chat_input("Digite sua resposta para continuar a simulação:"):
                handle_chat_interaction(st.session_state['username'], prompt)
                st.rerun()
        
        elif page_choice == '📊 Dashboard':
            show_dashboard()
    
    else:
        # === USUÁRIO NÃO LOGADO ===
        
        # Opção de usar autenticador tradicional ou login manual
        auth_method = st.sidebar.radio(
            "🔐 Método de Autenticação:",
            ['Manual (Recomendado)', 'Automático (Cookies)'],
            help="Manual funciona em qualquer dispositivo, Automático usa cookies"
        )
        
        if auth_method == 'Manual (Recomendado)':
            # === LOGIN/REGISTRO MANUAL ===
            
            choice = st.sidebar.selectbox(
                "Navegação:",
                ['🔐 Login', '📝 Registrar'],
                key="manual_auth_menu"
            )
            
            if choice == '🔐 Login':
                st.title("🔐 Login Manual")
                st.markdown('<div class="auth-info">✨ Este método funciona em qualquer dispositivo!</div>', unsafe_allow_html=True)
                st.markdown("---")
                
                with st.form("manual_login_form"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        username = st.text_input("👤 Usuário", placeholder="Seu nome de usuário")
                        password = st.text_input("🔒 Senha", type="password", placeholder="Sua senha")
                    
                    with col2:
                        st.markdown("**🔧 Problemas?**")
                        st.markdown("• Verifique usuário/senha")
                        st.markdown("• Registre-se se necessário")
                    
                    login_button = st.form_submit_button("🚀 Entrar", use_container_width=True)
                
                if login_button:
                    if username and password:
                        with st.spinner("Verificando credenciais..."):
                            success, result = manual_login(username, password)
                        
                        if success:
                            st.success(f"✅ Login realizado com sucesso! Bem-vindo(a), {result['name']}!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ {result}")
                    else:
                        st.error("❌ Por favor, preencha usuário e senha.")
            
            elif choice == '📝 Registrar':
                st.title("📝 Criar Nova Conta")
                st.markdown('<div class="auth-info">🎯 Registre-se para começar a usar o simulador!</div>', unsafe_allow_html=True)
                st.markdown("---")
                
                with st.form("manual_register_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_name = st.text_input("📛 Nome Completo", placeholder="João Silva")
                        new_username = st.text_input("👤 Nome de Usuário", placeholder="joao_silva", help="Será usado para login")
                    
                    with col2:
                        new_email = st.text_input("📧 E-mail", placeholder="joao@email.com")
                        new_password = st.text_input("🔒 Senha", type="password", placeholder="Mín. 6 caracteres")
                    
                    confirm_password = st.text_input("🔒 Confirmar Senha", type="password", placeholder="Digite a senha novamente")
                    
                    register_button = st.form_submit_button("🚀 Registrar", use_container_width=True)
                
                if register_button:
                    if not all([new_name, new_email, new_username, new_password]):
                        st.error("❌ Por favor, preencha todos os campos.")
                    elif new_password != confirm_password:
                        st.error("❌ As senhas não coincidem.")
                    elif len(new_password) < 6:
                        st.error("❌ A senha deve ter pelo menos 6 caracteres.")
                    else:
                        # Verifica se usuário já existe
                        with st.spinner("Verificando disponibilidade..."):
                            exists, message = check_user_exists_for_registration(new_username, new_email)
                        
                        if exists:
                            st.error(f"❌ {message}")
                        else:
                            with st.spinner("Criando conta..."):
                                success, result = register_user(new_name, new_username, new_email, new_password)
                            
                            if success:
                                st.success("✅ Conta criada com sucesso! Agora você pode fazer login.")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"❌ {result}")
        
        else:
            # === AUTENTICAÇÃO POR COOKIES (TRADICIONAL) ===
            st.title("🔐 Autenticação Automática")
            st.markdown('<div class="auth-info">⚠️ Este método usa cookies. Pode não funcionar em alguns dispositivos/navegadores.</div>', unsafe_allow_html=True)
            
            try:
                authenticator = create_authenticator()
                
                if authenticator:
                    name, authentication_status, username = authenticator.login(location='main')
                    
                    if authentication_status == True:
                        st.session_state.update({
                            'name': name,
                            'username': username,
                            'authentication_status': authentication_status,
                            'manual_login': False
                        })
                        st.success(f"✅ Login automático realizado! Bem-vindo(a), {name}!")
                        time.sleep(1)
                        st.rerun()
                    
                    elif authentication_status == False:
                        st.error('❌ Usuário ou senha incorretos')
                        st.info("💡 Experimente o **Login Manual** na barra lateral se continuar com problemas.")
                    
                    elif authentication_status == None:
                        st.warning('⚠️ Por favor, insira seu usuário e senha')
                
                else:
                    st.error("❌ Erro no sistema de autenticação")
                    st.info("💡 Use o **Login Manual** na barra lateral.")
            
            except Exception as e:
                st.error(f"❌ Erro na autenticação automática: {str(e)}")
                st.info("💡 Recomendamos usar o **Login Manual** na barra lateral.")

if __name__ == "__main__":
    main()
