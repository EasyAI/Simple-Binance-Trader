#! /usr/bin/env python3

'''
run

'''
import os
import sys
import time
import json
import hashlib
import logging
import threading
from core import botCore

## Config File Path.
cwd = os.getcwd()
settings = ("{0}/settings".format(cwd))
##-------------------->


## Setting up the logger.
logger = logging.getLogger()

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

file_handler = logging.FileHandler('runtimeLogs.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

##

## Runtime management varaiables.
updaterThreadActive = False
coreManThreadActive = False
bot_core = None
##-------------------->


with open('settings', 'r') as file:

    for line in file.readlines():
        key, data = line.split('=')

        if data != None:
            data = data.replace('\n', '')

        if key == 'publicKey':
            ## API public key.
            publicKey = data

        elif key == 'markets':
            ## API private key.

            data = data.replace(' ', '')

            if ',' in data:
                data = data.split(',')
            else:
                data = [data]

            markets_trading = data

        elif key == 'privateKey':
            ## API private key.
            privateKey = data

        elif key == 'runType':
            ## The type of run (real or not).
            runType = data.upper()

            if data.upper() != 'REAL':
                publicKey = None
                privateKey = None

        elif key == 'mainInterval':
            ## Main interval per market.
            mainInterval = data

        elif key == 'traderCurrency':
            ## Maxcurreny per trader
            MAC = float(data)

        elif key == 'debugLevel':
            ## Set the debug level during runtime.
            if data == 'warning':
                logger.setLevel(logging.WARNING)
            if data == 'debug':
                logger.setLevel(logging.DEBUG)
            else:
                logger.setLevel(logging.INFO)


def main():
    '''
    This is where all the data that will be used during runtime is collected.
    -> Setup the botcore.
    -> Setup the terminal feed thread.
    -> Start the botcore.
    '''
    global bot_core

    print('Starting in {0} mode.'.format(runType.upper()))
    
    ## <----------------------------------| RUNTIME CHECKS |-----------------------------------> ##
    bot_core = botCore.BotCore(runType, MAC, markets_trading, mainInterval, publicKey, privateKey)
    logging.info('Created bot core object.')

    ## <----------------------------------| RUNTIME CHECKS |-----------------------------------> ##
    if bot_core != None:
        bot_core.start()
        logging.info('Started bot core.')
        return

    logging.error('Unable to start collecting.')


if __name__ == '__main__':
    main()