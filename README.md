# NFCe Automation Project

## Overview

O **NFCe Automation Project** é um sistema automatizado para consultar e processar recibos fiscais eletrônicos (NFCe e SAT) a partir de chaves ou imagens de QR codes. O sistema extrai informações detalhadas dos recibos (como empresa, itens, valores e data), armazena os dados em uma planilha no Google Sheets e fornece insights via Telegram. Ele é composto por dois scripts principais (`telegram_bot.py` e `nfce_automation.py`), uma planilha no Google Sheets para armazenamento de dados, e um bot no Telegram para interação com o usuário.

### Features
- **Consulta de Recibos**: Consulta recibos NFCe e SAT a partir de chaves de 44 dígitos ou imagens de QR codes.
- **Extração de Dados**: Extrai informações como empresa, CNPJ, número do recibo, itens, valores, data de emissão e mais.
- **Armazenamento**: Salva os dados extraídos em uma planilha no Google Sheets.
- **Insights**: Gera insights sobre gastos (valor médio, comparação com compras anteriores, gastos por categoria) e envia ao usuário via Telegram.
- **Automação de CAPTCHA**: Solicita ao usuário que resolva CAPTCHAs manualmente durante as consultas.
- **Suporte a SAT e NFCe**: Identifica automaticamente o tipo de recibo (SAT ou NFCe) e processa de acordo.

---

## Project Structure

A estrutura de pastas do projeto é a seguinte:
C:.
└───nfce-automation
    ├───recibos
    │   └─── (pasta para armazenar imagens de recibos enviadas pelo Telegram)
    ├───telegram_bot.py
    ├───nfce_automation.py
    ├───README.md
    ├───requirements.txt
    └─── (outros arquivos gerados, como logs e backups)

### Files and Folders
- **`nfce-automation/`**: Diretório raiz do projeto.
  - **`recibos/`**: Diretório onde são salvas as imagens de recibos enviadas pelo Telegram.
  - **`telegram_bot.py`**: Script que gerencia o bot no Telegram, processa mensagens de texto (chaves) e imagens (QR codes), e retorna respostas com insights.
  - **`nfce_automation.py`**: Script principal que realiza a consulta de recibos (NFCe e SAT), extrai dados, e grava na planilha do Google Sheets.
  - **`README.md`**: Documentação do projeto (este arquivo).
  - **`requirements.txt`**: Arquivo com as dependências Python necessárias para executar o projeto.

---

## Prerequisites

Antes de executar o projeto, você precisa dos seguintes pré-requisitos:

### Software
- **Python 3.8+**: Certifique-se de ter o Python instalado.
- **Google Chrome**: O script usa Selenium com ChromeDriver para automação do navegador.
- **ChromeDriver**: Deve ser compatível com a versão do Chrome instalada. Baixe em [chromedriver.chromium.org](https://chromedriver.chromium.org/downloads).

### APIs e Credenciais
- **Google Sheets API**:
  - Crie um projeto no [Google Cloud Console](https://console.cloud.google.com/).
  - Ative a API do Google Sheets.
  - Crie uma conta de serviço e baixe o arquivo de credenciais JSON (ex.: `credentials.json`).
  - Compartilhe a planilha do Google Sheets com o e-mail da conta de serviço.
- **Telegram Bot**:
  - Crie um bot no Telegram usando o [BotFather](https://t.me/BotFather).
  - Obtenha o token do bot (ex.: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`).

### Dependências Python
As dependências estão listadas no arquivo `requirements.txt`. As principais bibliotecas incluem:
- `selenium`: Para automação do navegador.
- `gspread`: Para interação com o Google Sheets.
- `python-telegram-bot`: Para criar e gerenciar o bot no Telegram.
- `beautifulsoup4`: Para parsing de HTML.
- `opencv-python`: Para processamento de imagens (leitura de QR codes).
- Outras dependências: `pyzbar`, `requests`, `numpy`, etc.

---

## Installation

Siga os passos abaixo para configurar e executar o projeto:

### 1. Clone o Repositório
Clone este repositório para o seu computador:
```bash
git clone https://github.com/dudapinto/nfce-automation.git
cd nfce-automation
```
### 2. Configure o Ambiente Python
Crie e ative um ambiente virtual (recomendado):
```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

### 3. Instale as Dependências
Instale as bibliotecas listadas em requirements.txt:
```bash
pip install -r requirements.txt
```
### 4. Configure o ChromeDriver
Baixe o ChromeDriver compatível com sua versão do Chrome em chromedriver.chromium.org.
Coloque o executável chromedriver no diretório do projeto ou em um local acessível no PATH do sistema.

### 5. Configure as Credenciais
Google Sheets:
Coloque o arquivo credentials.json (obtido no Google Cloud Console) no diretório raiz do projeto.

Crie uma planilha no Google Sheets com as seguintes abas:
DADOS: Para armazenar os dados dos recibos. As colunas devem ser:
Empresa  CNPJ  Número NFCE  Consumidor  Código  Nome curto  Categoria  Descrição  Quantidade  UN  Vl Unitário  Vl Total  Data Emissão  Hora Emissão  Dia Semana  SAT

chaves44: Para armazenar as chaves processadas e evitar duplicatas. As colunas devem ser:
Chave  NumeroRecibo

Compartilhe a planilha com o e-mail da conta de serviço (encontrado no arquivo credentials.json).

Telegram Bot:
Edite o arquivo telegram_bot.py e insira o token do seu bot na variável TOKEN:

```python
TOKEN = "seu_token_aqui"  # Ex.: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
```

### 6. Estrutura de Pastas
Certifique-se de que a pasta recibos existe dentro do diretório nfce-automation:
```bash
mkdir recibos
```

---

## Security Notes

Este projeto utiliza arquivos sensíveis que **não devem ser enviados ao repositório público** no GitHub:

- **`.env`**: Contém o token do Telegram (`TELEGRAM_TOKEN`).
- **`credentials.json`**: Contém as credenciais da API do Google Sheets.
- **`recibos/`**: Diretório que armazena imagens de recibos enviadas pelos usuários, que podem conter informações sensíveis.
- **`NFCes_backup_*.csv`**: Arquivos de backup da planilha, que contêm dados extraídos dos recibos.
- **`debug_*.html`**: Arquivos de log gerados para depuração, que podem conter dados sensíveis.

O arquivo `.gitignore` já foi configurado para excluir esses arquivos. Certifique-se de que eles não estão no histórico de commits antes de enviar o projeto ao GitHub. 

Caso já tenham sido incluídos, siga os seguintes passos  para removê-los do controle de versão (sem deletar do seu drive):
```bash
git rm -r --cached .env
git rm -r --cached credentials.json
git rm -r --cached recibos
git rm -r --cached NFCes_backup_*.csv
git rm -r --cached debug_*.html
```
Faça um novo commit:
```bash
git commit -m "Remove arquivos sensíveis do controle de versão"
```

## Usage
### 1. Inicie o Bot
Execute o script telegram_bot.py para iniciar o bot:

```bash
python telegram_bot.py
```
O bot será iniciado e você verá logs indicando que ele está ativo.

### 2. Interaja com o Bot no Telegram
Abra o Telegram no celular ou no navegador e encontre o seu bot (usando o nome configurado no BotFather).
Envie uma mensagem com uma chave de 44 dígitos (com ou sem espaços, e com um "s" opcional no início para submeter recibos SAT diretamente). Exemplo:
s35250427005574000109590013320951455824435644
ou
3525 0427 0055 7400 0109 5900 1332 0951 4558 2443 5644

Alternativamente, envie uma foto de um recibo com QR code visível.
O bot processará o recibo e responderá com detalhes da compra, incluindo:
Empresa, data, total, número de itens.
Insights como valor médio, comparação com compras anteriores e gastos por categoria.
Durante a consulta, o bot pode solicitar que você resolva um CAPTCHA manualmente no navegador.

### 3. Verifique a Planilha
Os dados processados serão automaticamente salvos na aba "DADOS" da planilha do Google Sheets, com as seguintes colunas:
Empresa: Nome da empresa emitente.
CNPJ: CNPJ da empresa.
Número NFCE: Número do recibo (SAT ou NFCe).
Consumidor: Nome do consumidor ou "Não identificado".
Código: Código do item.
Nome curto: Nome simplificado do item.
Categoria: Categoria do item (ex.: "Carnes", "Frutas").
Descrição: Descrição completa do item.
Quantidade: Quantidade do item (ex.: "0.800").
UN: Unidade de medida (ex.: "KG", "UN").
Vl Unitário: Valor unitário (ex.: "$39.90").
Vl Total: Valor total (ex.: "$31.92").
Data Emissão: Data no formato "M/D/YYYY" (ex.: "4/17/2025").
Hora Emissão: Hora no formato "HH:MM:SS" (ex.: "12:54:43").
Dia Semana: Número do dia da semana (0 = Domingo, ..., 6 = Sábado).
SAT: Indica se é um recibo SAT ("TRUE") ou NFCe ("FALSE").

## Scripts Overview

## nfce_automation.py
Este script é responsável por consultar recibos (NFCe e SAT), extrair dados, e gravar na planilha do Google Sheets.

### Main Functions:
processar_imagem(caminho_imagem=None, chave_manual=None, debug_level=0, from_bot=False):
Processa uma chave manual ou uma imagem de QR code.
Identifica se o recibo é SAT (prefixo "s") ou NFCe.
Consulta o recibo no site apropriado (SAT ou NFCe).
Extrai dados (empresa, CNPJ, itens, valores, etc.).
Verifica duplicatas na planilha.
Grava os dados na aba "DADOS" e registra a chave na aba "chaves44".
consultar_sat(chave, driver, debug_level):
Consulta recibos SAT no site do SAT.
Solicita ao usuário que resolva o CAPTCHA manualmente.
extrair_numero_nfce(html):
Extrai o número do recibo NFCe do HTML da página de consulta.
extrair_itens(html, debug_level):
Extrai a lista de itens do recibo (descrição, quantidade, valores, etc.).

### Dependencies:
Selenium (para automação do navegador).
BeautifulSoup (para parsing de HTML).
OpenCV e pyzbar (para leitura de QR codes).
gspread (para interação com o Google Sheets).

## telegram_bot.py
Este script gerencia o bot no Telegram, processando mensagens de texto (chaves) e imagens (QR codes), e retornando respostas com insights.

### Main Functions:
handle_text(update, context):
Processa mensagens de texto contendo chaves de 44 dígitos.
Valida o formato da chave e chama processar_imagem para consulta.
Retorna uma mensagem com os detalhes da compra e insights.
handle_photo(update, context):
Processa imagens enviadas pelo usuário.
Salva a imagem no diretório recibos/.
Chama processar_imagem para extrair o QR code e consultar o recibo.
Retorna uma mensagem com os detalhes da compra e insights.
calcular_insights(empresa, total, itens, is_sat):
Gera insights sobre a compra, como valor médio, comparação com compras anteriores, e gastos por categoria.

### Dependencies
python-telegram-bot (para criar o bot).
Logging (para logs).
Configuration

### Google Sheets
Crie uma planilha com as abas "DADOS" e "chaves44".
Configure as colunas da aba "DADOS" conforme descrito na seção "Usage".
Compartilhe a planilha com o e-mail da conta de serviço (encontrado no credentials.json).

### Telegram Bot
Crie um bot no Telegram usando o BotFather.
Edite telegram_bot.py e insira o token do bot na variável TOKEN.

### ChromeDriver
Certifique-se de que o ChromeDriver está instalado e acessível.
O script abrirá automaticamente o Chrome para consultas e solicitará CAPTCHAs manuais.

## Troubleshooting Common Issues

### Erro de Conexão com o Google Sheets:
Verifique se o arquivo credentials.json está no diretório correto.
Certifique-se de que a planilha foi compartilhada com o e-mail da conta de serviço.

### Erro de CAPTCHA:
O script solicita que o usuário resolva CAPTCHAs manualmente. Certifique-se de que o Chrome está visível e que você resolveu o CAPTCHA dentro do tempo limite.

### Erro de Chave Inválida:
Verifique se a chave tem exatamente 44 dígitos (ou 45 com o prefixo "s" para SAT).
Certifique-se de que a chave é válida para NFCe ou SAT.

### Erro de ChromeDriver:
Certifique-se de que a versão do ChromeDriver é compatível com a versão do Chrome instalada.

### Logs
Logs detalhados são gerados no console e podem ser úteis para depuração.
Para aumentar o nível de debug, ajuste o parâmetro debug_level na função processar_imagem.

### Contributing
Contribuições são bem-vindas! Siga os passos abaixo para contribuir:
Faça um fork deste repositório.

Crie uma branch para sua feature ou correção:
```bash
git checkout -b minha-feature
```
Faça suas alterações e commit:
```bash
git commit -m "Adiciona minha feature"
```
Envie suas alterações para o seu fork:

```bash
git push origin minha-feature
```
Crie um Pull Request.

## License
Este projeto está licenciado sob a MIT License (LICENSE). Veja o arquivo LICENSE para mais detalhes.

## Contact
Para dúvidas ou sugestões, abra uma issue:
