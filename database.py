# database.py
import sqlite3
import pandas as pd

DB_NAME = "chat_history.db"

def init_db():
    """Inicializa o banco de dados e cria todas as tabelas necessárias."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabela de usuários
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        hashed_password TEXT NOT NULL
    )
    """)
    
    # Tabela de histórico de chat
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (username) REFERENCES users (username)
    )
    """)
    
    # Tabela de threads da OpenAI
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_threads (
        username TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        FOREIGN KEY (username) REFERENCES users (username)
    )
    """)

    # Tabela para Ações do usuário (para o dashboard)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        decision_type TEXT,
        outcome TEXT, -- 'acerto' ou 'erro'
        details TEXT, -- Pode guardar um JSON com mais detalhes
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (username) REFERENCES users (username)
    )
    """)
    
    conn.commit()
    conn.close()

# --- Funções de Gerenciamento de Usuários ---
def add_user(username, name, email, hashed_password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, name, email, hashed_password) VALUES (?, ?, ?, ?)",
                       (username, name, email, hashed_password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user_credentials():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, name, email, hashed_password FROM users")
    users = cursor.fetchall()
    conn.close()
    
    credentials = {"usernames": {}}
    for user in users:
        username, name, email, hashed_password = user
        credentials["usernames"][username] = {
            "name": name, "email": email, "password": hashed_password
        }
    return credentials

# --- Funções de Gerenciamento de Chat ---
def add_message_to_history(username, role, content):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", 
                   (username, role, content))
    conn.commit()
    conn.close()

def get_user_history(username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_history WHERE username = ? ORDER BY timestamp ASC", 
                   (username,))
    history = cursor.fetchall()
    conn.close()
    return [{"role": role, "content": content} for role, content in history]

def get_or_create_thread_id(username, openai_client):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT thread_id FROM user_threads WHERE username = ?", (username,))
    result = cursor.fetchone()
    if result:
        conn.close()
        return result[0]
    else:
        thread = openai_client.beta.threads.create()
        thread_id = thread.id
        cursor.execute("INSERT INTO user_threads (username, thread_id) VALUES (?, ?)", 
                       (username, thread_id))
        conn.commit()
        conn.close()
        return thread_id

# --- Funções de Gerenciamento de Ações (para o dashboard) ---
def log_user_action(username, decision_type, outcome, details=""):
    """Registra uma ação ou decisão do usuário no banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_actions (username, decision_type, outcome, details) VALUES (?, ?, ?, ?)",
                   (username, decision_type, outcome, details))
    conn.commit()
    conn.close()

def get_all_user_actions():
    """Busca todas as ações de todos os usuários para o dashboard."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM user_actions", conn)
    conn.close()
    return df
