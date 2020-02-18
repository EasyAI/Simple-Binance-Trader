#! /usr/bin/env python3

'''
trader

'''
import os
import sys
import time
import logging
import datetime
import threading
from . import restAPI
import conditions as con
import TradeIndicators as TI


## Minimum price rounding.
pRounding = 8

## Base commission fee with binance.
COMMISION_FEE = 0.00075


class Trader(object):

    def __init__(self, symbol, filters, restAPI, runType):
        '''
        Initilise the trader object and all of the atributes that are required for it to be run.
        '''

        ## Set the current restAPI.
        self.RESTapi = restAPI

        ## Run type for the bot being either real or test.
        self.botRunType = runType

        ## Holds update timers.
        self.lastUpdateTime = {
            'iu':0,     # interval update.
            'ou':0}     # order update.
        
        ## Holds the candles.
        self.candles = None
        
        ## Holds the trade indicators.
        self.normalIndicators = {}
        
        ## Holds runtime info of the trader.
        self.runtime = {
            'symbol':symbol,    # The market being traded.
            'token':symbol[:-3],# Current token of the market.
            'state':None,       # The traders state. [RUN, FORCE_STANDBY, STANDBY, STOP, COMPLETED_TRADE]
            'time':0}           # Last time an update was done.
        
        ## Holds current market information.
        self.currentMarket = {
            'lastPrice':None,      # Last price.
            'askPrice':None,       # Ask price.
            'bidPrice':None}       # Bid price.

        ## Force sell is set if a active trade is found on script reset.
        self.forceSell = False
        
        ## Holds information on current/past trades of the trader.
        self.TradesInformation = {
            'MAC':0,                            # 'MAC' this holds the Maximum Allowed Currency the bot can trade with.
            'currencyLeft':0,                   # 'currencyLeft' this holds the currency the bot has left to trade.
            'buyPrice':0,                       # 'buyPrice' this holds the buy price for the bot.
            'sellPrice':0,                      # 'sellPrice' this holds the sell price of the bot.
            'tokenBase':0,                      # 'tokenBase' this holds the base tokens bought.
            'canOrder':False,                   # 'canOrder' this will determin if the bot is allowed to place an order or not.
            'orderType':{'B':'wait', 'S':None}, # 'orderType' holds the current type of trade being carried out (B:[Wait/Signal/RSI] S:[Limit/Signal/Trail])
            'orderStatus':{'B':None, 'S':None}, # 'orderStatus' holds the status for the current order (B:[None/Placed/PF/Locked] S:[None/Placed/PF/Locked/PF_Sig])
            'updateOrder':False,                # 'updateOrder' this is used to determin if a placed order should be updated
            '#Trades':0,                        # '#Trades' this holds the number of FULL trades made by this market.
            'overall':0}                        # 'overall' this holds the overall outcomes for this markets trades.

        ## Holds the rules required for the market.
        self.marketRules = {
            'LOT_SIZE':filters['lotSize'],
            'TICK_SIZE':filters['tickSize'],
            'MINIMUM_NOTATION':filters['minNotional']}
        
        logging.debug('Initilized trader variables. [{0}]'.format(symbol))


    def start(self, MAC):
        '''
        Starts the trader.
        -> If recent trade, setup force sell.
        -> Start trader thread.
        '''
        self.runtime['state'] = 'SETUP'
        self.TradesInformation['MAC'] = MAC
        self.TradesInformation['currencyLeft'] = MAC

        symbol = self.runtime['symbol']

        if self.forceSell:
            checkCall = self.RESTapi.check_closed_orders('BUY', symbol)

            if checkCall['CALL']:
                self.TradesInformation['buyPrice'] = checkCall['data']['price']
                self._setup_sell()
            self.forceSell = False

        ## Start the main of the trader in a thread.
        traderThread = threading.Thread(target=self._main)
        traderThread.start()

        logging.info('Started trader. [{0}]'.format(symbol))


    def stop(self):
        ''' 
        Stop the trader. 
        -> Trader cleanup.
        '''
        symbol = self.runtime['symbol']
        self.runtime['state'] = 'STOP'
        self.RESTapi.cancel_open_orders('ALL', symbol)
        self.botRunType = None

        logging.info('Stopped trader. [{0}]'.format(symbol))


    def _main(self):
        '''
        Main body for the trader loop.
        -> Call update.
        -> Call order checker.
        -> Call trade condition checker.
        '''
        symbol = self.runtime['symbol']

        if self.botRunType == 'real':
            self.RESTapi.cancel_open_orders('ALL', symbol)

        while True:
            if self.candles != None and self.currentMarket['bidPrice'] != None:
                break
            time.sleep(1)

        while self.runtime['state'] != 'STOP':
            try:
                ## Call the update function for the trader.
                self._updater()

                tInfo = self.TradesInformation

                if not self.runtime['state'] in ['STANDBY', 'COMPLETED_TRADE', 'FORCE_STANDBY']:
                    ## Find out the status on a order that is placed.
                    if (tInfo['orderStatus']['B'] != None or tInfo['orderStatus']['S'] != None) or (self.botRunType == 'test'):
                        self._order_status_manager()

                    ## If the state is not on standby then check the trade conditions.
                    if self.runtime['state'] == 'RUN':
                        self._trade_manager()

            except Exception as error:
                logging.exception('Trader [{0}] got [{1}]'.format(symbol, error))
                print('Error was caught!')

            time.sleep(4)


    def _updater(self):
        '''
        This section is incharge of updating and getting data for indicators.
        -> Do timing for periodic events.
        -> Calculate and Re-calculate the Indicators.
        -> Do checks on the apis account and other periodic checks.
        '''
        symbol = self.runtime['symbol']
        tInfo = self.TradesInformation
        cMarket = self.currentMarket

        ## <----------------------------------| BOT TIMING MANAGEMENT |-----------------------------------> ##
        unixTime = time.time()

        ## Used to run peridotical updates (every 1 min).
        if self.lastUpdateTime['iu']+60 <= unixTime:
            self.lastUpdateTime['iu'] = unixTime

        ## <----------------------------------| INITIALIZE INDICATORS |-----------------------------------> ##
        candles = self.candles

        if 'MACD' in self.normalIndicators:
            MACD = self.normalIndicators['MACD'][:]

        ## [INDICATOR] ----->
        try:
            self.normalIndicators['MACD'] = TI.get_MACD(candles['close'], signal=14)
        except:
            self.normalIndicators['MACD'] = MACD[:]


        ## <----------------------------------| RUNTIME CHECKS |-----------------------------------> ##
        if self.runtime['state'] == 'FORCE_STANDBY':
            ## If force standy then force the trader to reset.
            self._setup_buy()
            self.runtime['state'] = 'STANDBY'

        if self.botRunType == 'real':
            ## Check the current order/trade.
            manager = self._balance_manager()

            if manager:
                side = 'BUY' if tInfo['orderType']['S'] == None else 'SELL'

                self._code_manager(manager['code'], side)

        ## Setup a time stamp of the last time the trader was updated.
        currenyTime = time.localtime()
        self.runtime['time'] = '{0}:{1}:{2}'.format(currenyTime[3], currenyTime[4], currenyTime[5])

        if self.runtime['state'] == 'SETUP':
            self.runtime['state'] = 'RUN'


    def _order_status_manager(self):
        '''
        This is the manager for all and any active orders.
        -> Check sell orders status.
        -> Check buy orders Status.
        '''
        symbol = self.runtime['symbol']
        tInfo = self.TradesInformation
        cMarket = self.currentMarket
        side = 'BUY' if tInfo['orderType']['S'] == None else 'SELL'
        tradeDone = False

        if self.botRunType == 'real':
            if tInfo['orderStatus']['B'] == 'Done' or tInfo['orderStatus']['S'] == 'Done':
                tradeDone = True

        elif self.botRunType == 'test':
            if tInfo['orderStatus']['B'] != None and side == 'BUY':
                if cMarket['lastPrice'] <= tInfo['buyPrice']:
                    tradeDone = True
            elif tInfo['orderStatus']['S'] != None and side == 'SELL':
                if cMarket['lastPrice'] >= tInfo['sellPrice']:
                    tradeDone = True

        if tradeDone:
            print('Finished trade')
            if side == 'BUY' and (tInfo['orderStatus']['B'] == 'Done' or self.botRunType == 'test'):
                ## Completed order on buy side.
                if self.botRunType == 'real':
                    token = self.runtime['token']
                    balance = self.RESTapi.get_balance(token)['free']
                elif self.botRunType == 'test':
                    balance = float('{0:.8f}'.format(tInfo['currencyLeft']/cMarket['lastPrice']))

                self.TradesInformation['tokenBase'] = balance

                self._setup_sell()
                logging.info('Completed buy order. [{0}]'.format(symbol))

            elif side == 'SELL' and (tInfo['orderStatus']['S'] == 'Done' or self.botRunType == 'test'):
                ## Completed order on sell side.
                fee = self.TradesInformation['MAC'] * COMMISION_FEE
                self.TradesInformation['overall'] += float('{0:.8f}'.format(((tInfo['sellPrice']-tInfo['buyPrice'])*tInfo['tokenBase'])-fee))
                self.TradesInformation['#Trades'] += 1

                self._setup_buy()
                logging.info('Completed sell order. [{0}]'.format(symbol))


    def _trade_manager(self):
        ''' 
        Here both the sell and buy conditions are managed by the trader.
        -> Manage sell conditions.
        -> Manage buy conditions.
        -> Place order on the market.
        '''
        symbol = self.runtime['symbol']
        cMarket = self.currentMarket
        tInfo = self.TradesInformation
        candles = self.candles
        ind = self.normalIndicators

        orderType = None
        updateOrder = tInfo['updateOrder']
        order = {'place':False}

        if tInfo['orderType']['S'] and tInfo['orderStatus']['S'] != 'Order_Lock':
            ## <----------------------------------| SELL CONDITION |-----------------------------------> ##
            logging.info('Checking for Sell condition. [{0}]'.format(symbol))

            conOrder = con.sell_conditions(ind, cMarket, tInfo, candles)

            if conOrder['place']:
                orderType = conOrder['tType']
                price = float('{0:.{1}f}'.format(conOrder['price'], pRounding))

                askPrice = cMarket['askPrice']

                if orderType == 'signal':
                    '''############### SIGNAL SELL ###############'''
                    if (price != tInfo['sellPrice'] and tInfo['sellPrice'] != askPrice) or updateOrder:
                        order = {'place':True, 'side':'SELL'}

                else:
                    logging.critical('The trade type [{0}] has not been configured'.format(conOrder['tType']))

            else:
                '''############### CANCEL BUY ORDER ###############'''
                if tInfo['orderType']['S'] == 'signal':
                    if self.botRunType == 'real':
                        self.RESTapi.cancel_open_orders('BUY', symbol)
                    self.TradesInformation['orderStatus']['S'] = None
                    self.TradesInformation['orderType']['S'] = 'wait'


        elif tInfo['orderType']['B'] and tInfo['orderStatus']['B'] != 'Order_Lock':
            ## <----------------------------------| BUY CONDITION |-----------------------------------> ##
            logging.info('Checking for Buy condition. [{0}]'.format(symbol))

            conOrder = con.buy_conditions(ind, cMarket, tInfo, candles)

            if conOrder['place']:
                orderType = conOrder['tType']
                price = float('{0:.{1}f}'.format(conOrder['price'], pRounding))

                bidPrice = cMarket['bidPrice']
                #print(price, bidPrice)

                if orderType == 'signal':
                    '''############### SIGNAL BUY ###############'''
                    if (price != tInfo['buyPrice'] and tInfo['buyPrice'] != bidPrice) or updateOrder:
                        order = {'place':True, 'side':'BUY'}

                else:
                    loggin.critical('The trade type [{0}] has not been configured'.format(conOrder['tType']))

            else:
                '''############### CANCEL BUY ORDER ###############'''
                if tInfo['orderType']['B'] == 'signal':
                    if self.botRunType == 'real':
                        self.RESTapi.cancel_open_orders('BUY', symbol)
                    self.TradesInformation['orderStatus']['B'] = None
                    self.TradesInformation['orderType']['B'] = 'wait'

        if updateOrder:
            self.TradesInformation['updateOrder'] = False

        ## <----------------------------------| ORDER MANAGER |-----------------------------------> ##
        if order['place']:
            print('{0} : [{1}]'.format(conOrder['description'], symbol))

            orderInfo = None

            if self.botRunType == 'real':
                ## Attempt to place an order on the market.
                orderInfo = self.RESTapi.order_placer(symbol,
                                                    self.marketRules, 
                                                    self.TradesInformation, 
                                                    order['side'], 
                                                    'LIMIT', 
                                                    price=price)

                logging.info('orderInfo: {0} [{1}]'.format(orderInfo, self.runtime['symbol']))

                if orderInfo:
                    code = orderInfo['code']
                else:
                    return

            elif self.botRunType == 'test':
                orderInfo = True
                code = 0
            
            ## Check the status of the order code.
            if orderInfo:
                self._code_manager(code, order['side'], price=price, orderType=orderType)


    def _balance_manager(self):
        '''
        The order manager is used when trying to place an order and will return data based on the status of the order that was placed.
        '''
        symbol = self.runtime['symbol']
        token = self.runtime['token']
        tInfo = self.TradesInformation
        mRules = self.marketRules
        lastPrice = self.currentMarket['lastPrice']
        message = None
        code = None

        if tInfo['orderType']['B'] != None and tInfo['orderType']['B'] != 'wait':
            if tInfo['orderStatus']['B'] in ['Placed', 'Order_Lock']:
                ## If the current order status for buy is anything but waiting.
                oOrder = self.RESTapi.check_open_orders(symbol)
                if not oOrder:
                    return

                if oOrder != 'Empty': 
                    ## Conditions for the order being placed and still being open.
                    if (tInfo['currencyLeft'] > mRules['MINIMUM_NOTATION']):
                        ## This checks if there is enought currency left to place a buy order.

                        balanceBTC = self.RESTapi.get_balance('BTC')
                        if not balanceBTC:
                            return

                        if (balanceBTC['free'] > tInfo['currencyLeft']):
                            ## If there is enough BTC to place new order and there is enough currency left to place an order it will be updated.
                            code, message = 100, 'Enough to re-place Buy. [{0}]'.format(symbol)
                        else:
                            ## If the current BTC balance is less than what is needed to place a new order the current order is locked.
                            code, message = 102, 'Lock Buy. [{0}]'.format(symbol)
                    else:
                        ## If the currency left is less than the minimum notation the order is locked.
                        code, message = 102, 'Lock Buy. [{0}]'.format(symbol)

                assetBalance = self.RESTapi.get_balance(token)
                if not assetBalance:
                    return

                if assetBalance:
                    if assetBalance['free']*lastPrice > mRules['MINIMUM_NOTATION']:
                        ## If the balance of the asset is over the minimum amount required and the order is empty the order is considered complete.
                        code, message = 200, 'Finished order buy. [{0}]'.format(symbol)
            else:
                self._setup_buy()

        if tInfo['orderType']['S'] != None:
            ## This deals with the Sell side for checking balances and trades.
            assetBalance = self.RESTapi.get_balance(token)
            if not assetBalance:
                return

            walletAssetValue = (assetBalance['locked']+assetBalance['free'])*lastPrice
            self.TradesInformation['currencyLeft'] = tInfo['MAC'] - (assetBalance['free']*lastPrice)

            if tInfo['orderStatus']['S'] == 'Placed':
                oOrder = self.RESTapi.check_open_orders(symbol)
                if not oOrder:
                    return

                if oOrder != 'Empty':
                    ## Conditions for the order being placed and still being open.
                    if (walletAssetValue > mRules['MINIMUM_NOTATION']):
                        ## If the current asset value is over the minimum required to place an order the bot will be allowed to place.
                        code, message = 100, 'Enough to re-place Sell. [{0}]'.format(symbol)
                    else:
                        ## If the current asset value is under the minimum required to place an order the bot will lock its sell order.
                        code, message = 102, 'Lock Sell. [{0}]'.format(symbol) 
                else:
                    if walletAssetValue < mRules['MINIMUM_NOTATION']:
                        ## If the wallet asset value is less than the minimum to place and order and also the open orders are empty the order is considered complete.
                        code, message = 200, 'Finished order Sell. [{0}]'.format(symbol)
                    else:
                        code, message = 101, 'Enough to place new Sell. [{0}]'.format(symbol)
            else:
                if (walletAssetValue > mRules['MINIMUM_NOTATION']):
                    code, message = 101, 'Enough to place new Sell. [{0}]'.format(symbol)

        if code:
            logging.info('Balance manager:{0}'.format({'code':code, 'msg':message}, symbol))

        return({'code':code, 'msg':message})


    def _code_manager(self, code, side=None, **kwargs):
        '''
        CODES:
        0 - Order have been placed.
        1 - Not enough to place an order.
        100 - Able to place either sell or buy order.
        101 - Order can be placed.
        102 - lock the current trade.
        200 - Order has been declared finished.
        '''
        if code == 0:
            ## Order has been placed.
            if side == 'BUY':
                self.TradesInformation['orderType']['B'] = kwargs['orderType']
                self.TradesInformation['orderStatus']['B'] = 'Placed'
                self.TradesInformation['buyPrice'] = kwargs['price']
            elif side == 'SELL':
                self.TradesInformation['orderType']['S'] = kwargs['orderType']
                self.TradesInformation['orderStatus']['S'] = 'Placed'
                self.TradesInformation['sellPrice'] = kwargs['price']

        elif code == 1:
            ## Not enough to place a order on the market.
            self.runtime['state'] = 'FORCE_STANDBY'

        elif code == 100:
            ## The bot is able to place a order on the market.
            pass

        elif code == 101:
            ## The bot is able to place a order on the market.
            if side == 'BUY':
                pass
            elif side == 'SELL':
                pass
            
            self.TradesInformation['updateOrder'] = True

        elif code == 102:
            ## There is not enough to place a new order so the order must be locked.
            if side == 'BUY':
                self.TradesInformation['orderStatus']['B'] = 'Order_Lock'
            elif side == 'SELL':
                self.TradesInformation['orderStatus']['S'] = 'Order_Lock'

        elif code == 200:
            ## order has been declared as finished.
            if side == 'BUY':
                self.TradesInformation['orderStatus']['B'] = 'Done'
            elif side == 'SELL':
                self.TradesInformation['orderStatus']['S'] = 'Done'


    def _setup_sell(self):
        ''' Used to setup the trader for selling after a buy has been completed. '''
        self.TradesInformation['orderStatus']['B']  = None
        self.TradesInformation['currencyLeft']      = 0

        self.TradesInformation['orderType']['B'] = None
        self.TradesInformation['orderType']['S'] = 'wait'
        self.TradesInformation['updateOrder'] = True


    def _setup_buy(self):
        ''' Used to setup the trader for buying after a sell has been completed. '''
        self.TradesInformation['orderStatus']['S']  = None
        self.TradesInformation['tokensHolding']     = 0
        self.TradesInformation['sellPrice']         = 0
        self.TradesInformation['buyPrice']          = 0
        self.TradesInformation['currencyLeft']      = self.TradesInformation['MAC']

        self.TradesInformation['orderType']['B'] = 'wait'
        self.TradesInformation['orderType']['S'] = None


    def get_trader_data(self):
        ''' Get bundled data about the current trader. '''
        botData = {'runtime': self.runtime,
                'currentMarket': self.currentMarket,
                'tradesInfo': self.TradesInformation,
                'indicators': self.normalIndicators}

        return(botData)


    def give_trader_data(self, data):
        ''' This is used to give data to the trader (passed from the socket). '''

        try:
            lastLPrice = self.currentMarket['lastPrice']

            self.currentMarket['lastPrice'] = float(data['candles']['close'][0])
            
        except Exception as e:
            self.currentMarket['lastPrice'] = lastLPrice
            return
        
        if data['bid'] != None:
            self.currentMarket['bidPrice'] = float(data['bid'])
            self.currentMarket['askPrice'] = float(data['ask'])

        self.candles = data['candles']