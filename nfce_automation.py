from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pyzbar.pyzbar import decode, ZBarSymbol
from PIL import Image
import os
import time
import re
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import logging

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configura o Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
spreadsheet = client.open("NFCes")  # Define a planilha
sheet = spreadsheet.worksheet("DADOS")  # Define a aba DADOS

# Função para log
def log(message, debug_level=0):
    if debug_level == 1:
        print(message)
    elif debug_level == 0:
        keywords = ["processando imagem", "empresa:", "data:", "total:", "código:", "✅", "imagem renomeada"]
        if any(kw in message.lower() for kw in keywords):
            print(message)

# URL para "Aguardando Documento"
IDLE_PAGE = 'data:text/html,<body style="background:black;color:white;text-align:center;font-family:Arial;"><h1>Aguardando Documento</h1></body>'

def verificar_qualidade_imagem(caminho_imagem, debug_level=0):
    try:
        img = Image.open(caminho_imagem)
        largura, altura = img.size
        log(f"Dimensões da imagem {os.path.basename(caminho_imagem)}: {largura}x{altura}", debug_level)
        if altura < 100 or largura < 100:
            return False, "Imagem muito pequena.", None
        return True, "", img
    except Exception as e:
        return False, f"Erro ao verificar imagem: {e}", None

def preprocessar_imagem(caminho_imagem, debug_level=0):
    log(f"Processando imagem: {os.path.basename(caminho_imagem)}", debug_level)
    qualidade_ok, mensagem, img = verificar_qualidade_imagem(caminho_imagem, debug_level)
    if not qualidade_ok:
        log(f"Imagem {os.path.basename(caminho_imagem)} ignorada: {mensagem}", debug_level)
        return None, mensagem

    try:
        qrcodes = decode(img, symbols=[ZBarSymbol.QRCODE])
        if qrcodes:
            for qrcode in qrcodes:
                if qrcode.data:
                    data = qrcode.data.decode("utf-8") if isinstance(qrcode.data, bytes) else str(qrcode.data)
                    log(f"Imagem {os.path.basename(caminho_imagem)}: QR code detectado: {data}", debug_level)
                    return [data], "QR code detectado"
        log(f"Imagem {os.path.basename(caminho_imagem)}: QR code não detectado.", debug_level)
        return None, "QR code não detectado"
    except Exception as e:
        log(f"Erro ao processar QR code: {e}", debug_level)
        return None, f"Erro ao processar QR code: {e}"

def limpar_valor(texto, debug_level=0):
    if not texto:
        return "0.0"
    texto = texto.strip()
    texto_limpo = texto.replace('\xa0', '').replace('\n', '').replace('\t', '').replace('R$', '').replace('$', '').replace(',', '.').strip()
    texto_limpo = re.sub(r'[^\d.]', '', texto_limpo)
    log(f"Valor bruto recebido: '{texto}'", debug_level)
    log(f"Valor limpo: '{texto_limpo}'", debug_level)
    try:
        return str(float(texto_limpo))
    except ValueError:
        log(f"Erro: Não foi possível converter '{texto}' -> '{texto_limpo}' para float", debug_level)
        return "0.0"

def remover_acentos(texto):
    mapa_acentos = {
        'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a',
        'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'Ä': 'A', 'Å': 'A',
        'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
        'È': 'E', 'É': 'E', 'Ê': 'E', 'Ë': 'E',
        'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
        'Ì': 'I', 'Í': 'I', 'Î': 'I', 'Ï': 'I',
        'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
        'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ö': 'O',
        'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
        'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ü': 'U',
        'ç': 'c', 'Ç': 'C',
        'ñ': 'n', 'Ñ': 'N'
    }
    return ''.join(mapa_acentos.get(char, char) for char in texto)

def extrair_empresa(html):
    inicio = remover_acentos('<div id="u20" class="txtTopo">')
    fim = remover_acentos('</div>')
    return extrair_texto_entre(html, inicio, fim)

def extrair_cnpj(html):
    inicio = remover_acentos('CNPJ:')
    start = html.index(inicio) if inicio in html else -1
    if start == -1:
        return ""
    fim = remover_acentos('</div>')
    end = html.index(fim, start) if fim in html[start:] else -1
    if end == -1:
        return ""
    return extrair_texto_entre(html, inicio, fim)

def extrair_emissao(html):
    regex_data_hora = r'(\d{2}/\d{2}/\d{4})\s(\d{2}:\d{2}:\d{2})'
    match = re.search(regex_data_hora, html)
    if match:
        data_original = match.group(1)
        partes_data = data_original.split('/')
        data = f"{partes_data[2]}-{partes_data[1]}-{partes_data[0]}"
        hora = match.group(2)
        return {"data": data, "hora": hora}
    return {"data": "Não encontrado", "hora": "Não encontrado"}

