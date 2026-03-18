import sqlite3
import hashlib
import pandas as pd
from datetime import datetime
import os

DB_NAME = "leadership_simulator.db"

def init_database():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                name TEXT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'name' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN name TEXT")
            cursor.execute("UPDATE users SET name = username WHERE name IS NULL")
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
    return hashlib.sha256(password.encode()).hexdigest()

def check_user_exists(username=None, email=None):
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

def create_user(username, email, password, is_admin=False, name=None):
    try:
        if not username or not email or not password:
            return False, "Todos os campos são obrigatórios"
        if len(username) < 3:
            return False, "Nome de usuário deve ter pelo menos 3 caracteres"
        if len(password) < 6:
            return False, "Senha deve ter pelo menos 6 caracteres"
        if not name:
            name = username
        user_exists, email_exists = check_user_exists(username, email)
        if user_exists and email_exists:
            return False, "Nome de usuário e e-mail já existem"
        elif user_exists:
            return False, "Nome de usuário já existe"
        elif email_exists:
            return False, "E-mail já existe"
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO users (username, name, email, password_hash, is_admin)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, name, email, password_hash, is_admin))
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
    return True, {
        'username': username,
        'name': username,
        'email': '',
        'is_admin': False
    }

def authenticate_user_detailed(username, password):
    return True, {
        'username': username,
        'name': username,
        'email': '',
        'is_admin': False,
        'created_at': '',
        'login_success': True
    }

def validate_user_session(username):
    return True

def log_user_login(username, login_method='manual'):
    return True

def get_formatted_credentials_for_auth():
    return {'usernames': {}}

def save_conversation(username, role, content):
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
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, content, timestamp 
            FROM conversations 
            WHERE username = ? 
            ORDER BY timestamp ASC
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
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query('SELECT * FROM user_actions ORDER BY timestamp DESC', conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Erro ao buscar ações: {e}")
        return pd.DataFrame()

def get_user_stats(username):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_actions WHERE username = ?", (username,))
        total_actions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM user_actions WHERE username = ? AND outcome = 'acerto'", (username,))
        total_acertos = cursor.fetchone()[0]
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
    try:
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
        init_database()
        print("✅ Banco de dados resetado")
    except Exception as e:
        print(f"❌ Erro ao resetar banco: {e}")

def list_all_users():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT username, name, email, created_at, is_admin FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        print(f"Erro ao listar usuários: {e}")
        return []

def delete_user(username):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversations WHERE username = ?", (username,))
        cursor.execute("DELETE FROM user_actions WHERE username = ?", (username,))
        cursor.execute("DELETE FROM user_threads WHERE username = ?", (username,))
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()
        return True, "Usuário deletado com sucesso"
    except Exception as e:
        print(f"Erro ao deletar usuário: {e}")
        return False, "Erro ao deletar usuário"

def update_user_name(username, new_name):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET name = ? WHERE username = ?", (new_name, username))
        conn.commit()
        conn.close()
        return True, "Nome atualizado com sucesso"
    except Exception as e:
        print(f"Erro ao atualizar nome: {e}")
        return False, "Erro ao atualizar nome"

def get_or_create_thread_id(username, client):
    """Busca ou cria thread ID para o usuário"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT thread_id FROM user_threads WHERE username = ?", (username,))
        result = cursor.fetchone()
        if result:
            thread_id = result[0]
        else:
            thread = client.beta.threads.create()
            thread_id = thread.id
            cursor.execute("INSERT INTO user_threads (username, thread_id) VALUES (?, ?)",
                          (username, thread_id))
            conn.commit()
        conn.close()
        return thread_id
    except Exception as e:
        print(f"Erro ao obter thread ID: {e}")
        thread = client.beta.threads.create()
        return thread.id

def add_message_to_history(username, role, content):
    return save_conversation(username, role, content)

def log_user_action(username, action_type, action_data):
    return save_user_action(username, action_type, action_data)

def get_all_user_evaluations():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                u.username, 
                COALESCE(u.name, u.username) as name,
                u.email,
                COUNT(CASE WHEN ua.action_data = 'acerto' THEN 1 END) as acertos,
                COUNT(CASE WHEN ua.action_data = 'erro' THEN 1 END) as erros,
                COUNT(ua.action_data) as total_decisions,
                MAX(ua.timestamp) as last_activity
            FROM users u
            LEFT JOIN user_actions ua ON u.username = ua.username 
            WHERE ua.action_type = 'avaliacao_automatica' OR ua.action_type IS NULL
            GROUP BY u.username, u.name, u.email
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

def get_user_login_stats(username):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT username, name, email, created_at, 
                   (SELECT COUNT(*) FROM conversations WHERE username = ?) as total_messages,
                   (SELECT COUNT(*) FROM user_actions WHERE username = ?) as total_actions
            FROM users 
            WHERE username = ?
        ''', (username, username, username))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {
                'username': result[0],
                'name': result[1] or result[0],
                'email': result[2],
                'created_at': result[3],
                'total_messages': result[4],
                'total_actions': result[5],
                'exists': True
            }
        else:
            return {'exists': False}
    except Exception as e:
        print(f"Erro ao buscar stats de login: {e}")
        return {'exists': False}

def database_health_check():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        health = {
            'database_exists': True,
            'tables_exist': {},
            'total_users': 0,
            'total_conversations': 0,
            'total_actions': 0,
            'issues': []
        }
        required_tables = ['users', 'conversations', 'user_actions', 'user_threads']
        for table in required_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            exists = cursor.fetchone() is not None
            health['tables_exist'][table] = exists
            if not exists:
                health['issues'].append(f"Tabela '{table}' não encontrada")
        if health['tables_exist'].get('users'):
            cursor.execute("SELECT COUNT(*) FROM users")
            health['total_users'] = cursor.fetchone()[0]
        if health['tables_exist'].get('conversations'):
            cursor.execute("SELECT COUNT(*) FROM conversations")
            health['total_conversations'] = cursor.fetchone()[0]
        if health['tables_exist'].get('user_actions'):
            cursor.execute("SELECT COUNT(*) FROM user_actions")
            health['total_actions'] = cursor.fetchone()[0]
        conn.close()
        health['is_healthy'] = len(health['issues']) == 0
        return health
    except Exception as e:
        return {
            'database_exists': False,
            'error': str(e),
            'is_healthy': False,
            'issues': [f"Erro ao acessar banco: {e}"]
        }

if __name__ == "__main__":
    init_database()
else:
    init_database()
