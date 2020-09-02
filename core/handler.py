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

            if '=' in line:
                key, data = line.split('=')

                if data != None:
                    data = data.replace('\n', '')

                if key == 'runType':
                    settings_file_data.update({'runType':data.upper()})

                if key == 'publicKey':
                    settings_file_data.update({'publicKey':data})

                elif key == 'privateKey':
                    settings_file_data.update({'privateKey':data})

                elif key == 'markets':
                    settings_file_data.update({'markets':data.split(',') if ',' in data else [data]})

                elif key == 'mainInterval':
                    settings_file_data.update({'mainInterval':data})

                elif key == 'traderCurrency':
                    settings_file_data.update({'traderCurrency':data})

                elif key == 'host_ip':
                    default_ip = '127.0.0.1'
                    t_ip = default_ip if data == '' else data
                    settings_file_data.update({'host_ip':t_ip})

                elif key == 'host_port':
                    default_port = 5000
                    t_port = default_port if data == '' else int(data)
                    settings_file_data.update({'host_port':t_port})

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