def extrair_itens(html, debug_level=0):
    log("Iniciando parsing do HTML com BeautifulSoup.", debug_level)
    soup = BeautifulSoup(html, 'html.parser')
    itens = []

    # Procurar a tabela com id="tabResult"
    tabela = soup.find('table', {'id': 'tabResult'})
    if not tabela:
        log("Erro: Nenhuma tabela com id='tabResult' encontrada.", debug_level)
        with open("debug_nfce_itens.html", "w", encoding="utf-8") as f:
            f.write(str(soup))
        log("HTML salvo em debug_nfce_itens.html para inspeção.", debug_level)
        return itens

    log(f"Tabela com id='tabResult' encontrada com {len(tabela.find_all('tr'))} linhas.", debug_level)
    linhas = tabela.find_all('tr')

    for i, linha in enumerate(linhas):
        log(f"Processando linha {i + 1}.", debug_level)
        colunas = linha.find_all('td')
        log(f"Linha contém {len(colunas)} colunas.", debug_level)

        # Esperamos 2 colunas por linha
        if len(colunas) != 2:
            log(f"Linha ignorada: esperado 2 colunas, mas encontrou {len(colunas)}.", debug_level)
            continue

        try:
            # Primeira coluna: contém descrição, código, quantidade, unidade, valor unitário
            primeira_coluna = colunas[0]
            # Descrição
            descricao_elem = primeira_coluna.find('span', {'class': 'txtTit'})
            descricao = descricao_elem.get_text(strip=True) if descricao_elem else "N/A"
            # Código
            codigo_elem = primeira_coluna.find('span', {'class': 'RCod'})
            codigo_raw = codigo_elem.get_text(strip=True) if codigo_elem else "N/A"
            # Limpar o código, removendo "(Código: ", ")", quebras de linha e espaços extras
            codigo = re.sub(r'\(Código:\s*', '', codigo_raw).replace(')', '').strip()
            codigo = re.sub(r'\s+', '', codigo)  # Remove quebras de linha e espaços extras
            # Quantidade
            quantidade_elem = primeira_coluna.find('span', {'class': 'Rqtd'})
            quantidade = quantidade_elem.get_text(strip=True).replace('Qtde.:', '').strip() if quantidade_elem else "1"
            # Unidade
            unidade_elem = primeira_coluna.find('span', {'class': 'RUN'})
            unidade_raw = unidade_elem.get_text(strip=True) if unidade_elem else "UN"
            # Limpar a unidade, removendo "UN: " e espaços extras
            unidade = re.sub(r'UN:\s*', '', unidade_raw).strip()
            # Valor Unitário
            vl_unitario_elem = primeira_coluna.find('span', {'class': 'RvlUnit'})
            vl_unitario = vl_unitario_elem.get_text(strip=True).replace('Vl. Unit.:', '').strip() if vl_unitario_elem else "0"

            # Segunda coluna: contém o valor total
            segunda_coluna = colunas[1]
            vl_total_elem = segunda_coluna.find('span', {'class': 'valor'})
            vl_total = vl_total_elem.get_text(strip=True) if vl_total_elem else vl_unitario

            # Limpar e converter valores numéricos
            quantidade = re.sub(r'[^\d,.]', '', quantidade).replace(',', '.')
            vl_unitario = re.sub(r'[^\d,.]', '', vl_unitario).replace(',', '.')
            vl_total = re.sub(r'[^\d,.]', '', vl_total).replace(',', '.')

            # Verificar se os campos obrigatórios foram preenchidos
            if descricao and descricao != "N/A":
                item = {
                    "codigo": codigo,
                    "descricao": descricao,
                    "quantidade": float(quantidade) if quantidade else 1.0,
                    "unidade": unidade,
                    "vlUnitario": float(vl_unitario) if vl_unitario else 0.0,
                    "vlTotal": float(vl_total) if vl_total else 0.0
                }
                log(f"Item adicionado: {item}", debug_level)
                itens.append(item)
            else:
                log("Linha ignorada: descrição não encontrada.", debug_level)
        except Exception as e:
            log(f"Erro ao processar linha {i + 1}: {e}", debug_level)

    log(f"Total de itens extraídos: {len(itens)}", debug_level)
    with open("debug_nfce_itens.html", "w", encoding="utf-8") as f:
        f.write(str(soup))
    log("HTML salvo em debug_nfce_itens.html para inspeção.", debug_level)

    return itens

