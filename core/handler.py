import os
import re
import json
import time
from os.path import exists, basename

cwd = os.getcwd()

class cache_handler(object):

    def __init__(self, cache_dir, max_file_time=1800):
        self.cache_dir = cache_dir
        self.max_time = max_file_time

    def read_cache_file(self, file_name):
        cTime = int(str(time.time()).split('.')[0])
        file_path = file_name if '/' in file_name else '{0}{1}'.format(self.cache_dir, file_name)
        file_data = None

        if exists(file_path):
            with open(file_path, 'r') as file:
                file_content = file.read()
                if file_content != '':
                    file_data = json.loads(file_content)
        else:
            return(False)

        if self.max_time:
            if (cTime - file_data['lastUpdateTime']) > self.max_time[file_id]:
                return(False)

        return(file_data)


    def save_cache_file(self, file_data, file_name):
        cTime = int(str(time.time()).split('.')[0])
        save_data = {'lastUpdateTime':cTime, 'data':file_data}
        file_path = file_name if '/' in file_name else '{0}{1}'.format(self.cache_dir, file_name)

        with open(file_path, 'w') as file:
            file.write(json.dumps(save_data))
            file.close()

        return(True)


def check_file_structure(paths_to_check):
    file_path_splitter = re.compile(r'^(.*\/)(.*)')

    if type(paths_to_check) != list:
        paths_to_check = [paths_to_check]

    for path in paths_to_check:
        base_path, filename = file_path_splitter.findall(path)[0]
        os.makedirs(base_path, exist_ok=True)

        if not(exists(path)):
            open(path, 'w').close()


def settings_reader():
    settings_file_data = {}

    with open('settings', 'r') as file:
        for line in file.readlines():

            if '=' in line and not('#' in line):
                key, data = line.split('=')

                if data != None:
                    data = data.replace('\n', '')

                if key == 'IS_TEST':
                    data = 'TEST' if data.upper() == 'TRUE' else 'REAL'
                    key = 'run_type'

                elif key == 'MARKET_TYPE':
                    data = data.upper()

                elif key == 'TRADING_MARKETS':
                    data = data.split(',') if ',' in data else [data]

                elif key == 'HOST_IP':
                    default_ip = '127.0.0.1'
                    data = default_ip if data == '' else data

                elif key == 'HOST_PORT':
                    default_port = 5000
                    data = default_port if data == '' else int(data)

                elif key == 'MAX_CANDLES':
                    default_candles_range = 500
                    data = default_candles_range if data == '' else int(data)

                elif key == 'MAX_DEPTH':
                    default_depth_range = 50
                    data = default_depth_range if data == '' else int(data)

                settings_file_data.update({key.lower():data})

    return(settings_file_data)