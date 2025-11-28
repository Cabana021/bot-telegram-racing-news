import sqlite3
from pathlib import Path

# Diretórios
ROOT_DIR = Path(__file__).parent
DB_DIR = ROOT_DIR / 'data'
DB_PATH = DB_DIR / 'racer_news.db'  

# Garante que a pasta existe. Se não existir, cria.
DB_DIR.mkdir(exist_ok=True)

# Função responsável pela conexão com o DB
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

# Função responsável por planejar o DB
def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Notícias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS noticias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,
            categoria TEXT,
            data_publicacao TEXT,
            imagem_url TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 1. Usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            chat_id INTEGER PRIMARY KEY,
            nome TEXT,
            horario_envio TEXT,  -- Ex: "08:00" ou NULL
            ativo BOOLEAN DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 1. Inscrições (N:N)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inscricoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            categoria TEXT NOT NULL,
            FOREIGN KEY (chat_id) REFERENCES usuarios (chat_id) ON DELETE CASCADE,
            UNIQUE(chat_id, categoria)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Tabelas criadas/verificadas com sucesso!")

# Função responsável por criar os índexes
def create_indexes():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Índice para buscar notícias por categoria rapidamente
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_noticias_cat ON noticias(categoria)')
    
    # Índice para buscar inscrições de um usuário rapidamente
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_inscricoes_user ON inscricoes(chat_id)')
    
    conn.commit()
    conn.close()
    print("✅ Índices de performance criados!")

# Funções para lidar com o usuário do bot
def add_user(chat_id, nome):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Se o ID já existe, não faz nada 
        cursor.execute('''
            INSERT OR IGNORE INTO usuarios (chat_id, nome) VALUES (?, ?)
        ''', (chat_id, nome))
        conn.commit()
    finally:
        conn.close()

def get_user_subscriptions(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT categoria FROM inscricoes WHERE chat_id = ?', (chat_id,))
    # O resultado vem como [(F1,), (Indy,)], transformamos em lista simples ['F1', 'Indy']
    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result

def toggle_subscription(chat_id, categoria):
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Verifica se já existe
    cursor.execute('SELECT id FROM inscricoes WHERE chat_id = ? AND categoria = ?', (chat_id, categoria))
    exists = cursor.fetchone()
    
    if exists:
        # Remove
        cursor.execute('DELETE FROM inscricoes WHERE chat_id = ? AND categoria = ?', (chat_id, categoria))
        action = False # "Desmarcado"
    else:
        # Adiciona
        cursor.execute('INSERT INTO inscricoes (chat_id, categoria) VALUES (?, ?)', (chat_id, categoria))
        action = True # "Marcado"
        
    conn.commit()
    conn.close()
    return action

# Funções para pesquisar as notícias
def get_personalized_news(chat_id, limit=5):
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT titulo, link, categoria, imagem_url 
        FROM noticias 
        WHERE categoria IN (SELECT categoria FROM inscricoes WHERE chat_id = ?)
        ORDER BY data_publicacao DESC 
        LIMIT ?
    '''
    cursor.execute(query, (chat_id, limit))
    noticias = cursor.fetchall()
    conn.close()
    return noticias

def search_news(termo):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT titulo, link, categoria, imagem_url 
        FROM noticias 
        WHERE titulo LIKE ? 
        ORDER BY data_publicacao DESC 
        LIMIT 5
    '''
    cursor.execute(query, (f'%{termo}%',)) # Ex: '%Verstappen%'
    noticias = cursor.fetchall()
    conn.close()
    return noticias

# Define o horário de envio automático.
def update_user_time(chat_id, horario):
    conn = get_connection()
    cursor = conn.cursor()
    
    if horario == 'OFF':
        cursor.execute('UPDATE usuarios SET horario_envio = NULL WHERE chat_id = ?', (chat_id,))
    else:
        cursor.execute('UPDATE usuarios SET horario_envio = ? WHERE chat_id = ?', (horario, chat_id))
        
    conn.commit()
    conn.close()

# Retorna a lista de chat_ids que configuraram para receber notícias 
def get_users_by_time(horario_atual):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM usuarios WHERE horario_envio = ?', (horario_atual,))
    # Retorna lista simples de IDs: [12345, 67890]
    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result

if __name__ == "__main__":
    print("Iniciando configuração do Banco de Dados...")
    create_tables()
    create_indexes()
    print(f"Banco de dados disponível em: {DB_PATH}")
