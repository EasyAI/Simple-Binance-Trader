#! /usr/bin/env python3

import time
import sys
import logging
import threading
from . import restAPI, socketAPI, trader


class BotCore():

    def __init__(self, publicKey, privateKey):
        ''' Init the core. '''
        if publicKey == None or privateKey == None:
            raise ValueError('No API keys provided but are required.')
            return

        self.publicKey = publicKey
        self.privateKey = privateKey
        self.coreState = 'Ready'

        self.traderRunType = 'test'
        self.baseCandleLimit = 200

        self.wsReady = False
        self.mainInterval = '5m'
        self.traderObjects = None

        ## Market trader info, holds the market and also the curreny amount for that market.
        ## Format should be {'market':BTC-LTC, 'amount':0.001}
        self.mtInfo = {}


    def start(self):
        ''' Start everything. '''
        self.coreState = 'Setting Up'

        ## This creates the bot bojects.
        market = ("{0}{1}".format(self.mtInfo['market'][4:], self.mtInfo['market'][:3])).lower()

        self.traderObject = trader.Trader(self.publicKey, 
                                        self.privateKey, 
                                        self.mtInfo['market'].upper(), 
                                        float(self.mtInfo['amount']))
        ##-------------------->

        ## This creates the socket query url and object.
        queryURL = '{0}@kline_{1}/{0}@depth20/'.format(market, self.mainInterval)
        self.binanceSocket = socketAPI.BinanceSOCK(queryURL)
        ##-------------------->

        ## This starts the socket manager thread.
        socketThread = threading.Thread(target=self._socket_manager)
        socketThread.start()
        
        while True:
            if self.wsReady:
                break
        ##-------------------->

        ## This creates a thread for each bot trader object.
        self.traderObject.start(self.traderRunType)

        while True:
            if self.traderObject.runtime['state'] == 'Setup':
                break
        ##-------------------->

        self.coreState = 'Running'


    def stop(self):
        ''' stop everything '''
        if self.binanceSocket.socketRunning:
            self.binanceSocket.ws.close()

        self.traderObject.stop()
        self.coreState = 'Stopped'


    def get_trader_data(self):
        ''' Get data from the trader '''
        return(self.traderObject.get_trader_data())


    def _socket_manager(self):
        '''
        This is the manager thread for the web socket.
        '''
        cElements = ['open', 'high', 'low', 'close', 'volume']
        market = self.mtInfo['market']
        klineAPICaller = restAPI.BinanceREST()
        self.binanceSocket.start()

        liveData = {'depth':{'bids':[], 'asks':[]}, 'candles':None}

        while self.coreState != 'Stopped':

            update = False
            dataStream = self.binanceSocket.get_buffer()

            ## This is used to store the data for bids.
            liveData['depth']['bids'] = dataStream['depth']['bids']
            liveData['depth']['asks'] = dataStream['depth']['asks']

            if liveData['candles'] != None and dataStream['candle'] != {}:
                ## This is used to update only the most recent data.
                if dataStream['candle']['time'] != liveData['candles']['time'][0]:
                    update = True
                else:
                    for element in cElements:
                        liveData['candles'][element][0] = dataStream['candle'][element]
            else:
                update = True

            if update:
                ## This is used to get a new set of all the new klines.
                liveData['candles'] = klineAPICaller.get_klines(interval=self.mainInterval, market=market.upper(), limit=self.baseCandleLimit)
                logging.info('New candles for [{0}]'.format(market))

            if not self.wsReady:
                isready = True
                if liveData['depth']['bids'] == [] or liveData['candles'] == None:
                    isready = False

            if isready:
                self.traderObject.give_trader_data(liveData)

            if isready and not self.wsReady:
                self.wsReady = True
                logging.info('Websocket is ready.')

            time.sleep(1)