def extrair_numero_nfce(html):
    inicio = '<strong>Número: </strong>'
    start = html.index(inicio) if inicio in html else -1
    if start == -1:
        return "Não encontrado"
    start += len(inicio)
    end = html.find('<', start)
    return html[start:end].strip()

def extrair_consumidor(html):
    soup = BeautifulSoup(html, "html.parser")
    # Procurar o elemento <strong> dentro da seção "Consumidor"
    consumidor_section = soup.find('div', {'data-role': 'collapsible'}, string=lambda text: 'Consumidor' in str(text))
    if consumidor_section:
        consumidor = consumidor_section.find('strong')
        return consumidor.get_text(strip=True) if consumidor else "Não identificado"
    return "Não identificado"

def extrair_texto_entre(html, inicio, fim):
    start = html.index(inicio) if inicio in html else -1
    if start == -1:
        return ""
    start += len(inicio)
    end = html.index(fim, start) if fim in html[start:] else -1
    if end == -1:
        return ""
    texto = html[start:end].strip()
    return texto.replace('\xa0', '')

def gerar_nome_curto(descricao):
    palavras = descricao.strip().split()
    ignorar = ["DE", "DA", "DO", "E", "COM", "BARRA", "MINI", "PV"]
    palavras_filtradas = [p for p in palavras if p.upper() not in ignorar]
    return (palavras_filtradas[0] + " " + palavras_filtradas[1]).upper() if len(palavras_filtradas) > 1 else palavras_filtradas[0].upper()

def gerar_categoria(descricao):
    descricao = descricao.lower()
    if re.search(r'pao|torrada|pizza|torta|panetone', descricao):
        return "Padaria"
    if re.search(r'chocolate|choc|biscoito|bombom|doce|gelatina|sorvete|torta|panetone|bis', descricao):
        return "Doces e Sobremesas"
    if re.search(r'batata|cenoura|tomate|alface|cebola|abobora|couve|brocolis|pepino', descricao):
        return "Legumes e Verduras"
    if re.search(r'acai|achocolatado|cha|cafe|suco|cerveja|coca|refrigerante', descricao):
        return "Bebidas"
    if re.search(r'frango|acem|alcatra|carne|bife|peixe|linguica|patinho|paleta', descricao):
        return "Carnes"
    if re.search(r'abacate|banana|laranja|limao|mamao|manga|morango|uva|abacaxi|melancia', descricao):
        return "Frutas"
    if re.search(r'arroz|feijao|macarrao|farinha|milho|aveia|sal|tempero|oleo|azeite|maionese', descricao):
        return "Graos e Cereais"
    if re.search(r'sabao|detergente|amaciante|desinfetante|alcool|toalha|sabonete|veja|esponja', descricao):
        return "Higiene e Limpeza"
    if re.search(r'leite|queijo|requeijao|ovo|manteiga|creme de leite|iogurte|yakult', descricao):
        return "Laticinios"
    return "Outros"

