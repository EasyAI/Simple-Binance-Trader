
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
from . import rest_api, socketAPI, trader

## Base historic candle reach.
BASE_CANDLE_LIMIT = 200


class BotCore():


    def __init__(self, run_type, MAC, trading_markets, candle_Interval, publicKey, privateKey):
        '''  
         #
         #
         #
         #
         #
        '''
        logging.debug('Attempting to initilize bot core.')

        self.rest_api = rest_api.BinanceREST(publicKey, privateKey)
        self.run_type = run_type
        self.wsReady = False
        self.initAccCheck = False

        ## Live trader data.
        self.maxLiveTraders = 0
        self.liveTraders = 0
        self.passiveTraders = 0

        ## Trader settings.
        self.MAC = MAC                          # MaxAllowedCurreny.
        self.candle_Interval = candle_Interval  # Interval.
        
        ## Dollar to BTC rate
        self.dToBTC = float(self.rest_api.get_market_summary('BTCUSDT')['lastPrice'])

        self.markets_info = []
        self.trading_markets = trading_markets
        self.updateRun = False
        self.coreState = 'READY'


    def start(self):
        '''
        
        '''
        logging.debug('Starting the bot core.')

        self.coreState = 'SETUP'

        for market in self.rest_api.get_market_rules():
            fmtMarket = '{0}-{1}'.format(market['quoteAsset'], market['baseAsset'])

            ## As currently only BTC markets can be traded it will only allow BTC markets.
            if market['quoteAsset'] != 'BTC':
                continue

            ## If the current base asset is on the blacklist then dont add it.
            if not fmtMarket in self.trading_markets:
                continue

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

            self.markets_info.append({
                'quote':market['quoteAsset'],
                'token':market['baseAsset'],
                'symbol':'{0}{1}'.format(market['baseAsset'], market['quoteAsset']),
                'filters':{'lotSize':lS, 'tickSize':tS, 'minNotional':mN},
                'object':trader.BaseTrader(
                                    '{0}{1}'.format(market['baseAsset'], market['quoteAsset']),
                                    {'lotSize':lS, 'tickSize':tS, 'minNotional':mN},
                                    self.rest_api,
                                    self.run_type)})

        ## This creates the socket query url and object.
        self.binanceSocket = socketAPI.BinanceSOCK()

        for trader_ in self.markets_info:
            trader_['object'].start(self.MAC)

        socket_Thread = threading.Thread(target=self._socket_manager)
        socket_Thread.start()

        painter_Thread = threading.Thread(target=self._feed_updater)
        painter_Thread.start()

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

        for index, market in enumerate(self.markets_info):
            if self.markets_info[index]['object']:
                tObj = self.markets_info[index]['object']
                symbol = self.markets_info[index]['symbol']

                rData.update({symbol: {'status':market['status'], 'object':tObj.get_trader_data()}})

        return(rData)


    def _socket_manager(self):
        """
        This is the manager thread for the web socket.
        """
        cElements = ['open', 'high', 'low', 'close', 'volume']
        liveData = {}
        queryURL = ''

        lSymbols = ['{0}{1}'.format(symbol[4:], symbol[:3]).lower() for symbol in self.trading_markets]

        for lSymbol in lSymbols:
            queryURL += '{0}@kline_1m/{0}@depth5/'.format(lSymbol)

        print(queryURL)

        self.binanceSocket.start(lSymbols, queryURL)

        while self.coreState != 'STOP':
            for market in self.markets_info:
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
                        print(self.binanceSocket.get_buffer())
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

                            if 'h' in self.candle_Interval:
                                stringNum = '%H'
                            else:
                                stringNum = '%M'

                            lastUpdateTimeSegment = time.strftime(stringNum, time.localtime(liveData[symbol]['candles']['time'][0]/1000))
                            currentTimeSegment = time.strftime(stringNum, time.localtime(dataStream['candle']['time']/1000))

                            if lastUpdateTimeSegment != currentTimeSegment and int(currentTimeSegment) % int(self.candle_Interval[:-1]) == 0:
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
                        liveData[symbol]['candles'] = self.rest_api.get_klines(self.candle_Interval, symbol, limit=BASE_CANDLE_LIMIT)
                        logging.debug('New candles for [{0}]'.format(symbol))

                    ## Give the trader candle and orderbook data.
                    market['object'].give_trader_data(liveData[symbol])

                    if update:
                        time.sleep(6)


    def _feed_updater(self):

        while self.coreState != 'STOP':
            total_trader = 0
            total_ROI = 0

            for index, market in enumerate(self.markets_info):
                if market['object']:
                    trader_information = market['object'].trade_information

                    total_trader += trader_information['#Trades']
                    total_ROI += trader_information['overall']

            detailString = '|#======#| Calls: {0} | P:{1},L:{2}/{3} | Total Trades: {4} | Overall: {5:.8f} |#======#|'.format(
                                                                                                    self.rest_api.callCounter, 
                                                                                                    self.passiveTraders,
                                                                                                    self.liveTraders, 
                                                                                                    self.maxLiveTraders,
                                                                                                    total_trader,
                                                                                                    total_ROI)
            print('\n|#{0}#|'.format('='*(len(detailString)-4)))
            print(detailString)
            print('|#{0}#|'.format('='*(len(detailString)-4)))

            for index, market in enumerate(self.markets_info):
                trader_object = market['object']

                # Check to make sure that the trader object has been initilized.
                if not trader_object:
                    continue

                # Check to make sure that indicators have loaded for the trader.
                if trader_object.indicators == {}:
                    continue

                _paint_trader_details(trader_object)

            time.sleep(30)


def _paint_trader_details(trader_object):

    rT = trader_object.runtime
    cM = trader_object.prices
    tI = trader_object.trade_information
    ind = trader_object.indicators

    print('[{0}] market: {1} | state: {2} | overall: {3:.8f} | last update: {4} | trades {5}'.format(
        '@',
        trader_object.symbol,
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
    print()

