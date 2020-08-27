#! /usr/bin/env python3
import os 
import logging
from core import botCore
from core import handler

cwd = os.getcwd()

RUNTIME_LOGS_PATH = '{0}/logs/runtimeLogs.log'.format(cwd)
ORDER_LOGS_PATH = '{0}/logs/order_log.log'.format(cwd)

handler.check_file_structure(ORDER_LOGS_PATH, RUNTIME_LOGS_PATH)

logger = logging.getLogger()

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

file_handler = logging.FileHandler(RUNTIME_LOGS_PATH)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)


def main():
    settings = handler.settings_reader()

    botCore.start(
        settings['traderCurrency'], 
        settings['markets'], 
        settings['mainInterval'], 
        settings['publicKey'], 
        settings['privateKey'], 
        settings['host_ip'],
        settings['host_port'],
        ORDER_LOGS_PATH)
    

if __name__ == '__main__':
    main()