def consultar_sat(chave, driver, debug_level=0):
    log(f"Tentativa 1 de consultar SAT para chave {chave}", debug_level)
    try:
        driver.get("https://satsp.fazenda.sp.gov.br/COMSAT/Public/ConsultaPublica/ConsultaPublicaCfe.aspx")
        log("Aguardando campo de chave...", debug_level)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "conteudo_txtChaveAcesso"))
        )
        log("Preenchendo campo de chave...", debug_level)
        driver.find_element(By.ID, "conteudo_txtChaveAcesso").send_keys(chave)
        log(f"Resolva o CAPTCHA para SAT (chave {chave}), depois clique em CONSULTAR...", debug_level)
        
        log("Aguardando página do cupom...", debug_level)
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "divTelaImpressao")),
            message="Timeout waiting for SAT page"
        )
        html = driver.page_source
        log("HTML capturado, extraindo dados...", debug_level)
        with open("debug_sat.html", "w", encoding="utf-8") as f:
            f.write(html)
        log("HTML salvo em debug_sat.html para debug.", debug_level)
        
        dados = {}
        try:
            dados["emitente"] = extrair_texto_entre(html, 'id="conteudo_lblNomeEmitente">', '</span>').strip() or "N/A"
            log(f"Emitente extraído: {dados['emitente']}", debug_level)
            dados["cnpj"] = extrair_texto_entre(html, 'id="conteudo_lblCnpjEmitente">', '</span>').strip() or "N/A"
            log(f"CNPJ extraído: {dados['cnpj']}", debug_level)
            endereco = extrair_texto_entre(html, 'id="conteudo_lblEnderecoEmintente">', '</span>').strip()
            bairro = extrair_texto_entre(html, 'id="conteudo_lblBairroEmitente">', '</span>').strip()
            cidade = extrair_texto_entre(html, 'id="conteudo_lblMunicipioEmitente">', '</span>').strip()
            cep = extrair_texto_entre(html, 'id="conteudo_lblCepEmitente">', '</span>').strip()
            dados["endereco"] = f"{endereco}, {bairro}, {cidade}, CEP {cep}".strip()
            log(f"Endereço extraído: {dados['endereco']}", debug_level)
        except Exception as e:
            log(f"Erro ao extrair emitente: {e}", debug_level)
            dados["emitente"] = dados["cnpj"] = dados["endereco"] = "N/A"
        
        try:
            dados["numeroSAT"] = extrair_texto_entre(html, 'id="conteudo_lblNumeroCfe">', '</span>').strip() or "N/A"
            log(f"Número SAT extraído: {dados['numeroSAT']}", debug_level)
            dados["data"] = extrair_texto_entre(html, 'id="conteudo_lblDataEmissao">', '</span>').strip() or "N/A"
            log(f"Data extraída: {dados['data']}", debug_level)
            dados["sat"] = extrair_texto_entre(html, 'id="conteudo_lblSatNumeroSerie">', '</span>').strip() or "N/A"
            log(f"SAT extraído: {dados['sat']}", debug_level)
            dados["total"] = limpar_valor(extrair_texto_entre(html, 'id="conteudo_lblTotal">', '</span>').strip()) or "0.0"
            log(f"Total extraído: {dados['total']}", debug_level)
            dados["emissao"] = {
                "data": dados["data"].split(" - ")[0] if " - " in dados["data"] else dados["data"],
                "hora": dados["data"].split(" - ")[1] if " - " in dados["data"] else "N/A"
            }
            dados["consumidor"] = extrair_texto_entre(html, 'id="conteudo_lblRazaoSocial">', '</span>').strip() or "N/A"
            log(f"Consumidor extraído: {dados['consumidor']}", debug_level)
        except Exception as e:
            log(f"Erro ao extrair cupom: {e}", debug_level)
            dados["numeroSAT"] = dados["data"] = dados["sat"] = "N/A"
            dados["total"] = "0.0"
            dados["emissao"] = {"data": "N/A", "hora": "N/A"}
            dados["consumidor"] = "N/A"
        
        dados["itens"] = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            tabela = soup.find('table', {'id': 'tableItens'})
            if tabela:
                log("Tabela encontrada via BeautifulSoup, processando...", debug_level)
                for row in tabela.find_all('tr')[1:]:
                    cols = row.find_all('td')
                    if len(cols) >= 8:
                        try:
                            item = {
                                "numero": cols[0].text.strip(),
                                "codigo": cols[1].text.strip(),
                                "descricao": cols[2].text.strip(),
                                "quantidade": limpar_valor(cols[3].text.strip()) or "1.0",
                                "unidade": cols[4].text.strip() or "UN",
                                "vlUnitario": limpar_valor(cols[5].text.strip()) or "0.0",
                                "vlTotal": limpar_valor(cols[7].text.strip()) or "0.0"
                            }
                            log(f"Item extraído: {item}", debug_level)
                            dados["itens"].append(item)
                        except Exception as e:
                            log(f"Erro ao extrair item: {e}", debug_level)
                            continue
            else:
                log("Tabela de itens não encontrada no HTML, logando trecho...", debug_level)
                div_impressao = re.search(r'<div id="divTelaImpressao"[\s\S]*?</div>', html)
                if div_impressao:
                    with open("debug_tabela.html", "w", encoding="utf-8") as f:
                        f.write(div_impressao.group(0))
                    log("Trecho do HTML salvo em debug_tabela.html.", debug_level)
        
        except Exception as e:
            log(f"Erro ao extrair itens: {e}", debug_level)
        
        return dados
    except TimeoutException:
        log(f"Timeout na consulta SAT para chave {chave}. Verifique o CAPTCHA.", debug_level)
        return {}
    except Exception as e:
        log(f"Erro na consulta SAT: {e}", debug_level)
        return {}

