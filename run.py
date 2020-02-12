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
logger.setLevel(logging.INFO)

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

            data.replace(' ', '')

            if ',' in data:
                 data.split(',')
            else:
                data = [data]

            markets_trading = data

        elif key == 'privateKey':
            ## API private key.
            privateKey = data

        elif key == 'runType':
            ## The type of run (real or not).
            runType = data

            if data != 'real':
                publicKey = None
                privateKey = None

        elif key == 'mainInterval':
            ## Main interval per market.
            mainInterval = data

        elif key == 'traderCurrency':
            ## Maxcurreny per trader
            MAC = float(data)


def main():
    '''
    This is where all the data that will be used during runtime is collected.
    -> Setup the botcore.
    -> Setup the terminal feed thread.
    -> Start the botcore.
    '''
    global bot_core
    logging.info('start.')

    print('Starting in {0} mode.'.format(runType.upper()))
    
    ## <----------------------------------| RUNTIME CHECKS |-----------------------------------> ##
    bot_core = botCore.BotCore(runType, MAC, mainInterval, markets_trading, publicKey, privateKey)
    logging.info('Created bot core object.')

    ## <----------------------------------| RUNTIME CHECKS |-----------------------------------> ##
    ## Create the thread that send interval updates to the web UI.
    updaterThread = threading.Thread(target=feed_updater)
    updaterThread.start()

    logging.info('Created updater thread.')

    ## <----------------------------------| RUNTIME CHECKS |-----------------------------------> ##
    if bot_core != None:
        bot_core.start()
        logging.info('Started bot core.')
        return

    logging.error('Unable to start collecting.')


def feed_updater():

    while True:
        totalTrades = 0
        totalOutcomes = 0
        traders = bot_core.get_trader_data()

        if traders != {}:
            for market in traders:
                if traders[market]['object']:
                    tI = traders[market]['object']['tradesInfo']

                    totalTrades += tI['#Trades']
                    totalOutcomes += tI['overall']

            detailString = '|#======#| Calls: {0} | P:{1},L:{2}/{3} | Total Trades: {4} | Overall: {5:.8f} |#======#|'.format(
                                                                                                    bot_core.RESTapi.callCounter, 
                                                                                                    bot_core.passiveTraders,
                                                                                                    bot_core.liveTraders, 
                                                                                                    bot_core.maxLiveTraders,
                                                                                                    totalTrades,
                                                                                                    totalOutcomes)
            print('\n|#{0}#|'.format('='*(len(detailString)-4)))
            print(detailString)
            print('|#{0}#|'.format('='*(len(detailString)-4)))

            paint_scrn(traders)

        time.sleep(20)


def paint_scrn(traderData):

    for market in traderData:

        tObj = traderData[market]['object']

        rT = tObj['runtime']
        cM = tObj['currentMarket']
        tI = tObj['tradesInfo']

        print('market: {0} | state: {1} | overall: {2:.8f} | last update: {3} | trades {4}'.format(
            rT['symbol'],
            rT['state'],
            tI['overall'],
            rT['time'],
            tI['#Trades']))
        
        if tI['orderType']['S'] == None:
            print('BUY| type: {0} | status: {1} | Bprice {2:.8f} | Sprice {3:.8f} | last: {4:.8f}'.format(
                tI['orderType']['B'],
                tI['orderStatus']['B'],
                tI['buyPrice'],
                tI['sellPrice'],
                cM['lastPrice']))
        else:
            print('SELL| type: {0} | status: {1} | Bprice {2:.8f} | Sprice {3:.8f} | last: {4:.8f}'.format(
                tI['orderType']['S'],
                tI['orderStatus']['S'],
                tI['buyPrice'],
                tI['sellPrice'],
                cM['lastPrice']))


if __name__ == '__main__':
    main()