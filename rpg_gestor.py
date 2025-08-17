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

# --- FUNÇÕES AUXILIARES CORRIGIDAS ---
def get_formatted_credentials():
    """
    Obtém as credenciais do banco de dados e as formata corretamente
    para o streamlit-authenticator (FUNÇÃO CORRIGIDA)
    """
    try:
        # Usa a nova função específica do database.py
        return db.get_formatted_credentials_for_auth()
        
    except Exception as e:
        st.error(f"Erro ao obter credenciais: {e}")
        return {
            'usernames': {}
        }

def create_authenticator():
    """Cria o autenticador com as credenciais atuais"""
    credentials = get_formatted_credentials()
    
    config = {
        'credentials': credentials,
        'cookie': {
            'name': 'mestre_gestor_cookie',
            'key': 'mestre_gestor_key', 
            'expiry_days': 30
        }
    }
    
    return stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
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
        try:
            # Primeiro, cria mensagem no thread
            client.beta.threads.messages.create(
                thread_id=st.session_state.thread_id,
                role="user",
                content=prompt
            )
            
            # Depois, cria e executa a run
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
    
    # Salva resposta do assistente
    if response:
        st.session_state.messages.append({"role": "assistant", "content": response})
        db.add_message_to_history(username, "assistant", response)

def show_dashboard():
    """Exibe o dashboard com estatísticas de todos os usuários"""
    st.title("📊 Dashboard de Análise")
    st.markdown("---")
    
    try:
        user_stats = db.get_all_user_evaluations()
        
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
        st.info("🔧 Verifique se todas as tabelas necessárias estão criadas no banco de dados.")

def register_user(name, username, email, password):
    """
    Registra novo usuário no banco de dados (FUNÇÃO CORRIGIDA)
    """
    try:
        # Chama a função create_user com os parâmetros corretos
        success, message = db.create_user(
            username=username,
            email=email,
            password=password,
            is_admin=False,
            name=name  # Passa o nome como parâmetro
        )
        
        return success, message
        
    except Exception as e:
        return False, f"Erro no registro: {str(e)}"

# --- APLICAÇÃO PRINCIPAL ---
def main():
    st.set_page_config(
        page_title="Simulador de Casos",
        page_icon="🎯",
        layout="wide"
    )
    
    # Debug: Mostra informações sobre credenciais (apenas para admin)
    if st.query_params.get("debug") == "true":
        st.sidebar.markdown("### Debug Info")
        creds = get_formatted_credentials()
        st.sidebar.write(f"Usuários encontrados: {len(creds['usernames'])}")
        st.sidebar.write(list(creds['usernames'].keys()))
    
    # Recarrega credenciais se necessário
    if 'just_registered' in st.session_state and st.session_state['just_registered']:
        st.session_state['just_registered'] = False
        st.cache_resource.clear()
    
    # Cria autenticador
    try:
        authenticator = create_authenticator()
    except Exception as e:
        st.error(f"Erro ao criar autenticador: {e}")
        st.info("Verifique se o banco de dados está configurado corretamente.")
        
        # Botão para tentar corrigir o banco
        if st.button("🔧 Tentar Corrigir Banco de Dados"):
            try:
                db.init_database()
                st.success("✅ Banco de dados corrigido! Recarregue a página.")
                st.rerun()
            except Exception as fix_error:
                st.error(f"Erro ao corrigir banco: {fix_error}")
        return
    
    # Verifica se o usuário está logado
    if 'authentication_status' in st.session_state and st.session_state['authentication_status']:
        # USUÁRIO JÁ LOGADO
        st.sidebar.empty()
        
        authenticator.logout('Logout', 'sidebar')
        st.sidebar.title(f"Bem-vindo(a) {st.session_state['name']}!")
        st.sidebar.markdown("---")
        
        # Menu principal após login
        page_choice = st.sidebar.selectbox(
            "Escolha uma opção:",
            ['🎯 Simulação', '📊 Dashboard'],
            key="main_menu"
        )
        
        if page_choice == '🎯 Simulação':
            # Inicializa estado da sessão
            initialize_session_state(st.session_state['username'])
            
            # Interface principal
            st.title("🎯 Simulador de Casos - Treinamento")
            st.markdown("---")
            
            # Exibe histórico de mensagens
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
        # USUÁRIO NÃO LOGADO
        st.sidebar.empty()
        
        choice = st.sidebar.selectbox(
            "Navegação:",
            ['🔐 Login', '📝 Registrar'],
            key="auth_menu"
        )
        
        # --- PÁGINA DE LOGIN ---
        if choice == '🔐 Login':
            st.title("🔐 Login")
            st.markdown("---")
            
            try:
                name, authentication_status, username = authenticator.login(location='main')
                
                if authentication_status == True:
                    # Usuário autenticado
                    st.session_state.update({
                        'name': name,
                        'username': username,
                        'authentication_status': authentication_status
                    })
                    st.success(f"✅ Login realizado com sucesso! Bem-vindo(a), {name}!")
                    time.sleep(1)
                    st.rerun()

                elif authentication_status == False:
                    st.error('❌ Usuário ou senha incorretos')
                    
                    # Debug: Ajuda para resolução de problemas
                    with st.expander("🔧 Problemas com login?"):
                        st.write("1. Verifique se o usuário e senha estão corretos")
                        st.write("2. Certifique-se de que se registrou corretamente")
                        st.write("3. Tente registrar novamente se necessário")
                        
                elif authentication_status == None:
                    st.warning('⚠️ Por favor, insira seu usuário e senha')
                    
            except Exception as e:
                st.error(f"❌ Erro no sistema de login: {str(e)}")
                st.info("🔧 Tente se registrar novamente ou contate o administrador.")
                
                # Debug adicional
                if st.button("🔍 Ver Detalhes do Erro"):
                    st.code(str(e))

        # --- PÁGINA DE REGISTRO ---
        elif choice == '📝 Registrar':
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
                            success, message = register_user(new_name, new_username, new_email, new_password)
                            
                            if success:
                                st.success("✅ Usuário registrado com sucesso! Redirecionando para o login...")
                                st.session_state['just_registered'] = True
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                                
                        except Exception as e:
                            st.error(f"❌ Ocorreu um erro durante o registro: {e}")
                            
                            # Debug adicional
                            if st.button("🔍 Ver Detalhes do Erro de Registro"):
                                st.code(str(e))

if __name__ == "__main__":
    main()
