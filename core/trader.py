#! /usr/bin/env python3

import os
import sys
import time
import logging
import datetime
import threading
from . import restAPI
import conditions as con
from decimal import Decimal
import TradeIndicators as TI


## Minimum price rounding.
pRounding = 8

## Base commission fee with binance.
COMMISION_FEE = 0.00075


class Trader(object):

    def __init__(self, publicKey, secretKey, market, maxACurrency):
        ## <------------------------| INITIAL VARIABLES |--------------------------> ##
        self.RESTapi = restAPI.BinanceREST(market, publicKey, secretKey)
        logging.debug('Initilized REST api. [{0}]'.format(market))

        ## <------------------------| GET MARKET VARIABLES |----------------------> ##
        ## This is used to lead the filters for a specific market.
        filters = self.RESTapi.get_market_rules()

        ## This sets up the LOT_SIZE for the market.
        if float(filters[2]['minQty']) < 1.0:
            minQuantBase = (Decimal(filters[2]['minQty'])).as_tuple()
            LOT_SIZE = abs(int(len(minQuantBase.digits)+minQuantBase.exponent))+1
        else: LOT_SIZE = 0

        ## This is used to set up the price precision for the market.
        tickSizeBase = (Decimal(filters[0]['tickSize'])).as_tuple()
        TICK_SIZE = abs(int(len(tickSizeBase.digits)+tickSizeBase.exponent))+1

        ## This is used to get the markets minimal notation.
        MINIMUM_NOTATION = float(filters[3]['minNotional'])
        logging.debug('Setup market filters. [{0}]'.format(market))

        ## <------------------------| MAIN TRADER VARIABLES |-------------------------> ##
        ## Holds update timers.
        self.lastUpdateTime = {
            'iu':0,     # interval update.
            'ou':0}     # order update.
        
        ## Holds the candles.
        self.candles = []
        
        ## Holds the trade indicators.
        self.normalIndicators = {}
        
        ## Holds runtime info of the trader.
        self.runtime = {
            'market':market,    # The market being traded.
            'state':'Setup',    # The traders state.
            'time':0}           # Last time an update was done.
        
        ## Holds current market information.
        self.currentMarket = {
            'lastPrice':0,      # Last price.
            'askPrice':0,       # Ask price.
            'bidPrice':0}       # Bid price.
        
        ## Holds information on current/past trades of the trader.
        self.TradesInformation = {
            'MAC':maxACurrency,                 # 'MAC' this holds the Maximum Allowed Currency the bot can trade with.
            'currencyLeft':maxACurrency,        # 'currencyLeft' this holds the currency the bot has left to trade.
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
            'LOT_SIZE':LOT_SIZE,
            'TICK_SIZE':TICK_SIZE,
            'MINIMUM_NOTATION':MINIMUM_NOTATION}
        logging.debug('Initilized trader variables. [{0}]'.format(market))


    def start(self, runType):
        ''' Starts the trader.'''
        self.botRunType = runType

        ## setup main in a thread.
        thread = threading.Thread(target=self._main)
        thread.start()

        logging.info('Started trader. [{0}]'.format(self.runtime['market']))


    def stop(self):
        ''' Stop the script. '''
        self.runtime['state'] = 'Stopped'
        self.RESTapi.cancel_open_orders('ALL')

        logging.info('Stopped trader. [{0}]'.format(self.runtime['market']))


    def _main(self):
        '''
        Main body for the trader loop.
        -> Update.
        -> order checking.
        -> trade condition checking.
        '''
        if self.botRunType == 'real':
            self.RESTapi.cancel_open_orders('ALL')

        while self.runtime['state'] != 'Stopped':

            ## Call the update function for the trader.
            self._updater()

            tInfo = self.TradesInformation

            ## Find out the status on a order that is placed.
            if (tInfo['orderStatus']['B'] != None or tInfo['orderStatus']['S'] != None) or (self.botRunType == 'test'):
                self._order_status_manager()

            ## If the state is not on standby then check the trade conditions.
            if self.runtime['state'] == 'Running':
                self._trade_manager()

            time.sleep(2)


    def _updater(self):
        '''
        This section is incharge of updating and getting data for indicators.
        -> Timing
        -> Indicators
        -> Checks
        '''
        tInfo = self.TradesInformation
        cMarket = self.currentMarket

        ## <----------------------------------| BOT TIMING MANAGEMENT |-----------------------------------> ##
        unixTime = time.time()
        update = False

        ## Used to run peridotical updates (every 1 min).
        if self.lastUpdateTime['iu']+60 <= unixTime:
            self.lastUpdateTime['iu'] = unixTime
            update = True
        ## <----------------------------------------------------------------------------------------------> ##

        ## <----------------------------------| INITIALIZE INDICATORS |-----------------------------------> ##
        candles = self.candles
        normalClose = candles['close']
        normalOpen = candles['open']

        ## [INDICATOR] ----->
        self.normalIndicators['MA9'] = TI.get_SMA(normalClose, maPeriod=9)
        self.normalIndicators['MA21'] = TI.get_SMA(normalClose, maPeriod=21)
        self.normalIndicators['BB'] = TI.get_BOLL(normalClose, ma_type=21, stDev=2)
        self.normalIndicators['RSI'] = TI.get_RSI(normalClose, rsiType=14)
        self.normalIndicators['MACD'] = TI.get_MACD(normalOpen, signal=14)
        self.normalIndicators['Ichimoku'] = TI.get_Ichimoku(candles, tS_type=9, kS_type=26, sSB_type=52, dataType='normal')
        ## <----------------------------------------------------------------------------------------------> ##

        ## <----------------------------------| RUNTIME CHECKS |-----------------------------------> ##
        if self.botRunType == 'real':
            ## Used to check what the trader is able to do and what not.
            manager = self._balance_manager()
            logging.info(manager)
            side = 'BUY' if tInfo['orderType']['S'] == None else 'SELL'

            ## Manage the code given by balance manager.
            self._code_manager(manager['code'], side)

            ## Update the balance for active trades.
            balance = self.RESTapi.get_balance()
            self.TradesInformation['currencyLeft'] = tInfo['MAC'] - (balance['free']*cMarket['lastPrice'])

        if update:
            if tInfo['orderType']['S'] == 'limit':
                self.TradesInformation['updateOrder'] = True

        ## Setup a time stamp of the last time the trader was updated.
        currenyTime = time.localtime()
        self.runtime['time'] = '{0}:{1}:{2}'.format(currenyTime[3], currenyTime[4], currenyTime[5])

        if self.runtime['state'] == 'Setup':
            self.runtime['state'] = 'Running'

    def _order_status_manager(self):
        '''
        This is the manager for all and any orders.
        '''
        tInfo = self.TradesInformation
        cMarket = self.currentMarket
        side = 'BUY' if tInfo['orderType']['S'] == None else 'SELL'
        tradeDone = False

        if self.botRunType == 'real':
            if tInfo['orderStatus']['B'] == 'Done' or tInfo['orderStatus']['S'] == 'Done':
                tradeDone = True

        elif self.botRunType == 'test':
            if side == 'BUY':
                if cMarket['lastPrice'] <= tInfo['buyPrice']:
                    tradeDone = True
            elif side == 'SELL':
                if cMarket['lastPrice'] >= tInfo['sellPrice'] and tInfo['sellPrice'] != 0:
                    tradeDone = True

        if tradeDone:
            if side == 'BUY' and (tInfo['orderStatus']['B'] == 'Done' or self.botRunType == 'test'):
                ## This is used to manage an order once it has been filled on teh sell side.

                if self.botRunType == 'real':
                    balance = self.RESTapi.get_balance()['free']

                elif self.botRunType == 'test':
                    balance = float('{0:.2f}'.format(tInfo['currencyLeft']/cMarket['lastPrice']))

                self.TradesInformation['tokenBase'] = balance
                self.TradesInformation['orderType']['B'] = None
                self.TradesInformation['orderType']['S'] = 'wait'
                self.TradesInformation['updateOrder'] = True

                self._setup_sell()
                logging.info('Completed a buy order. [{0}]'.format(self.runtime['market']))

            elif side == 'SELL' and (tInfo['orderStatus']['S'] == 'Done' or self.botRunType == 'test'):
                ## This is used to manage an order on the Sell side.
                fee = self.TradesInformation['MAC'] * COMMISION_FEE
                self.TradesInformation['overall'] += float('{0:.8f}'.format(((tInfo['sellPrice']-tInfo['buyPrice'])*tInfo['tokenBase'])-fee))
                self.TradesInformation['#Trades'] += 1

                self.TradesInformation['orderType']['B'] = 'wait'
                self.TradesInformation['orderType']['S'] = None

                self.TradesInformation['buyPrice'] = 0
                self.TradesInformation['sellPrice'] = 0

                self._setup_buy()
                logging.info('Completed a sell order. [{0}]'.format(self.runtime['market']))


    def _trade_manager(self):
        ''' 
        Here both the sell and buy conditions are managed by the trader.
        -> Sell conditions.
        -> Buy conditions.
        '''
        cMarket = self.currentMarket
        tInfo = self.TradesInformation
        candles = self.candles
        ind = self.normalIndicators

        updateOrder = tInfo['updateOrder']
        order = {'place':False}

        if tInfo['orderType']['S'] != None and not(tInfo['orderStatus']['S'] in ['Order_Lock']):
            '''##############                     ##############
            ##############      SELL CONDITIONS      ##############
            '''##############                     ##############
            logging.info('Checking for Sell condition. [{0}]'.format(self.runtime['market']))

            ##
            conOrder = con.sell_conditions(ind, cMarket, candles)

            if conOrder['place']:
                self.TradesInformation['orderType']['S'] = conOrder['tType']
                price = float('{0:.{1}f}'.format(conOrder['price'], pRounding))

            else:
                if tInfo['orderType']['S'] == 'signal':
                    if self.botRunType == 'real': 
                        self.RESTapi.cancel_open_orders('SELL')
                    self.TradesInformation['orderStatus']['S'] = None
                    self.TradesInformation['orderType']['S'] = 'wait'
                    self.TradesInformation['sellPrice'] = 0


            '''############### SIGNAL SELL ###############'''
            if self.TradesInformation['orderType']['S'] == 'signal':
                if price < tInfo['sellPrice'] or tInfo['sellPrice'] == 0:
                    print('[PLACING]: {0}'.format(conOrder['description']))
                    order = {'place':True, 'side':'SELL'}


        elif tInfo['orderType']['B'] and not(tInfo['orderStatus']['B'] in ['Order_Lock']):
            '''##############                    ##############
            ##############      BUY CONDITIONS      ##############
            '''##############                    ##############
            logging.debug('Checking for Buy condition. [{0}]'.format(self.runtime['market']))

            ## This will be used to determin what type of condition is to be placed.
            conOrder = con.buy_conditions(ind, cMarket, candles)

            if conOrder['place']:
                self.TradesInformation['orderType']['B'] = conOrder['tType']
                price = float('{0:.{1}f}'.format(conOrder['price'], pRounding))

            else:
                ## This will reset the orders back to waiting if there are no orders.
                if tInfo['orderType']['B'] == 'signal':
                    if self.botRunType == 'real': 
                        self.RESTapi.cancel_open_orders('BUY')
                    self.TradesInformation['orderStatus']['B'] = None
                    self.TradesInformation['orderType']['B'] = 'wait'
                    self.TradesInformation['buyPrice'] = 0

            '''############### SIGNAL BUY ###############'''
            if self.TradesInformation['orderType']['B'] == 'signal':
                if price > tInfo['buyPrice']:
                    print('[PLACING]: {0}'.format(conOrder['description']))
                    order = {'place':True, 'side':'BUY'}

        ## All orders to be placed will be managed via the manager.
        if order['place']:
            if self.botRunType == 'real':
                orderInfo = self.RESTapi.order_placer(self.marketRules, 
                                                    self.TradesInformation, 
                                                    order['side'], 
                                                    'LIMIT', 
                                                    price=price)

                logging.info('orderInfo: {0} [{1}]'.format(orderInfo, self.runtime['market']))

                if orderInfo:
                    self._code_manager(orderInfo['code'], order['side'], price=price)

            elif self.botRunType == 'test':
                self._code_manager(0, order['side'], price=price)


    def _balance_manager(self):
        '''
        The order manager is used when trying to place an order and will return data based on the status of the order that was placed.
        '''
        tInfo = self.TradesInformation
        mRules = self.marketRules
        lastPrice = self.currentMarket['lastPrice']
        message = None
        code = None

        if self.runtime['state'] == 'Standby':
            ## If the bot is on STANDBY mode conditions.
            balanceBTC = self.RESTapi.get_balance('BTC')
            if balanceBTC['free'] > tInfo['currencyLeft'] > mRules['MINIMUM_NOTATION']:
                ## If the current BTC balance is over the minimum required to place an order and is greater than the currency left the bot will go back to RUNNING mode.
                code, message = 11, 'Enough to move out of STANDBY. [{0}]'.format(self.runtime['market'])

        elif tInfo['orderStatus']['B'] == 'Done' or tInfo['orderStatus']['S'] == 'Done':
            pass

        else:
            assetBalance = self.RESTapi.get_balance()
            if tInfo['orderType']['B'] != None:
                ## This deals with the buy side for checking balances.
                if tInfo['orderType']['B'] == 'wait':
                    ## If no order has currently been placed by the bot.
                    balanceBTC = self.RESTapi.get_balance('BTC')
                    if balanceBTC['free'] < tInfo['currencyLeft']:
                        ## If there is not enough BTC to palce an order the bot will be placed into STANDBY mode.
                        code, message = 10, 'Not Enough to place initial Buy. [{0}]'.format(self.runtime['market'])

                    else:
                        ## If the is enough BTC to place an order the bot will be set to allow placing orders.
                        code, message = 100, 'Enough to place a Buy order. [{0}]'.format(self.runtime['market'])

                    walletAssetValue = (assetBalance['locked']+assetBalance['free'])*lastPrice
                    if (walletAssetValue > mRules['MINIMUM_NOTATION']):
                        ## If the asset value is greater than the minimum to palce an order the bot will declare there is an un finished sell order.
                        code, message = 110, 'Potential open trade. [{0}]'.format(self.runtime['market'])
                else:
                    if tInfo['orderStatus']['B'] == 'Placed':
                        ## If the current order status for buy is anything but waiting.

                        oOrder = self.RESTapi.check_open_orders()
                        if oOrder != 'Empty':
                            ## Conditions for the order being placed and still being open.
                            if (tInfo['currencyLeft'] > mRules['MINIMUM_NOTATION']):
                                ## This checks if there is enought currency left to place a buy order.

                                balanceBTC = self.RESTapi.get_balance('BTC')
                                if (balanceBTC['free'] > tInfo['currencyLeft']):
                                    ## If there is enough BTC to place new order and there is enough currency left to place an order it will be updated.
                                    code, message = 100, 'Enough to re-place Buy. [{0}]'.format(self.runtime['market'])
                                else:
                                    ## If the current BTC balance is less than what is needed to place a new order the current order is locked.
                                    code, message = 101, 'Lock Buy. [{0}]'.format(self.runtime['market'])
                            else:
                                ## If the currency left is less than the minimum notation the order is locked.
                                code, message = 101, 'Lock Buy. [{0}]'.format(self.runtime['market'])

                        else:
                            if assetBalance['free']*lastPrice > mRules['MINIMUM_NOTATION']:
                                ## If the balance of the asset is over the minimum amount required and the order is empty the order is considered complete.
                                code, message = 200, 'Finished order buy. [{0}]'.format(self.runtime['market'])

            if tInfo['orderType']['S'] != None:
                ## This deals with the Sell side for checking balances and trades.
                walletAssetValue = (assetBalance['locked']+assetBalance['free'])*lastPrice

                if tInfo['orderStatus']['S'] == 'Placed':
                    oOrder = self.RESTapi.check_open_orders()

                    if oOrder != 'Empty':
                        ## Conditions for the order being placed and still being open.
                        if (walletAssetValue > mRules['MINIMUM_NOTATION']):
                            ## If the current asset value is over the minimum required to place an order the bot will be allowed to place.
                            code, message = 100, 'Enough to re-place Sell. [{0}]'.format(self.runtime['market'])
                        else:
                            ## If the current asset value is under the minimum required to place an order the bot will lock its sell order.
                            code, message = 101, 'Lock Sell. [{0}]'.format(self.runtime['market']) 
                    else:
                        if walletAssetValue < mRules['MINIMUM_NOTATION']:
                            ## If the wallet asset value is less than the minimum to place and order and also the open orders are empty the order is considered complete.
                            code, message = 200, 'Finished order Sell. [{0}]'.format(self.runtime['market'])
                else:
                    if (walletAssetValue > mRules['MINIMUM_NOTATION']):
                        code, message = 100, 'Enough to place new Sell. [{0}]'.format(self.runtime['market'])

        logging.info('Balance manager:{0}'.format({'code':code, 'msg':message}, self.runtime['market']))

        return({'code':code, 'msg':message})


    def _code_manager(self, code, side=None, **OPargs):
        '''
        CODES:
        0 - Order have been placed.
        10 - Not enough BTC.
        11 - Allowed to come out of standby.
        100 - Able to place either sell or buy order.
        101 - lock the current trade.
        110 - Potential open trade.
        200 - Order has been declared finished.
        '''
        if code == 0:
            ## Order has been placed.
            if side == 'BUY':
                self.TradesInformation['orderStatus']['B'] = 'Placed'
                self.TradesInformation['buyPrice'] = OPargs['price']
            elif side == 'SELL':
                self.TradesInformation['orderStatus']['S'] = 'Placed'
                self.TradesInformation['sellPrice'] = OPargs['price']

        elif code == 10:
            ## Not enough BTC to place an intial buy order.
            self.runtime['state'] = 'Standby'

        elif code == 11:
            ## There is now enough BTC to place an buy order.
            self.runtime['state'] = 'Running'

        elif code == 100:
            ## The bot is able to place a order on the market.
            pass

        elif code == 101:
            ## There is not enough to place a new order so the order must be locked.
            if side == 'BUY':
                self.TradesInformation['orderStatus']['B'] = 'Order_Lock'
            elif side == 'SELL':
                self.TradesInformation['orderStatus']['S'] = 'Order_Lock'

        elif code in [200, 110]:
            ## order has been declared as finished.
            if side == 'BUY':
                self.TradesInformation['orderStatus']['B'] = 'Done'
            elif side == 'SELL':
                self.TradesInformation['orderStatus']['S'] = 'Done'


    def _setup_sell(self):
        ''' Used to setup the trader for selling after a buy has been completed. '''
        self.TradesInformation['orderStatus']['B']  = None
        self.TradesInformation['currencyLeft']      = 0


    def _setup_buy(self):
        ''' Used to setup the trader for buying after a sell has been completed. '''
        self.TradesInformation['orderStatus']['S']  = None
        self.TradesInformation['tokensHolding']     = 0
        self.TradesInformation['sellPrice']         = 0
        self.TradesInformation['buyPrice']          = 0
        self.TradesInformation['currencyLeft']      = self.TradesInformation['MAC']


    def get_trader_data(self):
        ''' Get bundled data about the current trader. '''
        botData = {'runtime': self.runtime,
                'currentMarket': self.currentMarket,
                'tradesInfo': self.TradesInformation}

        return(botData)


    def give_trader_data(self, data):
        ''' This is used to give data to the trader (passed from the socket). '''
        self.candles = data['candles']

        self.currentMarket['lastPrice'] = float(data['candles']['close'][0])
        self.currentMarket['bidPrice']  = float(data['depth']['bids'][0][0])
        self.currentMarket['askPrice']  = float(data['depth']['asks'][0][0])