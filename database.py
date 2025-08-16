def get_user_history(username):
    """
    Busca o histórico de mensagens de um usuário específico
    Retorna uma lista de dicionários com role e content
    """
    try:
        cursor.execute('''
            SELECT role, content, timestamp 
            FROM user_messages 
            WHERE username = ? 
            ORDER BY timestamp ASC
        ''', (username,))
        
        results = cursor.fetchall()
        messages = []
        
        for row in results:
            messages.append({
                'role': row[0],
                'content': row[1],
                'timestamp': row[2]
            })
        
        return messages
        
    except Exception as e:
        print(f"Erro ao buscar histórico do usuário {username}: {e}")
        return []

def get_all_user_actions():
    """
    Busca todas as ações de avaliação de todos os usuários
    Retorna DataFrame com username, action_data, timestamp
    """
    try:
        import pandas as pd
        
        cursor.execute('''
            SELECT username, action_data, timestamp, action_type
            FROM user_actions 
            WHERE action_type = 'avaliacao_automatica'
            ORDER BY timestamp DESC
        ''')
        
        results = cursor.fetchall()
        
        if results:
            df = pd.DataFrame(results, columns=['username', 'action_data', 'timestamp', 'action_type'])
            return df
        else:
            return pd.DataFrame(columns=['username', 'action_data', 'timestamp', 'action_type'])
        
    except Exception as e:
        print(f"Erro ao buscar ações dos usuários: {e}")
        import pandas as pd
        return pd.DataFrame()
