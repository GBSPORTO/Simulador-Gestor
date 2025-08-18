import sqlite3
import hashlib
import pandas as pd
from datetime import datetime
import os

# Nome do arquivo do banco de dados
DB_NAME = "leadership_simulator.db"

# ... (restante do código igual) ...

def authenticate_user(username, password):
    """
    Autentica usuário (DESABILITADO TEMPORARIAMENTE)
    Retorna: sempre True e dados genéricos
    """
    return True, {
        'username': username,
        'name': username,
        'email': '',
        'is_admin': False
    }

def authenticate_user_detailed(username, password):
    """
    Autenticação detalhada (DESABILITADA TEMPORARIAMENTE)
    """
    return True, {
        'username': username,
        'name': username,
        'email': '',
        'is_admin': False,
        'created_at': '',
        'login_success': True
    }

def validate_user_session(username):
    """Valida se o usuário existe (DESABILITADA TEMPORARIAMENTE)"""
    return True

def log_user_login(username, login_method='manual'):
    """Registra login (DESABILITADO TEMPORARIAMENTE)"""
    return True

def get_formatted_credentials_for_auth():
    """DESABILITADO TEMPORARIAMENTE"""
    return {'usernames': {}}

# ... (restante do código igual) ...
