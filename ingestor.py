import feedparser
import time
import sqlite3
from datetime import datetime
from database import get_connection

# URL do Feed RSS do Racer.com
RSS_URL = "https://racer.com/feed/"

def formatar_data(struct_time):
    if not struct_time:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return datetime.fromtimestamp(time.mktime(struct_time)).strftime('%Y-%m-%d %H:%M:%S')

# Função responsável pelo pipeline ETL
def run_etl():
    print("Iniciando ingestão de dados...")
    
    # 1. Extract 
    print(f"Conectando a {RSS_URL}...")
    feed = feedparser.parse(RSS_URL)
    
    if feed.bozo: # 'bozo' indica erro no XML
        print("Ops: O XML baixado contém erros de formatação, mas tentaremos ler.")

    conn = get_connection()
    cursor = conn.cursor()
    novas_noticias = 0

    # As mais antigas primeiro
    for entry in reversed(feed.entries):
        
        # 2. Transform
        titulo = entry.title
        link = entry.link
        data_pub = formatar_data(entry.published_parsed)
        
        # Se houver tags, pega a primeira (ex: 'Formula 1'). Senão, 'Geral'.
        categoria = entry.tags[0].term if hasattr(entry, 'tags') else 'Geral'
        
        # Imagem
        imagem_url = None
        if 'media_content' in entry and entry.media_content:
            imagem_url = entry.media_content[0]['url']
        elif 'media_thumbnail' in entry and entry.media_thumbnail:
            imagem_url = entry.media_thumbnail[0]['url']

        # 3. Load 
        try:
            cursor.execute('''
                INSERT INTO noticias (titulo, link, categoria, data_publicacao, imagem_url)
                VALUES (?, ?, ?, ?, ?)
            ''', (titulo, link, categoria, data_pub, imagem_url))
            
            conn.commit() # Salva efetivamente
            novas_noticias += 1
            print(f"✅ Nova [{categoria}]: {titulo[:40]}...")
            
        except sqlite3.IntegrityError:
            # Se o link já existe, pula.
            pass
            
    conn.close()
    print(f"\nETL Finalizado. {novas_noticias} novas notícias importadas.")

if __name__ == "__main__":
    run_etl()
