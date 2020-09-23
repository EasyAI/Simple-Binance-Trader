import os
import re
import json
import time
from os.path import exists, basename

cwd = os.getcwd()

CACHE_DIR = '{0}/cache/'.format(cwd)
CAHCE_FILES = ['markets.json', 'traders.json']
MAX_TIME = [345600, 1800]

def check_file_structure(order_logs, runtime_logs):
    file_path_splitter = re.compile(r'^(.*\/)(.*)')

    ol_basePath, ol_fileName = file_path_splitter.findall(order_logs)[0]
    rl_basePath, rl_fileName = file_path_splitter.findall(runtime_logs)[0]
    
    os.makedirs(ol_basePath, exist_ok=True)
    os.makedirs(rl_basePath, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    if not(exists(order_logs)):
        open(order_logs, 'w').close()

    if not(exists(runtime_logs)):
        open(runtime_logs, 'w').close()


def settings_reader():
    settings_file_data = {}

    with open('settings', 'r') as file:
        for line in file.readlines():

            if '=' in line and not('#' in line):
                key, data = line.split('=')

                if data != None:
                    data = data.replace('\n', '')

                if key == 'IS_TEST':
                    run_type = 'TEST' if data.upper() == 'TRUE' else 'REAL'
                    settings_file_data.update({'run_type':run_type})

                elif key == 'MARKET_TYPE':
                    settings_file_data.update({'market_type':data.upper()})

                elif key == 'PUBLIC_KEY':
                    settings_file_data.update({'public_key':data})

                elif key == 'PRIVATE_KEY':
                    settings_file_data.update({'private_key':data})

                elif key == 'TRADING_MARKETS':
                    settings_file_data.update({'trading_markets':data.split(',') if ',' in data else [data]})

                elif key == 'TRADER_INTERVAL':
                    settings_file_data.update({'trader_interval':data})

                elif key == 'TRADING_CURRENCY':
                    settings_file_data.update({'trading_currency':data})

                elif key == 'HOST_IP':
                    default_ip = '127.0.0.1'
                    t_ip = default_ip if data == '' else data
                    settings_file_data.update({'host_ip':t_ip})

                elif key == 'HOST_PORT':
                    default_port = 5000
                    t_port = default_port if data == '' else int(data)
                    settings_file_data.update({'host_port':t_port})

                elif key == 'MAX_CANDLES':
                    default_candles_range = 500
                    candle_range = default_candles_range if data == '' else int(data)
                    settings_file_data.update({'max_candles':candle_range})

                elif key == 'MAX_DEPTH':
                    default_depth_range = 50
                    depth_range = default_depth_range if data == '' else int(data)
                    settings_file_data.update({'max_depth':depth_range})

    return(settings_file_data)


def read_cache_file(file_id):

    cTime = time.time()
    file_path = '{0}{1}'.format(CACHE_DIR, CAHCE_FILES[file_id])
    file_data = None

    if exists(file_path):
        with open(file_path, 'r') as file:
            file_data = json.loads(file.read())
    else:
        return(False)

    if (cTime - file_data['lastUpdateTime']) > MAX_TIME[file_id]:
        return(False)
    else:
        return(file_data)


def save_cache_file(file_id, file_data):

    cTime = time.time()
    save_data = {'lastUpdateTime':cTime, 'data':file_data}
    file_path = '{0}{1}'.format(CACHE_DIR, CAHCE_FILES[file_id])

    with open(file_path, 'w') as file:
        file.write(json.dumps(save_data))
        file.close()

    return(True)

