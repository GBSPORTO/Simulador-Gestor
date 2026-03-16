def get_user_history(username):
    """Busca histórico de conversas do usuário"""
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
