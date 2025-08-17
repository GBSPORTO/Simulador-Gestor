import sqlite3
import hashlib
import pandas as pd
from datetime import datetime
import os

# Nome do arquivo do banco de dados
DB_NAME = "leadership_simulator.db"

def init_database():
    """Inicializa o banco de dados criando as tabelas necessárias"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Tabela de usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Tabela de mensagens/conversas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users (username)
            )
        ''')
        
        # Tabela de ações dos usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_data TEXT,
                outcome TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users (username)
            )
        ''')
        
        # Tabela de threads do OpenAI
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                thread_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users (username)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Banco de dados inicializado com sucesso")
        
    except Exception as e:
        print(f"❌ Erro ao inicializar banco de dados: {e}")

def hash_password(password):
    """Cria hash da senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_user_exists(username=None, email=None):
    """
    Verifica se usuário ou email já existem no banco
    Retorna: (user_exists, email_exists)
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        user_exists = False
        email_exists = False
        
        if username:
            cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(username) = LOWER(?)", (username,))
            user_exists = cursor.fetchone()[0] > 0
        
        if email:
            cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            email_exists = cursor.fetchone()[0] > 0
        
        conn.close()
        return user_exists, email_exists
        
    except Exception as e:
        print(f"Erro ao verificar usuário: {e}")
        return False, False

def create_user(username, email, password, is_admin=False):
    """
    Cria novo usuário no banco de dados
    Retorna: (success, message)
    """
    try:
        # Validações básicas
        if not username or not email or not password:
            return False, "Todos os campos são obrigatórios"
        
        if len(username) < 3:
            return False, "Nome de usuário deve ter pelo menos 3 caracteres"
        
        if len(password) < 6:
            return False, "Senha deve ter pelo menos 6 caracteres"
        
        # Verifica se já existem
        user_exists, email_exists = check_user_exists(username, email)
        
        if user_exists and email_exists:
            return False, "Nome de usuário e e-mail já existem"
        elif user_exists:
            return False, "Nome de usuário já existe"
        elif email_exists:
            return False, "E-mail já existe"
        
        # Cria o usuário
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        password_hash = hash_password(password)
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, is_admin)
            VALUES (?, ?, ?, ?)
        ''', (username, email, password_hash, is_admin))
        
        conn.commit()
        conn.close()
        
        return True, "Usuário criado com sucesso"
        
    except sqlite3.IntegrityError as e:
        if "username" in str(e).lower():
            return False, "Nome de usuário já existe"
        elif "email" in str(e).lower():
            return False, "E-mail já existe"
        else:
            return False, "Erro de integridade no banco de dados"
    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        return False, "Erro interno do servidor"

def authenticate_user(username, password):
    """
    Autentica usuário
    Retorna: (success, user_data or error_message)
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        password_hash = hash_password(password)
        
        cursor.execute('''
            SELECT username, email, is_admin 
            FROM users 
            WHERE LOWER(username) = LOWER(?) AND password_hash = ?
        ''', (username, password_hash))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return True, {
                'username': user[0],
                'email': user[1],
                'is_admin': user[2]
            }
        else:
            return False, "Nome de usuário ou senha incorretos"
            
    except Exception as e:
        print(f"Erro na autenticação: {e}")
        return False, "Erro interno do servidor"

def save_conversation(username, role, content):
    """Salva mensagem da conversa"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO conversations (username, role, content)
            VALUES (?, ?, ?)
        ''', (username, role, content))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Erro ao salvar conversa: {e}")
        return False

def get_user_history(username):
    """Busca histórico de conversas do usuário"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT role, content, timestamp 
            FROM conversations 
            WHERE username = ? 
            ORDER BY timestamp DESC
            LIMIT 50
        ''', (username,))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                'role': row[0],
                'content': row[1],
                'timestamp': row[2]
            })
        
        conn.close()
        return messages
        
    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
        return []

def save_user_action(username, action_type, action_data=None, outcome=None):
    """Salva ação do usuário"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_actions (username, action_type, action_data, outcome)
            VALUES (?, ?, ?, ?)
        ''', (username, action_type, action_data, outcome))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Erro ao salvar ação: {e}")
        return False

def get_all_user_actions():
    """Busca todas as ações dos usuários para análise"""
    try:
        conn = sqlite3.connect(DB_NAME)
        
        df = pd.read_sql_query('''
            SELECT * FROM user_actions 
            ORDER BY timestamp DESC
        ''', conn)
        
        conn.close()
        return df
        
    except Exception as e:
        print(f"Erro ao buscar ações: {e}")
        return pd.DataFrame()

