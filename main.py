import requests
from telegram import Bot
import logging
import asyncio
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID='@memecoinsolprice'
URL = "https://api.dexscreener.com/latest/dex/tokens/"

def chunk_list(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]

def dexScreenerRequest(tokens):
    try:
        tokens_str = ','.join(tokens)
        response = requests.get(URL + tokens_str)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f'Error en la petición: status code {response.status_code}')
            return None
    except Exception as e:
        logging.error(f'Error en dexScreenerRequest: {str(e)}')
        return None

def getTokensInfo(tokens):
    data = dexScreenerRequest(tokens)
    if data is None:
        return [None] * len(tokens)
    results = []
    try:
        pairs_dict = {pair['baseToken']['address'].lower(): pair for pair in data['pairs']}
        for token in tokens:
            if token.lower() in pairs_dict:
                pair = pairs_dict[token.lower()]
                info = {}
                baseToken = pair['baseToken']
                info['symbol'] = baseToken['symbol']
                info['priceUsd'] = float(pair['priceUsd']) if 'priceUsd' in pair and pair['priceUsd'] is not None else 0.0
                fdv_value = pair.get('fdv')
                if fdv_value is not None:
                    info['fdv'] = f"${float(fdv_value)/1000000:.1f}M"
                else:
                    info['fdv'] = "-"
                if 'priceChange' in pair:
                    price_change = pair['priceChange']
                    info['priceChange'] = {
                        '24h': str(price_change.get('h24', '0')),
                        '1h': str(price_change.get('h1', '0')),
                        '5m': str(price_change.get('m5', '0'))
                    }
                else:
                    info['priceChange'] = {'24h': '0', '1h': '0', '5m': '0'}
                results.append(info)
            else:
                logging.warning(f'Token no encontrado: {token}')
                results.append(None)
    except Exception as e:
        logging.error(f'Error procesando tokens: {str(e)}')
        return [None] * len(tokens)
    return results

def getInfoFromAddys(addys):
    MAX_TOKENS_PER_REQUEST = 30
    all_results = []
    address_chunks = chunk_list(addys, MAX_TOKENS_PER_REQUEST)
    for chunk in address_chunks:
        chunk_results = getTokensInfo(chunk)
        all_results.extend(chunk_results)
    return all_results

def getAddresses(path):
    addresses = []
    try:
        with open(path, 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = [part for part in line.split() if part]
                    if parts:
                        addresses.append(parts[0])
        logging.info(f"Direcciones encontradas: {len(addresses)}")
    except FileNotFoundError:
        logging.error(f"El archivo {path} no existe")
    except Exception as e:
        logging.error(f"Error al leer el archivo: {str(e)}")
    return addresses

def format_table(tokens):
    for token in tokens:
        if token is None:
            continue
        if 'fdv' not in token or token['fdv'] is None:
            token['fdv'] = "-"
        if 'priceUsd' not in token or token['priceUsd'] is None:
            token['priceUsd'] = 0.0

    max_coin_width = max(len(f"${token['symbol'].lstrip('$')}") for token in tokens if token is not None)
    max_mcap_width = max(
        max((len(token['fdv']) for token in tokens[2:] if token is not None and token['fdv']), default=1),
        max((len(f"${token['priceUsd']:.8f}") for token in tokens[:2] if token is not None), default=1)
    )
    max_24h_num = max((len(f"{float(token['priceChange']['24h']):+6.2f}%") for token in tokens if token is not None), default=7)
    max_24h_width = max(max_24h_num + 2, 7)

    table = ""
    for idx, token in enumerate(tokens):
        if token is None:
            continue
        pc = token['priceChange']
        change_24h = float(pc['24h'])
        if change_24h >= 30:
            emoji = '🔥'
        else:
            emoji = '🔴' if change_24h < 0 else '🟢'
        symbol = token['symbol'].lstrip('$')
        change_str = f"{emoji}{change_24h:+6.2f}%"
        mcap_or_price = token['fdv']
        table += f"${symbol:<{max_coin_width-1}} {mcap_or_price:<{max_mcap_width}} {change_str:>{max_24h_width}}\n"

    return f"<pre>{table}</pre>"

async def send_message():
    try:
        bot = Bot(token=TOKEN)
        addys = getAddresses('cas.txt')
        if not addys:
            logging.error("No se encontraron direcciones en el archivo")
            return
            
        data = getInfoFromAddys(addys)
        if not data:
            logging.error("No se pudo obtener información de los tokens")
            return
            
        table = format_table(data)
        await bot.send_message(chat_id=CHAT_ID, text=table, parse_mode='HTML')
        logging.info("Mensaje enviado exitosamente")
    except Exception as e:
        logging.error(f"Error al enviar mensaje: {str(e)}")

if __name__ == '__main__':
    asyncio.run(send_message())
