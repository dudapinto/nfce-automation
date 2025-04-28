import os
import sys
import telegram
from telegram.ext import Application, MessageHandler, filters, CommandHandler
from dotenv import load_dotenv
from nfce_automation import processar_imagem, limpar_valor, driver
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback
import logging
import re

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Obtém o token do Telegram a partir da variável de ambiente
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Verifica se o token foi carregado corretamente
if not TOKEN:
    raise ValueError("Token do Telegram não encontrado. Certifique-se de que a variável TELEGRAM_TOKEN está definida no arquivo .env")

# Configuração de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Configura Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("NFCes").worksheet("DADOS")

# Configura Telegram
bot = telegram.Bot(token=TOKEN)

# URL para "Aguardando Documento"
IDLE_PAGE = 'data:text/html,<body style="background:black;color:white;text-align:center;font-family:Arial;"><h1>Aguardando Documento</h1></body>'

def calcular_insights(empresa, total, itens, is_sat):
    rows = sheet.get_all_values()[1:]
    gastos_empresa = [
        float(limpar_valor(row[11])) if row[11] else 0.0
        for row in rows
        if row[0] == empresa
    ]
    media = sum(gastos_empresa) / len(gastos_empresa) if gastos_empresa else total

    data_atual = itens[0].get("data") if itens and len(itens) > 0 else None
    ultimas_compras = [
        r for r in rows
        if r[0] == empresa and (data_atual is None or r[12] != data_atual)
    ][-2:]
    comparacao = []
    for item in itens:
        for compra in ultimas_compras:
            if item["descricao"] == compra[7]:
                comparacao.append({
                    "descricao": item["descricao"],
                    "hoje": float(item["vlTotal"]),
                    "anterior": float(limpar_valor(compra[11])),
                    "data_anterior": compra[12]
                })

    outros_precos = []
    for item in itens:
        codigo = item.get("codigo", "")
        if codigo:
            precos = [
                float(limpar_valor(r[11]))
                for r in rows
                if r[4] == codigo and r[0] != empresa
            ]
            if precos:
                media_outros = sum(precos) / len(precos)
                outros_precos.append({
                    "descricao": item["descricao"],
                    "pago": float(item["vlTotal"]),
                    "media_outros": media_outros
                })

    categorias = {}
    for item in itens:
        cat = item.get("categoria", "Outros")
        categorias[cat] = categorias.get(cat, 0) + float(item["vlTotal"])

    return {
        "media": media,
        "comparacao": comparacao,
        "outros_precos": outros_precos,
        "categorias": categorias
    }

async def start(update, context):
    await update.message.reply_text("Olá! Eu sou o bot NFCe. Envie uma foto de um recibo com QR code ou digite a chave de 44 dígitos para começar!")

async def handle_text(update, context):
    texto = update.message.text.strip()
    logging.debug(f"Texto recebido: {texto}")
    
    # Remover todos os espaços do texto
    texto_sem_espacos = texto.replace(" ", "")
    
    # Verifica se o texto sem espaços tem exatamente 44 dígitos numéricos OU
    # se tem 45 dígitos sendo o primeiro um 's' ou 'S' e o restante 44 dígitos numéricos
    if not re.match(r'^(\d{44}|[sS]\d{44})$', texto_sem_espacos):
        await update.message.reply_text(
            "⚠️ Por favor, envie uma chave com exatamente 44 dígitos numéricos! "
            "Você pode digitar um 's' na frente se perceber que é um SAT e também "
            "com ou sem espaços a cada 4 dígitos (ex.: 3525 0447 ... ou 35250447...)."
            "Ou envie uma foto do recibo com QR code!"
        )
        return

    await update.message.reply_text("Processando sua chave... 🔍")
    try:
        dados = processar_imagem(chave_manual=texto_sem_espacos, debug_level=1, from_bot=True)
        if not dados:
            logging.debug(f"Falha ao processar chave manual: {texto_sem_espacos}")
            await update.message.reply_text("Não consegui processar a chave. Verifique e tente novamente! 😕")
            return

        empresa = dados.get("emitente", dados.get("empresa", "Desconhecida"))
        total = float(dados.get("vlTotal", sum(float(i["vlTotal"]) for i in dados["itens"])))
        insights = calcular_insights(empresa, total, dados["itens"], dados.get("is_sat", False))

        # Verificar se é uma duplicata com base na flag retornada
        is_duplicate = dados.get("is_duplicate", False)
        numero_recibo = dados.get("numeroRecibo", "N/A")

        resposta = "✅ Compra processada!\n" if not is_duplicate else f"⚠️ Esta compra (número {numero_recibo}) já foi processada anteriormente!\n"
        resposta += f"Empresa: {empresa}\n"
        resposta += f"Data: {dados.get('data', 'N/A')}\n"
        resposta += f"Total: R${total:.2f}\n"
        resposta += f"Itens: {len(dados['itens'])}\n"
        resposta += f"\n📊 Insights:\n"
        resposta += f"- Valor médio em {empresa}: R${insights['media']:.2f}\n"
        if insights["comparacao"]:
            resposta += "- Comparação com compras anteriores:\n"
            for comp in insights["comparacao"]:
                resposta += f"  • {comp['descricao']}: R${comp['hoje']:.2f} (anterior: R${comp['anterior']:.2f} em {comp['data_anterior']})\n"
        else:
            resposta += "- Sem compras anteriores para comparar.\n"
        if insights["outros_precos"]:
            resposta += "- Preços em outros estabelecimentos:\n"
            for outro in insights["outros_precos"]:
                resposta += f"  • {outro['descricao']}: R${outro['pago']:.2f} (média em outros: R${outro['media_outros']:.2f})\n"
        else:
            resposta += "- Sem dados de outros estabelecimentos.\n"
        if insights["categorias"]:
            resposta += "- Gastos por categoria:\n"
            for cat, valor in insights["categorias"].items():
                resposta += f"  • {cat}: R${valor:.2f}\n"

        await update.message.reply_text(resposta)

    except Exception as e:
        error_msg = f"Erro ao processar: {str(e)}"
        logging.error(error_msg)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(f"Erro ao processar: {str(e)} 😓")
    finally:
        try:
            if driver:
                logging.debug(f"Driver state before redirect: {driver}")
                driver.get(IDLE_PAGE)
                logging.debug("Browser redirecionado para 'Aguardando Documento'")
        except Exception as e:
            logging.error(f"Erro ao redirecionar browser: {str(e)}")

