import os
import logging
import ingestor
import pytz
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from database import (add_user, 
                      get_user_subscriptions, 
                      toggle_subscription, 
                      get_personalized_news, 
                      search_news, 
                      update_user_time, 
                      get_users_by_time)

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

# Define o menu
CATEGORIAS_DISPONIVEIS = ["Formula 1", "IndyCar", "NASCAR", "Rallying", "Le Mans/WEC", "Supercars Championship", "Off-Road"]

# Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # 1. Salva no Banco 
    add_user(chat_id, user.first_name)
    
    msg = (
        f"🏁 Olá, {user.first_name}! Bem-vindo ao RacingBot!\n\n"
        "Eu sou seu copiloto de notícias. Monitoro tudo sobre F1, Indy, NASCAR e WEC para você não perder nenhuma notícia.\n\n"
        "📋 Manual de uso (Comandos):\n\n"
        "⚙️ /config\n"
        "Acesse o Pit Stop: Escolha quais categorias você quer seguir.\n\n"
        "📰 /news\n"
        "Resumo Rápido: Receba agora as últimas notícias das suas categorias.\n\n"
        "⏰ /horario\n"
        "Piloto Automático: Agende um resumo diário. Ex: `/horario 08:00` (ou `/horario off` para cancelar).\n\n"
        "🔍 /search [termo]\n"
        "Pesquise notícias específicas. Ex: `/search Hamilton`.\n\n"
        "🚦 Primeiro passo: Clique em /config e monte seu grid de largada!"
    )
    await update.message.reply_text(msg)

# /config
async def config_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Busca o que o usuário já segue para marcar com ícone 
    inscricoes_atuais = get_user_subscriptions(chat_id)
    keyboard = []
    # Cria linhas de botões (2 por linha)
    row = []
    for cat in CATEGORIAS_DISPONIVEIS:
        # Se o usuário já segue, coloca um check
        texto = f"✅ {cat}" if cat in inscricoes_atuais else cat
        btn = InlineKeyboardButton(texto, callback_data=f"toggle_{cat}")
        row.append(btn)
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    # Se sobrou algum botão sozinho na última linha, adiciona
    if row:
        keyboard.append(row)
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Escolha suas categorias:", reply_markup=reply_markup)

# Função responsável por lidar com o clique nos botões.
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Avisa o Telegram que o clique foi recebido
    data = query.data
    chat_id = update.effective_chat.id
    
    if data.startswith("toggle_"):
        # Extrai o nome da categoria. Ex: "toggle_Formula 1" -> "Formula 1"
        categoria = data.replace("toggle_", "")
        toggle_subscription(chat_id, categoria)
        
        # 2. Recarrega o menu para atualizar os ✅
        inscricoes_atuais = get_user_subscriptions(chat_id)
        keyboard = []
        row = []
        for cat in CATEGORIAS_DISPONIVEIS:
            texto = f"✅ {cat}" if cat in inscricoes_atuais else cat
            btn = InlineKeyboardButton(texto, callback_data=f"toggle_{cat}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        # Edita a mensagem original com o novo teclado
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

# /news
async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    noticias = get_personalized_news(chat_id)
    
    if not noticias:
        await update.message.reply_text("Nenhuma notícia encontrada para as suas categorias.\nUse /config para marcar mais opções!")
        return

    await update.message.reply_text(f"Aqui estão as últimas do seu feed:", parse_mode='Markdown')

    for titulo, link, categoria, imagem_url in noticias:
        msg = f"🏎️ *{categoria}*\n**{titulo}**\n🔗 [Ler Matéria]({link})"
        
        # Se tiver imagem, envia como foto. Se não, apenas texto.
        if imagem_url:
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=imagem_url, caption=msg, parse_mode='Markdown')
            except:
                # Se a URL da imagem falhar, envia só o texto
                await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')

# /search
async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Digite algo para buscar. Exemplo:\n`/search Hamilton`", parse_mode='Markdown')
        return

    termo = " ".join(context.args)
    noticias = search_news(termo)
    
    if not noticias:
        await update.message.reply_text(f"Nada encontrado sobre '{termo}'.")
        return

    await update.message.reply_text(f"Resultados para '{termo}':", parse_mode='Markdown')
    
    for titulo, link, categoria, imagem_url in noticias:
        msg = f"📌 {titulo}\n🔗 [Ler Matéria]({link})"
        await update.message.reply_text(msg, parse_mode='Markdown')

async def enviar_noticias_para_usuario(context, chat_id):
    noticias = get_personalized_news(chat_id)
    if not noticias:
        await context.bot.send_message(chat_id, "📭 Sem notícias novas nas suas categorias.")
        return

    await context.bot.send_message(chat_id, "Seu Resumo Automotivo:", parse_mode='Markdown')
    for titulo, link, categoria, imagem_url in noticias:
        msg = f"🏎️ *{categoria}*\n**{titulo}**\n🔗 [Ler Matéria]({link})"
        if imagem_url:
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=imagem_url, caption=msg, parse_mode='Markdown')
            except:
                await context.bot.send_message(chat_id, msg, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id, msg, parse_mode='Markdown')

# Salva o horário de envio. Ex: /horario 08:00
async def cmd_horario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⏰ Use: `/horario 08:00` ou `/horario off` para cancelar.")
        return
    
    horario = context.args[0]
    chat_id = update.effective_chat.id
    
    if horario.lower() == 'off':
        update_user_time(chat_id, 'OFF')
        await update.message.reply_text("🔕 Envio automático cancelado.")
    else:
        # Validação simples de formato
        try:
            datetime.strptime(horario, '%H:%M')
            update_user_time(chat_id, horario)
            await update.message.reply_text(f"Agendado! Você receberá notícias diariamente às {horario}.")
        except ValueError:
            await update.message.reply_text("Formato inválido. Use HH:MM (Ex: 08:00 ou 18:30).")

# Automação do envio de notícias
async def job_etl_periodico(context: ContextTypes.DEFAULT_TYPE):
    print("Automação em curso: Rodando ETL...")
    ingestor.run_etl()

async def job_verificar_envios(context: ContextTypes.DEFAULT_TYPE):
    # "Que horas são?" -> "Quem quer notícias agora?" -> "Envia". 
    fuso = pytz.timezone('America/Sao_Paulo') 
    agora = datetime.now(fuso).strftime('%H:%M')
    
    # 1. Busca quem quer receber agora
    usuarios_para_enviar = get_users_by_time(agora)
    
    if usuarios_para_enviar:
        print(f"⏰ Hora do envio ({agora})! Enviando para {len(usuarios_para_enviar)} usuários.")
        for chat_id in usuarios_para_enviar:
            await enviar_noticias_para_usuario(context, chat_id)

if __name__ == '__main__':
    if not TOKEN:
        print("Erro: Token do Telegram não encontrado no arquivo .env")
        exit()
        
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Registrando os comandos
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('config', config_menu))
    application.add_handler(CommandHandler('news', cmd_news))
    application.add_handler(CommandHandler('search', cmd_search))
    application.add_handler(CommandHandler('horario', cmd_horario))
    
    # Registrando o clique nos botões
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Automação
    job_queue = application.job_queue
    
    # 1. ETL para rodar a cada 30 minutos (1800 segundos)
    job_queue.run_repeating(job_etl_periodico, interval=1800, first=10)
    
    # 2. Verificador de Envios para rodar a cada 60 segundos
    job_queue.run_repeating(job_verificar_envios, interval=60, first=5)
    
    print("Bot iniciado. Pressione Ctrl+C para parar.")
    application.run_polling()