def get_user_stats(username):
    """Busca estatísticas específicas do usuário"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Total de ações
        cursor.execute("SELECT COUNT(*) FROM user_actions WHERE username = ?", (username,))
        total_actions = cursor.fetchone()[0]
        
        # Acertos
        cursor.execute("SELECT COUNT(*) FROM user_actions WHERE username = ? AND outcome = 'acerto'", (username,))
        total_acertos = cursor.fetchone()[0]
        
        # Taxa de acerto
        taxa_acerto = (total_acertos / total_actions * 100) if total_actions > 0 else 0
        
        conn.close()
        
        return {
            'total_actions': total_actions,
            'total_acertos': total_acertos,
            'taxa_acerto': taxa_acerto
        }
        
    except Exception as e:
        print(f"Erro ao buscar stats do usuário: {e}")
        return {'total_actions': 0, 'total_acertos': 0, 'taxa_acerto': 0}

def reset_database():
    """CUIDADO: Apaga todo o banco de dados"""
    try:
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
        init_database()
        print("✅ Banco de dados resetado")
        
    except Exception as e:
        print(f"❌ Erro ao resetar banco: {e}")

def list_all_users():
    """Lista todos os usuários (admin only)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("SELECT username, email, created_at, is_admin FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        
        conn.close()
        return users
        
    except Exception as e:
        print(f"Erro ao listar usuários: {e}")
        return []

def delete_user(username):
    """Deleta usuário e seus dados (admin only)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Deleta conversas
        cursor.execute("DELETE FROM conversations WHERE username = ?", (username,))
        
        # Deleta ações
        cursor.execute("DELETE FROM user_actions WHERE username = ?", (username,))
        
        # Deleta usuário
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        
        conn.commit()
        conn.close()
        
        return True, "Usuário deletado com sucesso"
        
    except Exception as e:
        print(f"Erro ao deletar usuário: {e}")
        return False, "Erro ao deletar usuário"

# Funções adicionais para compatibilidade com o rpg_gestor.py
def get_or_create_thread_id(username, client):
    """Busca ou cria thread ID para o usuário"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Verifica se existe thread para o usuário
        cursor.execute("SELECT thread_id FROM user_threads WHERE username = ?", (username,))
        result = cursor.fetchone()
        
        if result:
            thread_id = result[0]
        else:
            # Cria novo thread
            thread = client.beta.threads.create()
            thread_id = thread.id
            
            # Salva no banco
            cursor.execute("INSERT INTO user_threads (username, thread_id) VALUES (?, ?)", 
                          (username, thread_id))
            conn.commit()
        
        conn.close()
        return thread_id
        
    except Exception as e:
        print(f"Erro ao obter thread ID: {e}")
        # Cria thread temporário se houver erro
        thread = client.beta.threads.create()
        return thread.id

def add_message_to_history(username, role, content):
    """Adiciona mensagem ao histórico"""
    return save_conversation(username, role, content)

def log_user_action(username, action_type, action_data):
    """Log de ações do usuário"""
    return save_user_action(username, action_type, action_data)

def get_all_user_evaluations():
    """Busca avaliações de todos os usuários"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                u.username, 
                u.username as name,  -- Usando username como fallback para name
                u.email,
                COUNT(CASE WHEN ua.action_data = 'acerto' THEN 1 END) as acertos,
                COUNT(CASE WHEN ua.action_data = 'erro' THEN 1 END) as erros,
                COUNT(ua.action_data) as total_decisions,
                MAX(ua.timestamp) as last_activity
            FROM users u
            LEFT JOIN user_actions ua ON u.username = ua.username 
            WHERE ua.action_type = 'avaliacao_automatica' OR ua.action_type IS NULL
            GROUP BY u.username, u.email
            ORDER BY total_decisions DESC
        ''')
        
        results = cursor.fetchall()
        user_stats = []
        
        for row in results:
            user_stats.append({
                'username': row[0],
                'name': row[1] or 'N/A',
                'email': row[2],
                'acertos': row[3] or 0,
                'erros': row[4] or 0, 
                'total_decisions': row[5] or 0,
                'last_activity': row[6] or 'Nunca'
            })
        
        conn.close()
        return user_stats
        
    except Exception as e:
        print(f"Erro ao obter avaliações: {e}")
        return []

# Inicializa o banco quando o módulo é importado
if __name__ == "__main__":
    init_database()
else:
    init_database()