def clean_float(value):
    """Remove símbolos e caracteres não numéricos de um valor monetário e converte para float."""
    if not value:
        return 0.0
    # Remove $, espaços, e substitui vírgula por ponto (se necessário)
    cleaned = value.replace('$', '').replace(' ', '').replace(',', '.').strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def processar_imagem(caminho_imagem=None, chave_manual=None, debug_level=0, from_bot=False):
    global driver, spreadsheet
    try:
        if chave_manual:
            log(f"Processando chave manual: {chave_manual}", debug_level)
            codigo = chave_manual
        else:
            log(f"\nProcessando imagem: {os.path.basename(caminho_imagem)}", debug_level)
            dados_qr, mensagem_qr = preprocessar_imagem(caminho_imagem, debug_level)
            if not dados_qr:
                log(f"Imagem {os.path.basename(caminho_imagem)}: {mensagem_qr}", debug_level)
                if driver:
                    log(f"Redirecionando para IDLE_PAGE devido a falha de detecção.", debug_level)
                    driver.get(IDLE_PAGE)
                return None
            codigo = dados_qr[0]
            log(f"Conteúdo bruto detectado: {codigo}", debug_level)

        chave = None
        is_sat = False

        log(f"Validando código: {codigo}", debug_level)
        # Verificar se a chave tem o prefixo "s" para indicar SAT
        if codigo.lower().startswith("s") and len(codigo) == 45:  # 44 dígitos + "s"
            log("Prefixo 's' detectado, tratando como SAT diretamente.", debug_level)
            chave = codigo[1:]  # Remove o "s" do início
            is_sat = True
        elif "qrcode" in codigo.lower():
            chave_match = re.search(r'p=(\d{44})(?:\|.*)?', codigo)
            chave = chave_match.group(1) if chave_match else None
        elif re.match(r'^\d{44}$', codigo.strip()):
            chave = codigo.strip()

        if not chave or len(chave) != 44:
            log(f"Chave inválida: {codigo}", debug_level)
            if driver and caminho_imagem:
                log(f"Redirecionando para IDLE_PAGE devido a chave inválida.", debug_level)
                driver.get(IDLE_PAGE)
            return None

        # Verificar duplicatas na aba "chaves44"
        log(f"Verificando duplicatas na aba chaves44 para chave {chave}...", debug_level)
        chaves_sheet = spreadsheet.worksheet("chaves44")
        chaves_data = chaves_sheet.get_all_values()
        numero_recibo_to_check = None
        existing_data = None

        for row in chaves_data[1:]:  # Ignorar o cabeçalho
            if len(row) > 0 and row[0].strip() == chave:
                numero_recibo_to_check = row[1].strip() if len(row) > 1 else "N/A"
                log(f"Chave {chave} encontrada na aba chaves44 com NumeroRecibo {numero_recibo_to_check}.", debug_level)
                # Buscar dados na aba "DADOS" usando NumeroRecibo
                sheet_data = sheet.get_all_values()
                chave_column_index = 2  # Coluna C (índice 2) contém o número do recibo
                for row in sheet_data[1:]:  # Ignorar o cabeçalho
                    if len(row) > chave_column_index and row[chave_column_index].strip() == numero_recibo_to_check:
                        log(f"Documento com NumeroRecibo {numero_recibo_to_check} encontrado na aba DADOS.", debug_level)
                        existing_data = {
                            "empresa": row[0] if len(row) > 0 else "N/A",
                            "cnpj": row[1] if len(row) > 1 else "N/A",
                            "numeroRecibo": numero_recibo_to_check,
                            "consumidor": row[3] if len(row) > 3 else "N/A",
                            "itens": [],
                            "emissao": {
                                "data": row[12] if len(row) > 12 else "N/A",
                                "hora": row[13] if len(row) > 13 else "N/A"
                            },
                            "is_sat": row[14] if len(row) > 14 else False,  # Supondo que a coluna 15 (índice 14) indique se é SAT
                            "data": row[12] if len(row) > 12 else "N/A",
                            "is_duplicate": True
                        }
                        # Adicionar itens
                        for item_row in sheet_data[1:]:
                            if len(item_row) > chave_column_index and item_row[chave_column_index].strip() == numero_recibo_to_check:
                                item = {
                                    "codigo": item_row[4] if len(item_row) > 4 else "N/A",
                                    "nomeCurto": item_row[5] if len(item_row) > 5 else "N/A",
                                    "categoria": item_row[6] if len(item_row) > 6 else "N/A",
                                    "descricao": item_row[7] if len(item_row) > 7 else "N/A",
                                    "quantidade": float(item_row[8]) if len(item_row) > 8 and item_row[8] else 0.0,
                                    "unidade": item_row[9] if len(item_row) > 9 else "UN",
                                    "vlUnitario": clean_float(item_row[10]) if len(item_row) > 10 and item_row[10] else 0.0,
                                    "vlTotal": clean_float(item_row[11]) if len(item_row) > 11 and item_row[11] else 0.0
                                }
                                existing_data["itens"].append(item)
                        break
                break

        if existing_data:
            log(f"Documento com NumeroRecibo {numero_recibo_to_check} já processado anteriormente!", debug_level)
            if from_bot:
                log(f"Retornando dados existentes para o bot Telegram.", debug_level)
                return existing_data
            else:
                log(f"Pulando consulta para chave {chave}.", debug_level)
                if caminho_imagem:
                    novo_nome = f"OK_{os.path.basename(caminho_imagem)}"
                    os.rename(caminho_imagem, os.path.join(os.path.dirname(caminho_imagem), novo_nome))
                    log(f"Imagem renomeada para {novo_nome}", debug_level)
                return None

        # Limpar o estado do navegador antes da consulta
        if driver:
            log("Limpando cookies e cache do navegador antes da consulta...", debug_level)
            driver.delete_all_cookies()

        # Prosseguir com a consulta
        dados = None
        if is_sat:
            log(f"Iniciando consulta SAT para chave {chave}.", debug_level)
            dados = consultar_sat(chave, driver, debug_level)
            if not dados or dados.get("numeroSAT") == "N/A":
                log(f"Chave {chave} inválida no SAT.", debug_level)
                return None
        else:
            # Tentar NFCe primeiro
            try:
                url = "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx"
                log(f"Acessando página de consulta NFCe: {url}", debug_level)
                driver.get(url)

                log("Aguardando campo de chave...", debug_level)
                campo_chave = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.ID, "Conteudo_txtChaveAcesso"))
                )

                log("Preenchendo campo de chave...", debug_level)
                campo_chave.clear()
                campo_chave.send_keys(chave)

                log("Aguardando botão Consultar...", debug_level)
                botao_consultar = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.ID, "Conteudo_btnConsultaResumida"))
                )

                log(f"Resolva o CAPTCHA para NFCe (chave {chave}), depois clique em CONSULTAR...", debug_level)

                try:
                    WebDriverWait(driver, 120).until(
                        lambda driver: (
                            driver.find_elements(By.CSS_SELECTOR, "tr[id^='Item']") or
                            driver.find_elements(By.CSS_SELECTOR, "table.tabelaItens") or
                            driver.find_elements(By.ID, "u20") or
                            driver.find_elements(By.CSS_SELECTOR, "span.msgErro") or
                            (
                                driver.find_elements(By.ID, "spnAlertaMaster") and
                                "Chave de Acesso Inválida [Não é referente a NFC-e - modelo 65]" in driver.find_element(By.ID, "spnAlertaMaster").text
                            )
                        )
                    )
                except SeleniumTimeoutException:
                    log("Timeout atingido ao aguardar resposta da consulta NFCe.", debug_level)
                    raise

                # Verificar se o erro específico foi encontrado
                if driver.find_elements(By.ID, "spnAlertaMaster"):
                    alerta = driver.find_element(By.ID, "spnAlertaMaster").text
                    if "Chave de Acesso Inválida [Não é referente a NFC-e - modelo 65]" in alerta:
                        log(f"Erro detectado: {alerta}. Tentando consulta SAT...", debug_level)
                        dados = consultar_sat(chave, driver, debug_level)
                        if not dados or dados.get("numeroSAT") == "N/A":
                            log(f"Chave {chave} também inválida no SAT.", debug_level)
                            return None
                        is_sat = True
                    else:
                        log(f"Erro inesperado na consulta NFCe: {alerta}", debug_level)
                        return None
                else:
                    # Processamento normal para NFCe
                    time.sleep(2)
                    html = driver.page_source
                    with open("debug_nfce.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    log("HTML da NFCe salvo em debug_nfce.html para inspeção.", debug_level)

                    soup = BeautifulSoup(html, "html.parser")
                    error = soup.find("span", {"class": "msgErro"})
                    if error and "Chave de Acesso Inválida" in error.text:
                        log(f"Chave {chave} inválida na NFCe, tentando SAT...", debug_level)
                        dados = consultar_sat(chave, driver, debug_level)
                        if not dados or dados.get("numeroSAT") == "N/A":
                            log(f"Chave {chave} também inválida no SAT.", debug_level)
                            return None
                        is_sat = True
                    else:
                        html_limpo = html
                        html_limpo_sem_acentos = remover_acentos(html_limpo)
                        dados = {
                            "empresa": extrair_empresa(html_limpo_sem_acentos),
                            "cnpj": extrair_cnpj(html_limpo_sem_acentos),
                            "emissao": extrair_emissao(html_limpo),
                            "itens": extrair_itens(html_limpo, debug_level),
                            "consumidor": extrair_consumidor(html_limpo),
                            "numeroRecibo": extrair_numero_nfce(html_limpo)
                        }
                        log(f"Itens extraídos: {len(dados['itens'])}", debug_level)
                        if not dados["itens"]:
                            log(f"Nenhum item encontrado na NFCe para chave {chave}, tentando SAT...", debug_level)
                            dados = consultar_sat(chave, driver, debug_level)
                            if not dados or dados.get("numeroSAT") == "N/A":
                                log(f"Chave {chave} também inválida no SAT.", debug_level)
                                return None
                            is_sat = True
            except (TimeoutException, NoSuchElementException) as e:
                log(f"Erro ao consultar NFCe: {e}, tentando SAT...", debug_level)
                dados = consultar_sat(chave, driver, debug_level)
                if not dados or dados.get("numeroSAT") == "N/A":
                    log(f"Chave {chave} também inválida no SAT.", debug_level)
                    return None
                is_sat = True
            except WebDriverException as e:
                log(f"Erro de WebDriver ao consultar NFCe: {e}, tentando SAT...", debug_level)
                dados = consultar_sat(chave, driver, debug_level)
                if not dados or dados.get("numeroSAT") == "N/A":
                    log(f"Chave {chave} também inválida no SAT.", debug_level)
                    return None
                is_sat = True
            except Exception as e:
                log(f"Erro inesperado ao consultar NFCe: {e}, tentando SAT...", debug_level)
                dados = consultar_sat(chave, driver, debug_level)
                if not dados or dados.get("numeroSAT") == "N/A":
                    log(f"Chave {chave} também inválida no SAT.", debug_level)
                    return None
                is_sat = True

        if not dados:
            log(f"Falha ao consultar chave {chave}.", debug_level)
            return None

        # Adicionar nomeCurto e categoria aos itens
        dados["itens"] = [
            {
                **item,
                "nomeCurto": gerar_nome_curto(item["descricao"]),
                "categoria": gerar_categoria(item["descricao"])
            }
            for item in dados["itens"]
        ]

        # Renomear a chave para numeroRecibo, independentemente de ser SAT ou NFCe
        if is_sat:
            dados["numeroRecibo"] = dados.get("numeroSAT", "N/A")
        else:
            dados["numeroRecibo"] = dados.get("numeroRecibo", "N/A")

        # Verificar duplicatas na aba DADOS por NumeroRecibo + CNPJ
        log(f"Verificando duplicatas na aba DADOS para NumeroRecibo {dados['numeroRecibo']} e CNPJ {dados['cnpj']}...", debug_level)
        sheet_data = sheet.get_all_values()
        numero = dados.get("numeroRecibo", "N/A")
        cnpj = dados.get("cnpj", "N/A")
        is_duplicate = False
        existing_data = None
        for row in sheet_data[1:]:  # Ignorar o cabeçalho
            if (len(row) > 2 and row[2].strip() == numero and 
                len(row) > 1 and row[1].strip() == cnpj):
                log(f"Duplicata encontrada na aba DADOS: NumeroRecibo {numero}, CNPJ {cnpj}.", debug_level)
                is_duplicate = True
                existing_data = {
                    "empresa": row[0] if len(row) > 0 else "N/A",
                    "cnpj": row[1] if len(row) > 1 else "N/A",
                    "numeroRecibo": numero,
                    "consumidor": row[3] if len(row) > 3 else "N/A",
                    "itens": [],
                    "emissao": {
                        "data": row[12] if len(row) > 12 else "N/A",
                        "hora": row[13] if len(row) > 13 else "N/A"
                    },
                    "is_sat": is_sat,
                    "data": row[12] if len(row) > 12 else "N/A",
                    "is_duplicate": True
                }
                for item_row in sheet_data[1:]:
                    if (len(item_row) > 2 and item_row[2].strip() == numero and 
                        len(item_row) > 1 and item_row[1].strip() == cnpj):
                        item = {
                            "codigo": item_row[4] if len(item_row) > 4 else "N/A",
                            "nomeCurto": item_row[5] if len(item_row) > 5 else "N/A",
                            "categoria": item_row[6] if len(item_row) > 6 else "N/A",
                            "descricao": item_row[7] if len(item_row) > 7 else "N/A",
                            "quantidade": float(item_row[8]) if len(item_row) > 8 and item_row[8] else 0.0,
                            "unidade": item_row[9] if len(item_row) > 9 else "UN",
                            "vlUnitario": clean_float(item_row[10]) if len(item_row) > 10 and item_row[10] else 0.0,
                            "vlTotal": clean_float(item_row[11]) if len(item_row) > 11 and item_row[11] else 0.0
                        }
                        existing_data["itens"].append(item)
                break

        if is_duplicate:
            if from_bot:
                log(f"Retornando dados existentes para o bot Telegram.", debug_level)
                return existing_data
            else:
                log(f"Duplicata encontrada, pulando gravação para chave {chave}.", debug_level)
                if caminho_imagem:
                    novo_nome = f"OK_{os.path.basename(caminho_imagem)}"
                    os.rename(caminho_imagem, os.path.join(os.path.dirname(caminho_imagem), novo_nome))
                    log(f"Imagem renomeada para {novo_nome}", debug_level)
                return None

        # Gravar na planilha
        if dados["itens"]:
            # Backup da planilha DADOS
            with open(f"NFCes_backup_{time.strftime('%Y%m%d_%H%M%S')}.csv", "w", encoding="utf-8") as f:
                for row in sheet_data:
                    f.write(",".join(row) + "\n")

            # Gravar na aba DADOS
            linhas = [
                [
                    dados["emitente"] if is_sat else dados["empresa"],
                    dados["cnpj"],
                    dados["numeroRecibo"],
                    dados["consumidor"],
                    item["codigo"],
                    item["nomeCurto"],
                    item["categoria"],
                    item["descricao"],
                    float(item["quantidade"]),
                    item["unidade"].upper(),
                    clean_float(str(item["vlUnitario"])),
                    clean_float(str(item["vlTotal"])),
                    dados["emissao"]["data"],
                    dados["emissao"]["hora"],
                    str(is_sat)  # Adiciona se é SAT ou não na última coluna (supondo que seja a coluna 15)
                ]
                for item in dados["itens"]
            ]
            sheet.append_rows(linhas, value_input_option="RAW")
            log(f"✅ Dados da chave {chave} ({'SAT' if is_sat else 'NFCe'}) inseridos na aba DADOS!", debug_level)

            # Gravar na aba chaves44
            chaves_sheet = spreadsheet.worksheet("chaves44")
            chaves_sheet.append_row([chave, numero], value_input_option="RAW")
            log(f"✅ Chave {chave} e NumeroRecibo {numero} inseridos na aba chaves44!", debug_level)

            if caminho_imagem:
                novo_nome = f"OK_{os.path.basename(caminho_imagem)}"
                os.rename(caminho_imagem, os.path.join(os.path.dirname(caminho_imagem), novo_nome))
                log(f"Imagem renomeada para {novo_nome}", debug_level)
        else:
            log(f"❌ Nenhum item encontrado para a chave {chave}", debug_level)
            return None

        dados["is_sat"] = is_sat
        dados["data"] = dados["emissao"]["data"]
        return dados

    except Exception as e:
        log(f"Erro ao processar: {e}", debug_level)
        if driver:
            log(f"Redirecionando para IDLE_PAGE devido a erro.", debug_level)
            driver.get(IDLE_PAGE)
        return None
    finally:
        if driver:
            log(f"Fechando sessão ou redirecionando após processamento.", debug_level)
            driver.get(IDLE_PAGE)

# Configuração do ChromeDriver
options = webdriver.ChromeOptions()
options.add_argument('--ignore-certificate-errors')
options.add_argument('--ignore-ssl-errors')
options.add_argument('--log-level=3')
service = Service(executable_path="chromedriver.exe", log_path="NUL")
driver = webdriver.Chrome(service=service, options=options)

# Redimensionar a janela para 1/4 do tamanho atual
tamanho_atual = driver.get_window_size()
largura_atual = tamanho_atual['width']
altura_atual = tamanho_atual['height']
nova_largura = max(500, largura_atual // 2)  # Metade da largura, com mínimo de 500 pixels
nova_altura = max(500, altura_atual // 2)    # Metade da altura, com mínimo de 500 pixels
driver.set_window_size(nova_largura, nova_altura)
logging.info(f"Janela do navegador redimensionada para {nova_largura}x{nova_altura}")

# Processamento em lote
def main(debug_level=0):
    pasta_recibos = "recibos/"
    imagens = [f for f in os.listdir(pasta_recibos) if f.endswith((".png", ".jpg", ".jpeg")) and not f.startswith("OK")]
    chaves_processadas = set()

    for imagem in imagens:
        caminho_imagem = os.path.join(pasta_recibos, imagem)
        dados = processar_imagem(caminho_imagem=caminho_imagem, debug_level=debug_level)
        if dados and dados.get("chave"):
            chaves_processadas.add(dados["chave"])

    driver.quit()
    log("Consulta concluída!", debug_level)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", type=int, default=0, choices=[0, 1], help="Nível de debug: 0 (mínimo), 1 (completo)")
    args = parser.parse_args()
    main(debug_level=args.debug)