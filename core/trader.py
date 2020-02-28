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
from . import rest_api
import conditions as con
import TradeIndicators as TI


## Minimum price rounding.
pRounding = 8

## Base commission fee with binance.
COMMISION_FEE = 0.00075


class BaseTrader(object):

    def __init__(self, symbol, filters, rest_api, run_type):
        '''
        Initilise the trader object and all of the atributes that are required for it to be run.

        -> Initilize Data Objects.
            Initilize all the data objects that will be required to track and monitor the trader.

        '''

        ## Initilize Data Objects.

        # Sets the rest api that will be used by the trader.
        self.rest_api = rest_api

        # Sets the run type for the trader, this is usually either REAL or TEST.
        self.run_type = run_type

        # Holds update timers.
        self.last_inter_update = 0 # Last time an update occured on a set interval.
        
        # Holds the candles.
        self.candles = None
        
        # Holds the trade indicators.
        self.indicators = {}

        # Force sell is set if a active trade is found on script reset.
        self.force_sell = False

        # Holds the current symbolic pair of the market being traded.
        self.symbol = symbol
        
        # Holds runtime info of the trader.
        self.runtime = {
            'state':'STOP',   # The traders state. [RUN, FORCE_STANDBY, STANDBY, STOP, COMPLETED_TRADE]
            'time':0}       # Last time an update was DONE.
        
        # Holds current market information.
        self.prices = {
            'lastPrice':None,   # Last price.
            'askPrice':None,    # Ask price.
            'bidPrice':None}    # Bid price.
        
        # Holds information on current/past trades of the trader.
        self.trade_information = {
            'MAC':0,                            # 'MAC' this holds the Maximum Allowed Currency the bot can trade with.
            'currencyLeft':0,                   # 'currencyLeft' this holds the currency the bot has left to trade.
            'buyPrice':0,                       # 'buyPrice' this holds the buy price for the bot.
            'sellPrice':0,                      # 'sellPrice' this holds the sell price of the bot.
            'tokenBase':0,                      # 'tokenBase' this holds the base tokens bought.
            'canOrder':False,                   # 'canOrder' this will determin if the bot is allowed to place an order or not.
            'orderType':{'B':'WAIT', 'S':None}, # 'orderType' holds the current type of trade being carried out (B:[WAIT/SIGNAL/RSI] S:[LIMIT/SIGNAL/Trail])
            'orderStatus':{'B':None, 'S':None}, # 'orderStatus' holds the status for the current order (B:[None/PLACED/PF/Locked] S:[None/PLACED/PF/Locked/PF_Sig])
            'updateOrder':False,                # 'updateOrder' this is used to determin if a PLACED order should be updated
            '#Trades':0,                        # '#Trades' this holds the number of FULL trades made by this market.
            'overall':0}                        # 'overall' this holds the overall outcomes for this markets trades.

        # Holds the rules required for the market.
        self.rules = {
            'LOT_SIZE':filters['lotSize'],
            'TICK_SIZE':filters['tickSize'],
            'MINIMUM_NOTATION':filters['minNotional']}
        
        logging.debug('Initilized trader variables. [{0}]'.format(symbol))


    def start(self, MAC):
        '''
        Start the trader.
        Requires: MAC (Max Allowed Currency, the max amount the trader is allowed to trade with in BTC).

        -> Check for previous trade.
            If a recent, not closed traded is seen, or leftover currency on the account over the min to place order then set trader to sell automatically.
        
        ->  Start the trader thread. 
            Once all is good the trader will then start the thread to allow for the market to be monitored.
        '''
        self.runtime['state'] = 'SETUP'
        self.trade_information['MAC'] = MAC
        self.trade_information['currencyLeft'] = MAC

        if self.run_type == 'REAL':
            self.rest_api.cancel_open_orders('ALL', self.symbol)

        if self.force_sell:
            check_closed_orders = self.rest_api.check_closed_orders('BUY', self.symbol)

            if check_closed_orders['CALL']:
                self.trade_information['buyPrice'] = check_closed_orders['data']['price']
                self._setup_sell()
            self.force_sell = False

        ## Start the main of the trader in a thread.
        trader_thread = threading.Thread(target=self._main)
        trader_thread.start()

        logging.info('Started trader. [{0}]'.format(self.symbol))


    def stop(self):
        ''' 
        Stop the trader.

        -> Trader cleanup.
            To gracefully stop the trader and cleanly eliminate the thread as well as market orders.
        '''
        self.runtime['state'] = 'STOP'
        self.rest_api.cancel_open_orders('ALL', self.symbol)
        self.run_type = None

        logging.info('Stopped trader. [{0}]'.format(self.symbol))


    def _main(self):
        '''
        Main body for the trader loop.

        -> WAIT for candle data to be fed to trader.
            Infinite loop to check if candle has been populated with data,

        -> Call the updater.
            Updater is used to re-calculate the indicators as well as carry out timed checks.

        -> Call Order Manager.
            Order Manager is used to check on currently PLACED orders.

        -> Call Trader Manager.
            Trader Manager is used to check the current conditions of the indicators then set orders if any can be PLACED.

        '''
        while True:
            if self.candles != None and self.prices['bidPrice'] != None:
                break
            time.sleep(1)

        while self.runtime['state'] != 'STOP':
            ## Call the update function for the trader.
            self._updater()

            if not self.runtime['state'] in ['STANDBY', 'COMPLETED_TRADE', 'FORCE_STANDBY']:
                tInfo = self.trade_information

                ## Find out the status on a order that is PLACED.
                if (tInfo['orderStatus']['B'] != None or tInfo['orderStatus']['S'] != None) or (self.run_type == 'TEST'):
                    self._order_status_manager()

                ## If the state is not on standby then check the trade conditions.
                if self.runtime['state'] == 'RUN':
                    self._trade_manager()

            time.sleep(4)


    def _updater(self):
        '''
        This section is incharge of updating and getting data for indicators.

        -> Do periodic timed events
            The updater will update data based on a set interval.
            
        -> Calculate and Re-calculate the Indicators.
            re-calculate the indicators used with new candle data.
    
        -> Do checks on the API account.
            Do checks on teh account depending on the current order state.
            
        '''
        current_unix_time = time.time()

        ## Periodic timer (1 min) 
        if self.last_inter_update+60 <= current_unix_time:
            self.last_inter_update = current_unix_time

        ## Re-calculate Indicators
        if 'MACD' in self.indicators:
            MACD = self.indicators['MACD'][:]

        ## [INDICATOR] ----->
        try:
            self.indicators['MACD'] = TI.get_MACD(self.candles['close'], signal=14)
        except :
            self.indicators['MACD'] = MACD[:]

        ## Main Updater
        if self.runtime['state'] == 'FORCE_STANDBY':
            # If force standy then force the trader to reset.
            self._setup_buy()
            self.runtime['state'] = 'STANDBY'

        if self.run_type == 'REAL':
            # Check the current order/trade.
            manager = self._balance_manager()

            if manager:
                if manager['code'] != None:
                    side = 'BUY' if self.trade_information['orderType']['S'] == None else 'SELL'
                    self._code_manager(manager['code'], side)

        # Setup a time stamp of the last time the trader was updated.
        current_localtime = time.localtime()
        self.runtime['time'] = '{0}:{1}:{2}'.format(current_localtime[3], current_localtime[4], current_localtime[5])

        if self.runtime['state'] == 'SETUP':
            self.runtime['state'] = 'RUN'


    def _order_status_manager(self):
        '''
        This is the manager for all and any active orders.

        -> Check orders (Test/Real).
            This checks both the buy and sell side for test orders and updates the trader accordingly.

        -> Monitor trade outcomes.
            Monitor and note down the outcome of trades for keeping track of progress.

        '''

        tInfo = self.trade_information
        side = 'BUY' if tInfo['orderType']['S'] == None else 'SELL'
        trade_done = False

        ## Check orders (Test/Real).
        if self.run_type == 'REAL':
            # Signify order completion for real trades.
            if tInfo['orderStatus']['B'] == 'DONE' or tInfo['orderStatus']['S'] == 'DONE':
                trade_done = True

        elif self.run_type == 'TEST':
            # Signify order completion for test trades.
            if tInfo['orderStatus']['B'] != None and side == 'BUY':
                if self.prices['lastPrice'] <= tInfo['buyPrice']:
                    trade_done = True
            elif tInfo['orderStatus']['S'] != None and side == 'SELL':
                if self.prices['lastPrice'] >= tInfo['sellPrice']:
                    trade_done = True

        ## Monitor trade outcomes.
        if trade_done:
            print('Finished {0} trade for {1}'.format(side, self.symbol))

            if side == 'BUY' and (tInfo['orderStatus']['B'] == 'DONE' or self.run_type == 'TEST'):
                # Here all the necissary variables and values are added to signal a completion on a buy trade.

                if self.run_type == 'REAL':
                    token = self.symbol[:-3]
                    balance = self.rest_api.get_balance(token)['free']
                elif self.run_type == 'TEST':
                    balance = float('{0:.8f}'.format(tInfo['currencyLeft']/self.prices['lastPrice']))

                self.trade_information['tokenBase'] = balance

                self._setup_sell()
                logging.info('Completed buy order. [{0}]'.format(self.symbol))

            elif side == 'SELL' and (tInfo['orderStatus']['S'] == 'DONE' or self.run_type == 'TEST'):
                # Here all the necissary variables and values are added to signal a completion on a sell trade.

                fee = self.trade_information['MAC'] * COMMISION_FEE
                self.trade_information['overall'] += float('{0:.8f}'.format(((tInfo['sellPrice']-tInfo['buyPrice'])*tInfo['tokenBase'])-fee))
                self.trade_information['#Trades'] += 1

                self._setup_buy()
                logging.info('Completed sell order. [{0}]'.format(self.symbol))


    def _trade_manager(self):
        ''' 
        Here both the sell and buy conditions are managed by the trader.

        -> Manager Sell Conditions.
            Manage the placed sell condition as well as monitor conditions for the sell side.

        -> Manager Buy Conditions.
            Manage the placed buy condition as well as monitor conditions for the buy side.

        -> Place Market Order.
            Place orders on the market with real and assume order placemanet with test.

        '''
        tInfo = self.trade_information

        orderType = None
        updateOrder = tInfo['updateOrder']
        order = {'place':False}

        if tInfo['orderType']['S'] and tInfo['orderStatus']['S'] != 'ORDER_LOCK':
            ## Manager Sell Conditions.

            logging.debug('Checking for Sell condition. [{0}]'.format(self.symbol))

            # Check the conditions in place to see if a order can be setup.
            new_order = con.sell_conditions(
                self.indicators, 
                self.prices, 
                tInfo, 
                self.candles)

            if new_order['place']:
                orderType = new_order['tType']
                price = float('{0:.{1}f}'.format(new_order['price'], pRounding))

                askPrice = self.prices['askPrice']

                if orderType == 'SIGNAL':
                    # Setup a signal sell order.
                    if (price != tInfo['sellPrice'] and tInfo['sellPrice'] != askPrice) or updateOrder:
                        order = {'place':True, 'side':'SELL'}

                else:
                    logging.critical('The trade type [{0}] has not been configured'.format(new_order['tType']))
            else:
                if orderType == 'SIGNAL':
                    if self.run_type == 'REAL':
                        self.rest_api.cancel_open_orders('SELL', self.symbol)
                    self.trade_information['orderStatus']['S'] = None
                    self.trade_information['orderType']['S'] = 'WAIT'


        elif tInfo['orderType']['B'] and tInfo['orderStatus']['B'] != 'ORDER_LOCK':
            ## Manager Buy Conditions.

            logging.debug('Checking for Buy condition. [{0}]'.format(self.symbol))

            # Check the conditions in place to see if a order can be setup.
            new_order = con.buy_conditions(
                self.indicators, 
                self.prices, 
                tInfo, 
                self.candles)

            if new_order['place']:
                orderType = new_order['tType']
                price = float('{0:.{1}f}'.format(new_order['price'], pRounding))

                bidPrice = self.prices['bidPrice']

                if orderType == 'SIGNAL':
                    # Setup a signal buy order.
                    if (price != tInfo['buyPrice'] and tInfo['buyPrice'] != bidPrice) or updateOrder:
                        order = {'place':True, 'side':'BUY'}

                else:
                    logging.critical('The trade type [{0}] has not been configured'.format(new_order['tType']))

            else:
                # Cancel a existing signal buy order.
                if tInfo['orderType']['B'] == 'SIGNAL':
                    if self.run_type == 'REAL':
                        self.rest_api.cancel_open_orders('BUY', self.symbol)
                    self.trade_information['orderStatus']['B'] = None
                    self.trade_information['orderType']['B'] = 'WAIT'

        if updateOrder:
            self.trade_information['updateOrder'] = False

        ## Place Market Order.
        if order['place']:
            print('{0} : [{1}]'.format(new_order['description'], self.symbol))

            orderInfo = None

            if self.run_type == 'REAL':
                # Attempt to place an order on the market.
                orderInfo = self.rest_api.order_placer(
                    self.symbol,
                    self.rules, 
                    self.trade_information, 
                    order['side'], 
                    'LIMIT', 
                    price=price)

                print('orderInfo: {0} [{1}]'.format(orderInfo, self.symbol))

                if orderInfo:
                    code = orderInfo['code']
                else:
                    self.runtime['state'] = 'FORCE_STANDBY'
                    return

            elif self.run_type == 'TEST':
                orderInfo = True
                code = 0
            
            # Check the status of the order code.
            if orderInfo:
                self._code_manager(code, order['side'], price=price, orderType=orderType)


    def _balance_manager(self):
        '''
        The order manager is used when trying to place an order and will return data based on the status of the order that was placed.
        '''
        symbol = self.symbol
        token = symbol[:-3]
        tInfo = self.trade_information
        message = None
        code = None

        if tInfo['orderType']['B'] != None and tInfo['orderType']['B'] != 'WAIT':

            if tInfo['orderStatus']['B'] in ['PLACED', 'ORDER_LOCK']:
                ## If the current order status for buy is anything but WAITing.
                open_order = self.rest_api.check_open_orders(symbol)
                if not open_order:
                    return({'code':code, 'msg':message})

                if open_order == 'Empty': 
                    assetBalance = self.rest_api.get_balance(token)

                    if not assetBalance:
                        return({'code':code, 'msg':message})

                    if assetBalance['free']*self.prices['lastPrice'] > self.rules['MINIMUM_NOTATION']:
                        ## If the balance of the asset is over the minimum amount required and the order is empty the order is considered complete.
                        code, message = 200, 'Finished order buy. [{0}]'.format(symbol)
                    else:
                        return({'code':code, 'msg':message})
                else:
                    balanceBTC = self.rest_api.get_balance('BTC')
                    if not balanceBTC:
                        return({'code':code, 'msg':message})

                     ## If there is enough BTC to place new order and there is enough currency left to place an order it will be updated.
                    if not((balanceBTC['free']+balanceBTC['locked']) > tInfo['currencyLeft']):
                        code, message = 102, 'Lock Buy. [{0}]'.format(symbol)
                    else:
                        ## Conditions for the order being PLACED and still being open.
                        if (tInfo['currencyLeft'] > self.rules['MINIMUM_NOTATION']):
                            ## This checks if there is enought currency left to place a buy order.
                            code, message = 100, 'Enough to re-place Buy. [{0}]'.format(symbol)
                        else:
                            ## If the current BTC balance is less than what is needed to place a new order the current order is locked.
                            code, message = 102, 'Lock Buy. [{0}]'.format(symbol)
            else:
                balanceBTC = self.rest_api.get_balance('BTC')
                if not balanceBTC:
                    return({'code':code, 'msg':message})

                ## Make sure there is enough BTC to place and buy order.
                if balanceBTC['free'] < tInfo['currencyLeft']:
                    code, message = 1, 'Not enought to place buy. [{0}]'.format(symbol)

        if tInfo['orderType']['S'] != None:
            ## This deals with the Sell side for checking balances and trades.
            assetBalance = self.rest_api.get_balance(token)
            if not assetBalance:
                return({'code':code, 'msg':message})

            walletAssetValue = (assetBalance['locked']+assetBalance['free'])*self.prices['lastPrice']
            self.trade_information['currencyLeft'] = tInfo['MAC'] - (assetBalance['free']*self.prices['lastPrice'])

            if tInfo['orderStatus']['S'] in ['PLACED', 'ORDER_LOCK']:
                open_order = self.rest_api.check_open_orders(symbol)
                if not open_order:
                    return({'code':code, 'msg':message})

                if open_order != 'Empty':
                    ## Conditions for the order being PLACED and still being open.
                    if (walletAssetValue > self.rules['MINIMUM_NOTATION']):
                        ## If the current asset value is over the minimum required to place an order the bot will be allowed to place.
                        code, message = 100, 'Enough to re-place Sell. [{0}]'.format(symbol)
                    else:
                        ## If the current asset value is under the minimum required to place an order the bot will lock its sell order.
                        code, message = 102, 'Lock Sell. [{0}]'.format(symbol) 
                else:
                    if walletAssetValue < self.rules['MINIMUM_NOTATION']:
                        ## If the wallet asset value is less than the minimum to place and order and also the open orders are empty the order is considered complete.
                        code, message = 200, 'Finished order Sell. [{0}]'.format(symbol)
                    else:
                        code, message = 101, 'Enough to place new Sell. [{0}]'.format(symbol)
            else:
                if (walletAssetValue > self.rules['MINIMUM_NOTATION']):
                    code, message = 101, 'Enough to place new Sell. [{0}]'.format(symbol)

        if code:
            logging.info('Balance manager:{0}'.format({'code':code, 'msg':message}, symbol))

        return({'code':code, 'msg':message})


    def _code_manager(self, code, side=None, **kwargs):
        '''
        CODES:
        0 - Order have been PLACED.
        1 - Not enough to place an order.
        100 - Able to place either sell or buy order.
        101 - Order can be PLACED.
        102 - lock the current trade.
        200 - Order has been declared finished.
        '''

        if code == 0:
            ## Order has been PLACED.
            if side == 'BUY':
                self.trade_information['orderType']['B'] = kwargs['orderType']
                self.trade_information['orderStatus']['B'] = 'PLACED'
                self.trade_information['buyPrice'] = kwargs['price']
            elif side == 'SELL':
                self.trade_information['orderType']['S'] = kwargs['orderType']
                self.trade_information['orderStatus']['S'] = 'PLACED'
                self.trade_information['sellPrice'] = kwargs['price']

        elif code == 1:
            ## Not enough to place a order on the market.
            self.runtime['state'] = 'FORCE_STANDBY'

        elif code == 100:
            ## The bot is able to place a order on the market.
            if self.runtime['state'] == 'STANDBY':
                self.runtime['state'] = 'RUN'

        elif code == 101:
            ## The bot is able to place a order on the market.
            if side == 'BUY':
                pass
            elif side == 'SELL':
                pass
            
            self.trade_information['updateOrder'] = True

        elif code == 102:
            ## There is not enough to place a new order so the order must be locked.
            if side == 'BUY':
                self.trade_information['orderStatus']['B'] = 'ORDER_LOCK'
            elif side == 'SELL':
                self.trade_information['orderStatus']['S'] = 'ORDER_LOCK'

        elif code == 200:
            ## order has been declared as finished.
            if side == 'BUY':
                self.trade_information['orderStatus']['B'] = 'DONE'
            elif side == 'SELL':
                self.trade_information['orderStatus']['S'] = 'DONE'


    def _setup_sell(self):
        ''' Used to setup the trader for selling after a buy has been completed. '''
        self.trade_information['orderStatus']['B'] = None
        self.trade_information['currencyLeft'] = 0

        self.trade_information['orderType']['B'] = None
        self.trade_information['orderType']['S'] = 'WAIT'
        self.trade_information['updateOrder'] = True


    def _setup_buy(self):
        ''' Used to setup the trader for buying after a sell has been completed. '''
        self.trade_information['orderStatus']['S'] = None
        self.trade_information['tokensHolding'] = 0
        self.trade_information['sellPrice'] = 0
        self.trade_information['buyPrice'] = 0
        self.trade_information['currencyLeft'] = self.trade_information['MAC']

        self.trade_information['orderType']['B'] = 'WAIT'
        self.trade_information['orderType']['S'] = None


    def give_trader_data(self, data):
        ''' This is used to give data to the trader (passed from the socket). '''

        try:
            lastPrice = self.prices['lastPrice']
            self.prices['lastPrice'] = float(data['candles']['close'][0])
        except Exception as e:
            self.prices['lastPrice'] = lastPrice
            return
        
        if data['bid'] != None:
            self.prices['bidPrice'] = float(data['bid'])
            self.prices['askPrice'] = float(data['ask'])

        self.candles = data['candles']