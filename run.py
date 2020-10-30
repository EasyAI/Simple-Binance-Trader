#! /usr/bin/env python3
import os 
import sys
import logging
from core import handler
from core import botCore

## 
cwd = os.getcwd()
CACHE_DIR = '{0}/cache/'.format(cwd)
CAHCE_FILES = ['markets.json', 'traders.json']
LOGS_DIR = '{0}/logs/'.format(cwd)
handler.check_file_structure(['{0}{1}'.format(CACHE_DIR, name) for name in CAHCE_FILES])
handler.check_file_structure(LOGS_DIR)

cache_handler = handler.cache_handler(CACHE_DIR, None)

##
log_format = '%(asctime)s:%(name)s:%(message)s'
logging.basicConfig(
    format=log_format,
    level=logging.INFO)
logger = logging.getLogger()

def main():
    settings = handler.settings_reader()
    botCore.start(settings, LOGS_DIR, cache_handler)

if __name__ == '__main__':

    if len(sys.argv) > 1:
        if sys.argv[1] == 'pullCandles':
            botCore.pull_candles(cache_handler)
    else:
        main()