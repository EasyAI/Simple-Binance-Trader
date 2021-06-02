#! /usr/bin/env python3
import os
import logging
from core import botCore

## Setup    
cwd = os.getcwd()
CACHE_DIR = 'cache/'.format(cwd)
LOGS_DIR = 'logs/'.format(cwd)

## Settup logging.
log_format = '%(asctime)s:%(name)s:%(message)s'
logging.basicConfig(
    format=log_format,
    level=logging.INFO)
logger = logging.getLogger()

SETTINGS_FILE_NAME = 'settings.conf'
DEFAULT_SETTINGS_DATA = '''# Public and Private key pais used for the for the trader.
PUBLIC_KEY=
PRIVATE_KEY=

# Allow trader to be run in test mode (True/False).
IS_TEST=True

# Allow trader to be run in either spot or margin type.
MARKET_TYPE=SPOT

# Automatically update the BNB balance when low (for trading fees, only applicable to real trading)
UPDATE_BNB_BALANCE=True

# Interval used for the trader (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d).
TRADER_INTERVAL=15m

# The currency max the trader will use (in BTC) also note this scales up with the number of markets i.e. 2 pairs each market will have 0.0015 as their trading currency pair.
TRADING_CURRENCY=0.002

# The markets that will be traded (currently only BTC markets) seperate markets with a , for multi market trading.
TRADING_MARKETS=BTC-ETH,BTC-LTC

# Configuration for the webapp (default if left blank is IP=127.0.0.1, Port=5000)
HOST_IP=
HOST_PORT=

# Configuration for the candle range and depth range (default if left bank is candles=500, Depth=50)
MAX_CANDLES=
MAX_DEPTH=
'''


def settings_reader():
    # Setting reader function to parse over the settings file and collect kv pairs.

    ## Setup settings file object with initial default variables.
    settings_file_data = {'public_key':'', 'private_key':'', 'host_ip':'127.0.0.1', 'host_port':5000, 'max_candles':500,'max_depth':50}

    ## Read the settings file and extract the fields.
    with open(SETTINGS_FILE_NAME, 'r') as f:
        for line in f.readlines():

            ### Check for kv line.
            if not('=' in line) or line[0] == '#':
                continue

            key, data = line.split('=')

            ### Check if data holds a value.
            if data == None or data == '\n':
                continue

            data = data.replace('\n', '')

            if key == 'IS_TEST':
                data = 'TEST' if data.upper() == 'TRUE' else 'REAL'
                key = 'run_type'

            elif key == 'MARKET_TYPE':
                data = data.upper()

            elif key == 'TRADING_MARKETS':
                data = data.replace(' ', '')
                data = data.split(',') if ',' in data else [data]

            elif key == 'HOST_IP':
                default_ip = '127.0.0.1'

            elif key == 'HOST_PORT':
                data = int(data)

            elif key == 'MAX_CANDLES':
                data = int(data)

            elif key == 'MAX_DEPTH':
                data = int(data)

            settings_file_data.update({key.lower():data})

    return(settings_file_data)


if __name__ == '__main__':

    ## Check and make cache/logs dir.
    if not(os.path.exists(LOGS_DIR)):
        os.makedirs(LOGS_DIR, exist_ok=True)
    if not(os.path.exists(CACHE_DIR)):
        os.makedirs(CACHE_DIR, exist_ok=True)

    ## Load settings/create settings file.
    if os.path.exists(SETTINGS_FILE_NAME):
        settings = settings_reader()
        botCore.start(settings, LOGS_DIR, CACHE_DIR)
    else:
        with open(SETTINGS_FILE_NAME, 'w') as f:
            f.write(DEFAULT_SETTINGS_DATA)
        print('Created settings.conf file.')

