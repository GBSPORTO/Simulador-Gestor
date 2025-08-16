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

    # CORRIGIDO: Tabela para Ações do usuário (compatível com o código principal)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        action_type TEXT NOT NULL,  -- 'avaliacao_automatica', etc.
        action_data TEXT,           -- 'acerto' ou 'erro' para avaliações
        details TEXT,               -- JSON com mais detalhes se necessário
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

# --- CORRIGIDO: Funções de Gerenciamento de Ações (compatível com o código principal) ---
def log_user_action(username, action_type, action_data, details=""):
    """
    Registra uma ação ou decisão do usuário no banco de dados.
    - action_type: 'avaliacao_automatica', etc.
    - action_data: 'acerto' ou 'erro' para avaliações
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_actions (username, action_type, action_data, details) VALUES (?, ?, ?, ?)",
                   (username, action_type, action_data, details))
    conn.commit()
    conn.close()

def get_all_user_actions():
    """Busca todas as ações de todos os usuários para o dashboard."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM user_actions", conn)
    conn.close()
    return df

# --- NOVA: Função necessária para o dashboard funcionar completamente ---
def get_all_user_evaluations():
    """
    Retorna estatísticas de avaliação de todos os usuários para o dashboard.
    Esta função é chamada pelo código principal.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT 
                u.username, 
                u.name, 
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
        conn.close()
        return []

# --- Funções auxiliares para analytics (opcionais) ---
def get_user_stats(username):
    """Obtém estatísticas específicas de um usuário."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(CASE WHEN action_data = 'acerto' THEN 1 END) as acertos,
            COUNT(CASE WHEN action_data = 'erro' THEN 1 END) as erros,
            COUNT(*) as total
        FROM user_actions 
        WHERE username = ? AND action_type = 'avaliacao_automatica'
    ''', (username,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'acertos': result[0],
            'erros': result[1],
            'total': result[2],
            'taxa_acerto': (result[0] / result[2] * 100) if result[2] > 0 else 0
        }
    return {'acertos': 0, 'erros': 0, 'total': 0, 'taxa_acerto': 0}

def clear_user_history(username):
    """Limpa o histórico de chat de um usuário (útil para testes)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE username = ?", (username,))
    cursor.execute("DELETE FROM user_actions WHERE username = ?", (username,))
    conn.commit()
    conn.close()
