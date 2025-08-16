"""
Database module for RPG Gestor Simulator
Handles all database operations including user management, message history, and user actions.
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

# Configurações do banco de dados
DB_FILE = 'simulador_gestor.db'

def get_db_connection():
    """
    Cria e retorna uma conexão com o banco de dados
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row  # Permite acesso por nome das colunas
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

def init_db():
    """
    Inicializa o banco de dados e cria todas as tabelas necessárias
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Tabela de usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME
            )
        ''')
        
        # Tabela de mensagens/histórico de conversas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de ações/avaliações dos usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de threads do OpenAI por usuário
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_threads (
                username TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de sessões de usuários (opcional, para controle de sessão)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                session_start DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_end DATETIME,
                total_decisions INTEGER DEFAULT 0,
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            )
        ''')
        
        # Cria índices para melhor performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_messages_username ON user_messages(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_actions_username ON user_actions(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_actions_type ON user_actions(action_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_messages_timestamp ON user_messages(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_actions_timestamp ON user_actions(timestamp)')
        
        conn.commit()
        conn.close()
        
        print(f"✅ Banco de dados inicializado com sucesso: {DB_FILE}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao inicializar banco de dados: {e}")
        return False

def get_user_credentials():
    """
    Obtém credenciais de todos os usuários para o sistema de autenticação
    Retorna no formato esperado pelo streamlit-authenticator
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'usernames': {}}
            
        cursor = conn.cursor()
        cursor.execute('SELECT username, name, email, hashed_password FROM users')
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {'usernames': {}}
        
        credentials = {'usernames': {}}
        
        for row in results:
            username = row['username']
            credentials['usernames'][username] = {
                'name': row['name'],
                'email': row['email'],
                'password': row['hashed_password']
            }
        
        return credentials
        
    except Exception as e:
        print(f"Erro ao buscar credenciais: {e}")
        return {'usernames': {}}

def add_user(username, name, email, hashed_password):
    """
    Adiciona novo usuário ao banco de dados
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO users (username, name, email, hashed_password) 
            VALUES (?, ?, ?, ?)
        ''', (username, name, email, hashed_password))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Usuário {username} adicionado com sucesso")
        return True
        
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            print(f"❌ Usuário ou email já existe: {username}")
        return False
    except Exception as e:
        print(f"❌ Erro ao adicionar usuário {username}: {e}")
        return False

def update_last_login(username):
    """
    Atualiza o timestamp do último login do usuário
    """
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET last_login = CURRENT_TIMESTAMP 
            WHERE username = ?
        ''', (username,))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Erro ao atualizar último login: {e}")

def get_user_history(username):
    """
    Busca o histórico completo de mensagens de um usuário
    """
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, content, timestamp 
            FROM user_messages 
            WHERE username = ? 
            ORDER BY timestamp ASC
        ''', (username,))
        
        results = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in results:
            messages.append({
                'role': row['role'],
                'content': row['content'],
                'timestamp': row['timestamp']
            })
        
        return messages
        
    except Exception as e:
        print(f"Erro ao buscar histórico do usuário {username}: {e}")
        return []

def add_message_to_history(username, role, content):
    """
    Adiciona uma mensagem ao histórico do usuário
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_messages (username, role, content) 
            VALUES (?, ?, ?)
        ''', (username, role, content))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Erro ao adicionar mensagem para {username}: {e}")
        return False

def clear_user_history(username):
    """
    Limpa o histórico de mensagens de um usuário
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_messages WHERE username = ?', (username,))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Histórico do usuário {username} limpo")
        return True
        
    except Exception as e:
        print(f"Erro ao limpar histórico do usuário {username}: {e}")
        return False

def log_user_action(username, action_type, action_data, metadata=None):
    """
    Registra uma ação do usuário (avaliações, decisões, etc.)
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_actions (username, action_type, action_data, metadata) 
            VALUES (?, ?, ?, ?)
        ''', (username, action_type, action_data, metadata))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Erro ao registrar ação do usuário {username}: {e}")
        return False

def get_or_create_thread_id(username, client):
    """
    Obtém thread_id existente ou cria nova thread para o usuário
    """
    try:
        conn = get_db_connection()
        if not conn:
            # Fallback: cria thread temporária
            thread = client.beta.threads.create()
            return thread.id
            
        cursor = conn.cursor()
        cursor.execute('SELECT thread_id FROM user_threads WHERE username = ?', (username,))
        result = cursor.fetchone()
        
        if result:
            thread_id = result['thread_id']
            # Atualiza último uso
            cursor.execute('''
                UPDATE user_threads 
                SET last_used = CURRENT_TIMESTAMP 
                WHERE username = ?
            ''', (username,))
            conn.commit()
        else:
            # Cria nova thread
            thread = client.beta.threads.create()
            thread_id = thread.id
            
            cursor.execute('''
                INSERT INTO user_threads (username, thread_id) 
                VALUES (?, ?)
            ''', (username, thread_id))
            conn.commit()
        
        conn.close()
        return thread_id
        
    except Exception as e:
        print(f"Erro ao obter/criar thread para {username}: {e}")
        # Fallback: cria thread temporária
        try:
            thread = client.beta.threads.create()
            return thread.id
        except:
            return None