async def handle_photo(update, context):
    user = update.message.from_user
    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"recibos/{user.id}_{int(time.time())}.jpg"
    os.makedirs("recibos", exist_ok=True)
    await photo_file.download_to_drive(photo_path)

    await update.message.reply_text("Processando sua imagem... 📸")

    try:
        test_data = sheet.col_values(3)
        logging.debug(f"Google Sheets column 3 data: {test_data}")
    except Exception as e:
        logging.error(f"Google Sheets error: {e}")
        await update.message.reply_text("Erro ao acessar Google Sheets. Contate o administrador.")
        return

    try:
        logging.debug(f"Processing image: {photo_path}")
        dados = processar_imagem(caminho_imagem=photo_path, debug_level=1, from_bot=True)
        if not dados:
            logging.debug(f"Failed to process {photo_path}")
            await update.message.reply_text("Não consegui extrair o QR code. Tente outra imagem ou envie a chave de 44 dígitos! 😕")
            return

        empresa = dados.get("emitente", dados.get("empresa", "Desconhecida"))
        total = float(dados.get("vlTotal", sum(float(i["vlTotal"]) for i in dados["itens"])))
        insights = calcular_insights(empresa, total, dados["itens"], dados.get("is_sat", False))

        # Verificar se é uma duplicata com base na flag retornada
        is_duplicate = dados.get("is_duplicate", False)
        numero_recibo = dados.get("numeroRecibo", "N/A")

        resposta = "✅ Compra processada!\n" if not is_duplicate else f"⚠️ Esta compra (número {numero_recibo}) já foi processada anteriormente!\n"
        resposta += f"Empresa: {empresa}\n"
        resposta += f"Data: {dados.get('data', 'N/A')}\n"
        resposta += f"Total: R${total:.2f}\n"
        resposta += f"Itens: {len(dados['itens'])}\n"
        resposta += f"\n📊 Insights:\n"
        resposta += f"- Valor médio em {empresa}: R${insights['media']:.2f}\n"
        if insights["comparacao"]:
            resposta += "- Comparação com compras anteriores:\n"
            for comp in insights["comparacao"]:
                resposta += f"  • {comp['descricao']}: R${comp['hoje']:.2f} (anterior: R${comp['anterior']:.2f} em {comp['data_anterior']})\n"
        else:
            resposta += "- Sem compras anteriores para comparar.\n"
        if insights["outros_precos"]:
            resposta += "- Preços em outros estabelecimentos:\n"
            for outro in insights["outros_precos"]:
                resposta += f"  • {outro['descricao']}: R${outro['pago']:.2f} (média em outros: R${outro['media_outros']:.2f})\n"
        else:
            resposta += "- Sem dados de outros estabelecimentos.\n"
        if insights["categorias"]:
            resposta += "- Gastos por categoria:\n"
            for cat, valor in insights["categorias"].items():
                resposta += f"  • {cat}: R${valor:.2f}\n"

        await update.message.reply_text(resposta)

    except Exception as e:
        error_msg = f"Erro ao processar: {str(e)}"
        logging.error(error_msg)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(f"Erro ao processar: {str(e)} 😓")
    finally:
        try:
            if driver:
                logging.debug(f"Driver state before redirect: {driver}")
                driver.get(IDLE_PAGE)
                logging.debug("Browser redirecionado para 'Aguardando Documento'")
        except Exception as e:
            logging.error(f"Erro ao redirecionar browser: {str(e)}")

def main():
    debug_level = 0
    if len(sys.argv) > 1 and sys.argv[1].startswith("debug="):
        try:
            debug_level = int(sys.argv[1].split("=")[1])
            logging.info(f"Debug mode set to: {debug_level}")
        except ValueError:
            print("Argumento debug inválido. Usando debug=0.")
    
    setup_logging(debug_level)

    try:
        if driver:
            logging.debug(f"Driver state at startup: {driver}")
            driver.get(IDLE_PAGE)
            logging.info("Browser inicializado em 'Aguardando Documento'")
    except Exception as e:
        logging.error(f"Erro ao inicializar browser: {str(e)}")

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logging.info("Bot está rodando...")
    application.run_polling()

if __name__ == "__main__":
    main()