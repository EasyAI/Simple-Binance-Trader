
#! /usr/bin/env python3

'''
Botcore

'''
import sys
import time
import logging
import threading
import conditions as con
from decimal import Decimal
from . import restAPI, socketAPI, trader

## Base historic candle reach.
BASE_CANDLE_LIMIT = 200


class BotCore():


    def __init__(self, runType, MAC, mainInterval, markets_trading, publicKey, privateKey):
        '''  
         #
         #
         #
         #
         #
        '''
        logging.debug('Attempting to initilize bot core.')

        self.RESTapi = restAPI.BinanceREST(publicKey, privateKey)
        self.traderRunType = runType
        self.wsReady = False
        self.initAccCheck = False

        ## Live trader data.
        self.maxLiveTraders = 0
        self.liveTraders = 0
        self.passiveTraders = 0

        ## Trader settings.
        self.MAC = MAC                   ## MaxAllowedCurreny.
        self.mainInterval = mainInterval ## Interval.
    
        self.markets_trading = markets_trading        
        self.marketsInfo = []
        self.coreState = 'READY'


    def start(self):
        '''
        
        '''
        logging.debug('Starting the bot core.')

        self.coreState = 'SETUP'

        for market in self.RESTapi.get_market_rules():
            fmtMarket = '{0}-{1}'.format(market['quoteAsset'], market['baseAsset'])
            if market['quoteAsset'] == 'BTC' and fmtMarket in self.markets_trading:

                filters = market['filters']

                ## This is used to setup min quantity
                if float(filters[2]['minQty']) < 1.0:
                    minQuantBase = (Decimal(filters[2]['minQty'])).as_tuple()
                    lS = abs(int(len(minQuantBase.digits)+minQuantBase.exponent))+1
                else: lS = 0

                ## This is used to set up the price precision for the market.
                tickSizeBase = (Decimal(filters[0]['tickSize'])).as_tuple()
                tS = abs(int(len(tickSizeBase.digits)+tickSizeBase.exponent))+1

                ## This is used to get the markets minimal notation.
                mN = float(filters[3]['minNotional'])

                symbol = '{0}{1}'.format(market['baseAsset'], market['quoteAsset'])

                self.marketsInfo.append({
                    'quote':market['quoteAsset'],
                    'token':market['baseAsset'],
                    'symbol':symbol,
                    'overall':None,
                    'status':None,
                    'object':trader.Trader(
                                        symbol,
                                        {'lotSize':lS, 'tickSize':tS, 'minNotional':mN},
                                        self.RESTapi,
                                        self.traderRunType)})

        ## This creates the socket query url and object.
        self.binanceSocket = socketAPI.BinanceSOCK()

        for trader_ in self.marketsInfo:
            trader_['object'].start(self.MAC)

        socketThread = threading.Thread(target=self._socket_manager)
        socketThread.start()

        self.coreState = 'RUN'


    def stop(self):
        ''' '''
        if self.binanceSocket.socketRunning:
            self.binanceSocket.ws.close()

        for market in self.traderObjects:
            self.traderObjects[market].stop()

        self.coreState = 'STOP'


    def get_trader_data(self):
        '''  '''
        rData = {}

        for index, market in enumerate(self.marketsInfo):
            if self.marketsInfo[index]['object']:
                tObj = self.marketsInfo[index]['object']
                symbol = self.marketsInfo[index]['symbol']

                rData.update({symbol: {'status':market['status'], 'object':tObj.get_trader_data()}})

        return(rData)


    def _socket_manager(self):
        """
        This is the manager thread for the web socket.
        """
        cElements = ['open', 'high', 'low', 'close', 'volume']
        liveData = {}
        queryURL = ''

        lSymbols = ['{0}{1}'.format(symbol[4:], symbol[:3]).lower() for symbol in self.markets_trading]

        for lSymbol in lSymbols:
            queryURL += '{0}@kline_1m/{0}@depth5/'.format(lSymbol)

        self.binanceSocket.start(lSymbols, queryURL)

        while self.coreState != 'STOP':
            for market in self.marketsInfo:
                symbol = market['symbol']

                if self.binanceSocket.socketRunning:
                    update = False

                    ## Add the symbol to the live data buffer.
                    if not (symbol in liveData):
                        liveData.update({symbol:{'bid':None, 'ask':None, 'candles':None}})

                    ## Get data from the socket buffer.
                    try:
                        dataStream = self.binanceSocket.get_buffer()[symbol.lower()]
                    except Exception as e:
                        print(e)
                        dataStream = None
                        update = True

                    if dataStream != None:
                        ## Get orderbook data from the socket or set it to None.
                        try:
                            liveData[symbol]['ask'] = dataStream['depth']['asks'][0][0]
                            liveData[symbol]['bid'] = dataStream['depth']['bids'][0][0]
                        except Exception as e:
                            logging.warning('{0} --- {1}'.format(e, symbol))
                            liveData[symbol]['ask'] = None
                            liveData[symbol]['bid'] = None

                    if not update:
                        ## Get new candle data (update current candle | get new set of candles)
                        if liveData[symbol]['candles'] != None and dataStream['candle'] != {}:

                            if 'h' in self.mainInterval:
                                stringNum = '%H'
                            else:
                                stringNum = '%M'

                            lastUpdateTimeSegment = time.strftime(stringNum, time.localtime(liveData[symbol]['candles']['time'][0]/1000))
                            currentTimeSegment = time.strftime(stringNum, time.localtime(dataStream['candle']['time']/1000))

                            if lastUpdateTimeSegment != currentTimeSegment and int(currentTimeSegment) % int(self.mainInterval[:-1]) == 0:
                                ## Get a new set of candles.
                                print('update')
                                update = True
                            else:
                                ## Udate the current candle.
                                for element in cElements:
                                    liveData[symbol]['candles'][element][0] = dataStream['candle'][element]
                        else:
                            update = True

                    if update:
                        time.sleep(1)
                        ## Get a new set of candles.
                        liveData[symbol]['candles'] = self.RESTapi.get_klines(self.mainInterval, symbol, limit=BASE_CANDLE_LIMIT)
                        logging.debug('New candles for [{0}]'.format(symbol))

                    if market['object'] != None:
                        ## Give the trader candle and orderbook data.
                        market['object'].give_trader_data(liveData[symbol])

                    if update:
                        time.sleep(6)