def get_all_user_actions():
    """
    Busca todas as ações dos usuários para análise no dashboard
    """
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()
            
        query = '''
            SELECT username, action_data, timestamp, action_type, metadata
            FROM user_actions 
            WHERE action_type = 'avaliacao_automatica'
            ORDER BY timestamp DESC
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
        
    except Exception as e:
        print(f"Erro ao buscar ações dos usuários: {e}")
        return pd.DataFrame(columns=['username', 'action_data', 'timestamp', 'action_type', 'metadata'])

def get_all_user_evaluations():
    """
    Obtém estatísticas de avaliação de todos os usuários para o dashboard
    """
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                u.username, 
                u.name, 
                u.email,
                COUNT(CASE WHEN ua.action_data = 'acerto' THEN 1 END) as acertos,
                COUNT(CASE WHEN ua.action_data = 'erro' THEN 1 END) as erros,
                COUNT(ua.action_data) as total_decisions,
                MAX(ua.timestamp) as last_activity,
                u.last_login
            FROM users u
            LEFT JOIN user_actions ua ON u.username = ua.username 
            WHERE ua.action_type = 'avaliacao_automatica' OR ua.action_type IS NULL
            GROUP BY u.username, u.name, u.email, u.last_login
            ORDER BY total_decisions DESC, u.username ASC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        user_stats = []
        for row in results:
            user_stats.append({
                'username': row['username'],
                'name': row['name'] or 'N/A',
                'email': row['email'],
                'acertos': row['acertos'] or 0,
                'erros': row['erros'] or 0,
                'total_decisions': row['total_decisions'] or 0,
                'last_activity': row['last_activity'] or 'Nunca',
                'last_login': row['last_login'] or 'Nunca'
            })
        
        return user_stats
        
    except Exception as e:
        print(f"Erro ao obter avaliações dos usuários: {e}")
        return []

def get_user_performance_summary(username):
    """
    Obtém resumo de performance de um usuário específico
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(CASE WHEN action_data = 'acerto' THEN 1 END) as acertos,
                COUNT(CASE WHEN action_data = 'erro' THEN 1 END) as erros,
                COUNT(action_data) as total_decisions,
                MIN(timestamp) as first_activity,
                MAX(timestamp) as last_activity
            FROM user_actions 
            WHERE username = ? AND action_type = 'avaliacao_automatica'
        ''', (username,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            acertos = result['acertos'] or 0
            erros = result['erros'] or 0
            total = result['total_decisions'] or 0
            accuracy = (acertos / total * 100) if total > 0 else 0
            
            return {
                'username': username,
                'acertos': acertos,
                'erros': erros,
                'total_decisions': total,
                'accuracy': accuracy,
                'first_activity': result['first_activity'] or 'Nunca',
                'last_activity': result['last_activity'] or 'Nunca'
            }
        
        return None
        
    except Exception as e:
        print(f"Erro ao obter resumo de performance para {username}: {e}")
        return None

def cleanup_old_data(days=30):
    """
    Remove dados antigos para manter o banco otimizado
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Remove mensagens antigas
        cursor.execute('''
            DELETE FROM user_messages 
            WHERE timestamp < datetime('now', '-{} days')
        '''.format(days))
        
        # Remove ações antigas (mantém avaliações)
        cursor.execute('''
            DELETE FROM user_actions 
            WHERE timestamp < datetime('now', '-{} days') 
            AND action_type != 'avaliacao_automatica'
        '''.format(days))
        
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        
        print(f"✅ Limpeza concluída: {rows_affected} registros removidos")
        return True
        
    except Exception as e:
        print(f"Erro na limpeza de dados: {e}")
        return False

def get_database_stats():
    """
    Obtém estatísticas gerais do banco de dados
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        stats = {}
        
        # Contagem de usuários
        cursor.execute('SELECT COUNT(*) FROM users')
        stats['total_users'] = cursor.fetchone()[0]
        
        # Contagem de mensagens
        cursor.execute('SELECT COUNT(*) FROM user_messages')
        stats['total_messages'] = cursor.fetchone()[0]
        
        # Contagem de ações
        cursor.execute('SELECT COUNT(*) FROM user_actions')
        stats['total_actions'] = cursor.fetchone()[0]
        
        # Usuários ativos (com pelo menos uma ação)
        cursor.execute('''
            SELECT COUNT(DISTINCT username) 
            FROM user_actions 
            WHERE action_type = 'avaliacao_automatica'
        ''')
        stats['active_users'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
        
    except Exception as e:
        print(f"Erro ao obter estatísticas do banco: {e}")
        return None

# Função de teste para verificar se o banco está funcionando
def test_database():
    """
    Testa as funções básicas do banco de dados
    """
    print("🧪 Testando banco de dados...")
    
    # Testa inicialização
    if init_db():
        print("✅ Inicialização: OK")
    else:
        print("❌ Inicialização: ERRO")
        return False
    
    # Testa estatísticas
    stats = get_database_stats()
    if stats:
        print(f"✅ Estatísticas: {stats}")
    else:
        print("❌ Estatísticas: ERRO")
    
    # Testa credenciais
    creds = get_user_credentials()
    print(f"✅ Credenciais: {len(creds.get('usernames', {}))} usuários encontrados")
    
    print("🎯 Teste do banco de dados concluído!")
    return True

# Executa teste se rodado diretamente
if __name__ == "__main__":
    test_database()
