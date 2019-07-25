#! /usr/bin/env python3

import os
import sys
import time
import json
import hashlib
import logging
import threading
from core import botCore

logging.basicConfig(level=logging.WARNING)

## Config File Path.
settingPath = "settings.json"
##-------------------->

## Runtime management varaiables.
bot_core = None
##-------------------->


def load_core():
    global bot_core

    ## load the data from the settings file.
    try:
        settingData = json.load(open(settingPath, 'r'))
        logging.info('Loaded the settings data from file.')
    except:
        ## set and error for the missing api key file.
        logging.error('NO SETTINGS DATA')
        return

    ## Create the bot_core object.
    bot_core = botCore.BotCore(settingData['keys']['public'], settingData['keys']['private'])
    logging.info('Created bot core object.')

    ## start the core 
    start_core(settingData)

    ## Create the thread that send interval updates to the web UI.
    updaterThread = threading.Thread(target=screen_updater)
    updaterThread.start()
    logging.info('Created updater thread.')


def start_core(settingData):
    runType = 'test'

    if bot_core.coreState != 'INVALID API KEYS':

        ## Setup the trading variables.
        bot_core.mtInfo = {'market':settingData['market'], 'amount':settingData['amount']}
        bot_core.mainInterval = settingData['interval']

        ## Set real or test trading.
        if runType == 'test':
            logging.warning('Starting in TEST mode.')
            bot_core.traderRunType = 'test'
        else:
            logging.warning('Starting in REAL mode.')
            bot_core.traderRunType = 'real'

        ## Start the core.
        bot_core.start()
        logging.info('Started bot core.')
        return

    logging.error('Unable to start collecting.')


def screen_updater():
    '''
    This is used to print to the screen.
    '''
    while True:
        if bot_core.coreState == 'Running':

            tObj = bot_core.get_trader_data()

            rT = tObj['runtime']
            cM = tObj['currentMarket']
            tI = tObj['tradesInfo']
            marketInfoString = ''

            marketInfoString += 'Market: {0} | state: {1} | last update: {2} | trades: {3} | outcome: {4:8f}\n'.format(rT['market'], 
                                                                                            rT['state'], 
                                                                                            rT['time'],
                                                                                            tI['#Trades'],
                                                                                            tI['overall'])

            marketInfoString += 'last price: {0:8f} | bid price: {1:8f} | ask price: {2:8f}\n'.format(cM['lastPrice'],
                                                                                            cM['askPrice'],
                                                                                            cM['bidPrice'])

            if tI['orderType']['S'] == None:
                fmtTypeStr = 'buy type: {0}'.format(tI['orderType']['B'])
                orderStatus = tI['orderStatus']['B']
                side = 'buy'
            else:
                fmtTypeStr =  'sell type: {0}'.format(tI['orderType']['S'])
                orderStatus = tI['orderStatus']['S']
                side = 'sell'

            marketInfoString += 'trade state: {0} | buy price: {1:8f} | sell price: {2:8f} | {3} | order status: {4}\n\n'.format(side,
                                                                                                                    tI['buyPrice'],
                                                                                                                    tI['sellPrice'],
                                                                                                                    fmtTypeStr,
                                                                                                                    orderStatus)
            print(marketInfoString)

        time.sleep(10)


def make_setting_file():
    '''
    make a new setting file.
    '''
    data = {
    'market':'BTC-LTC',
    'amount':0.001,
    'interval':'5m',
    'test':True,
    'keys':{'public':'', 'private':''}}

    settingFile = open(settingPath, 'w')
    settingFile.write(json.dumps(data))
    settingFile.close()


if __name__ == '__main__':

    if os.path.isfile(settingPath):
        load_core()
    else:
        make_setting_file()
    