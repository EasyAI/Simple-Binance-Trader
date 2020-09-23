#! /usr/bin/env python3
import os 
import logging
from core import botCore
from core import handler

cwd = os.getcwd()

RUNTIME_LOGS_PATH = '{0}/logs/runtimeLogs.log'.format(cwd)
ORDER_LOGS_PATH = '{0}/logs/order_log.log'.format(cwd)

handler.check_file_structure(ORDER_LOGS_PATH, RUNTIME_LOGS_PATH)

log_format = '%(asctime)s:%(name)s:%(message)s'

logging.basicConfig(
    format=log_format,
    level=logging.INFO)

logger = logging.getLogger()


#file_handler = logging.FileHandler(RUNTIME_LOGS_PATH)
#file_handler.setLevel(logging.INFO)
#file_handler.setFormatter(formatter)

#logger.addHandler(file_handler)


def main():
    settings = handler.settings_reader()

    botCore.start(settings, ORDER_LOGS_PATH)


if __name__ == '__main__':
    main()