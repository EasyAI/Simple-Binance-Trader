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
import trader_configuration as TC


## Base commission fee with binance.
COMMISION_FEE = 0.00075

INVERT_FOR_BTC_FIAT = True

class BaseTrader(object):

    def __init__(self, base_asset, quote_asset, filters, socket_api, rest_api):
        '''
        Initilise the trader object and all of the atributes that are required for it to be run.

        -> Initilize Data Objects.
            Initilize all the data objects that will be required to track and monitor the trader.
        '''
        symbol = '{0}{1}'.format(base_asset, quote_asset)

        logging.info('[BaseTrader] Initilizing trader object for market {0}.'.format(symbol))

        # Sets the rest api that will be used by the trader.
        self.rest_api = rest_api
        self.socket_api = socket_api

        # Holds update timers.
        self.last_inter_update = 0 # Last time an update occured on a set interval.

        self.orderDesc = {'B':'', 'S':''}
        
        # Holds the trade indicators.
        self.indicators = {}

        self.custom_conditional_data = {}

        self.orders_log_path = 'order_log.txt'

        # Force sell is set if a active trade is found on script reset.
        self.force_sell = False

        # Hold the base MAC
        self.base_mac = 0 # 'MAC' this holds the Maximum Allowed Currency the bot can trade with.

        self.btc_wallet = None
        self.trading_asset = None

        # Holds the current symbolic pair of the market being traded.
        self.btc_base_pair  = True if base_asset == 'BTC'else False
        self.print_pair     = '{0}-{1}'.format(quote_asset, base_asset)
        self.symbol         = symbol
        self.quote_asset    = quote_asset
        self.base_asset     = base_asset
        
        # Holds runtime info of the trader.
        self.last_update_time   = 0
        self.runtime_state      = 'STOP'

        self.buyTime = 0


        self.order_id = {
            'B':0,
            'S':0
        }
        
        # Holds current market information.
        self.prices = {
            'lastPrice':0,   # Last price.
            'askPrice':0,    # Ask price.
            'bidPrice':0}    # Bid price.
        
        # Holds information on current/past trades of the trader.
        self.trade_information = {
            'currencyLeft':0,                   # 'currencyLeft' this holds the currency the bot has left to trade.
            'buyPrice':0,                       # 'buyPrice' this holds the buy price for the bot.
            'sellPrice':0,                      # 'sellPrice' this holds the sell price of the bot.
            'tokens_bought':0,
            'tokenBase':0,                      # 'tokenBase' this holds the base tokens bought.
            'stopLoss':False,
            'canOrder':True,                    # 'canOrder' this will determin if the bot is allowed to place an order or not.
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


    def start(self, MAC, wallet_pair, open_orders=None):
        '''
        Start the trader.
        Requires: MAC (Max Allowed Currency, the max amount the trader is allowed to trade with in BTC).

        -> Check for previous trade.
            If a recent, not closed traded is seen, or leftover currency on the account over the min to place order then set trader to sell automatically.
        
        ->  Start the trader thread. 
            Once all is good the trader will then start the thread to allow for the market to be monitored.
        '''
        logging.debug('[BaseTrader] Starting trader {0}.'.format(self.print_pair))

        self.runtime_state                      = 'SETUP'
        self.base_mac                           = float(MAC)
        self.trade_information['currencyLeft']  = float(MAC)

        base = self.base_asset
        quote = self.quote_asset

        startSide = 'BUY'
        total_val = 0

        if open_orders != None:
            ## The trader will look if any trades currently open (BUY/SELL)
            if open_orders['side'] == 'BUY':
                self.trade_information['buyPrice'] = float(open_orders['price'])
                self.trade_information['orderType']['B'] = 'SIGNAL'
                self.trade_information['orderStatus']['B'] = 'PLACED'
                self.order_id['B'] = open_orders['orderId']

            elif open_orders['side'] == 'SELL':
                self.trade_information['sellPrice'] = float(open_orders['price'])
                self.trade_information['orderType']['S'] = 'SIGNAL'
                self.trade_information['orderStatus']['S'] = 'PLACED'
                self.order_id['S'] = open_orders['orderId']

            logging.info('[BaseTrader] Found open {0} for market {1}.'.format(open_orders['side'], self.print_pair))

        ## The trader will keep a copy of the values for the quote and base asset for trading.
        if self.btc_base_pair:
            self.btc_wallet = wallet_pair[base]
            if quote in wallet_pair:
                self.trading_asset = wallet_pair[quote]
                price = self.rest_api.get_latest_price(symbol=self.symbol)
                total_val = ((wallet_pair[quote][0]+wallet_pair[quote][1]) / float(price['price']))
                if total_val > 0.00011:
                    startSide = 'SELL'
                    self._setup_sell()
        else:
            self.btc_wallet = wallet_pair[quote]
            if base in wallet_pair:
                self.trading_asset = wallet_pair[base]
                price = self.rest_api.get_latest_price(symbol=self.symbol)
                total_val = ((wallet_pair[base][0]+wallet_pair[base][1]) * float(price['price']))
                if total_val > 0.00011:
                    startSide = 'SELL'
                    self._setup_sell()

        p_str = '[{0}] Starting on side {1}'.format(self.print_pair, startSide)
        if total_val > 0:
            p_str += ', value: {0:.8f}'.format(total_val)

        logging.info(p_str+'.')
        logging.debug('[BaseTrader] Wallet Pair '+str(wallet_pair))

        ## Start the main of the trader in a thread.
        logging.debug('[BaseTrader] Starting trader main thread {0}.'.format(self.print_pair))
        trader_thread = threading.Thread(target=self._main)
        trader_thread.start()


    def stop(self):
        ''' 
        Stop the trader.

        -> Trader cleanup.
            To gracefully stop the trader and cleanly eliminate the thread as well as market orders.
        '''
        logging.debug('[BaseTrader] Stopping trader {0}.'.format(self.print_pair))

        if self.trade_information['orderType']['S'] == None:
            self.trade_information['orderStatus']['B'] = 'FORCE_PREVENT_BUY'

            while True:
                if self.trade_information['orderType']['S'] == None:
                    break
                time.sleep(10)

        else:
            self.rest_api.cancel_open_orders('ALL', self.symbol)

        self.runtime_state = 'STOP'


    def _main(self):
        '''
        Main body for the trader loop.

        -> Wait for candle data to be fed to trader.
            Infinite loop to check if candle has been populated with data,

        -> Call the updater.
            Updater is used to re-calculate the indicators as well as carry out timed checks.

        -> Call Order Manager.
            Order Manager is used to check on currently PLACED orders.

        -> Call Trader Manager.
            Trader Manager is used to check the current conditions of the indicators then set orders if any can be PLACED.
        '''
        sock_symbol = self.base_asset+self.quote_asset

        while True:
            if self.socket_api.get_live_candles()[sock_symbol] and ('a' in self.socket_api.get_live_depths()[sock_symbol]):
                break

        last_wallet_update_time = 0

        while self.runtime_state != 'STOP':
            ## Call the update function for the trader.
            candles = self.socket_api.get_live_candles()[sock_symbol]
            books_data = self.socket_api.get_live_depths()[sock_symbol]
            indicators = TC.technical_indicators(candles)
            self.custom_conditional_data, self.trade_information = TC.other_conditions(self.custom_conditional_data, self.trade_information, indicators)
            logging.debug('[BaseTrader] Collected trader data from socket. [{0}]'.format(self.print_pair))

            socket_buffer_global = self.socket_api.socketBuffer

            if sock_symbol in self.socket_api.socketBuffer:
                socket_buffer_symbol = self.socket_api.socketBuffer[sock_symbol]
            else:
                socket_buffer_symbol = None

            if 'outboundAccountInfo' in socket_buffer_global:
                if last_wallet_update_time != socket_buffer_global['outboundAccountInfo']['E']:
                    last_wallet_update_time = socket_buffer_global['outboundAccountInfo']['E']
                    foundBase=False
                    foundQuote=False
                    for wallet in socket_buffer_global['outboundAccountInfo']['B']:
                        if self.base_asset == wallet['a']:
                            if self.base_asset == 'BTC':
                                self.btc_wallet = [float(wallet['f']), float(wallet['l'])]
                            else:
                                self.trading_asset = [float(wallet['f']), float(wallet['l'])]
                            foundBase=True

                        if self.quote_asset == wallet['a']:
                            if self.base_asset == 'BTC':
                                self.trading_asset = [float(wallet['f']), float(wallet['l'])]
                            else:
                                self.btc_wallet = [float(wallet['f']), float(wallet['l'])]
                            foundQuote=True 

                        if foundQuote and foundBase:
                            break
                    logging.info('[BaseTrader] New account data pulled, wallets updated. [{0}]'.format(self.print_pair))

            self.prices = {
                    'lastPrice':candles[0][4],
                    'askPrice':books_data['a'][0][0],
                    'bidPrice':books_data['b'][0][0]}

            if (self.btc_wallet[0] <= self.base_mac and self.trade_information['orderType']['B'] == 'WAIT'):
                self.runtime_state = 'STANDBY'

            if self.runtime_state == 'STANDBY' and self.btc_wallet[0] > self.base_mac:
                self.runtime_state = 'RUN'

            if not self.runtime_state in ['STANDBY', 'COMPLETED_TRADE', 'FORCE_STANDBY', 'FORCE_PAUSE']:
                tInfo = self.trade_information

                ## Find out the status on a order that is PLACED.
                if socket_buffer_symbol != None:
                    self._order_status_manager(socket_buffer_symbol)

                ## If the state is not on standby then check the trade conditions.
                if self.runtime_state == 'RUN' and self.trade_information['canOrder'] == True:
                    self._trade_manager(indicators, candles)

            current_localtime = time.localtime()
            self.last_update_time = '{0}:{1}:{2}'.format(current_localtime[3], current_localtime[4], current_localtime[5])

            if self.runtime_state == 'COMPLETED_TRADE':
                self.runtime_state = 'RUN'

            if self.runtime_state == 'SETUP':
                self.runtime_state = 'RUN'
            time.sleep(0.5)
        

    def _order_status_manager(self, socket_buffer_symbol):
        '''
        This is the manager for all and any active orders.

        -> Check orders (Test/Real).
            This checks both the buy and sell side for test orders and updates the trader accordingly.

        -> Monitor trade outcomes.
            Monitor and note down the outcome of trades for keeping track of progress.
        '''
        if self.base_asset == 'BTC':
            token = self.quote_asset
        else:
            token = self.base_asset

        if 'executionReport' in socket_buffer_symbol:
            side = 'BUY' if self.trade_information['orderType']['S'] == None else 'SELL'
            trade_done = False

            recentOrder = socket_buffer_symbol['executionReport']

            if side == 'BUY':
                if (not(self.btc_base_pair) and recentOrder['S'] == 'BUY') or (self.btc_base_pair and recentOrder['S'] == 'SELL'):
                    self.trade_information['buyPrice'] = float(recentOrder['L'])
                    if recentOrder['X'] == 'FILLED':
                        trade_done = True
                    elif recentOrder['X'] == 'PARTIALLY_FILLED':
                        self.trade_information['orderStatus']['S'] = 'LOCKED'

            elif side == 'SELL':
                if (self.btc_base_pair and recentOrder['S'] == 'BUY') or (not(self.btc_base_pair) and recentOrder['S'] == 'SELL'):
                    self.trade_information['sellPrice'] = float(recentOrder['L'])
                    if recentOrder['X'] == 'FILLED':
                        trade_done = True
                    elif recentOrder['X'] == 'PARTIALLY_FILLED':
                        self.trade_information['orderStatus']['B'] = 'LOCKED'
        else:
            return

        ## Monitor trade outcomes.
        if trade_done and self.trading_asset:
            print(recentOrder)
            print('Finished {0} trade for {1}'.format(side, self.print_pair))
            tInfo = self.trade_information

            if side == 'BUY':
                # Here all the necissary variables and values are added to signal a completion on a buy trade.
                self.trade_information['tokenBase'] = self.trading_asset[0]
                self.buyTime = time.time()
                self._setup_sell()

                logging.info('[BaseTrader] Completed buy order. [{0}]'.format(self.print_pair))
            elif side == 'SELL':
                # Here all the necissary variables and values are added to signal a completion on a sell trade.
                fee = self.base_mac * COMMISION_FEE

                sellTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                buyTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.buyTime))

                if self.base_asset == 'BTC':
                    outcome = float('{0:.8f}'.format(((tInfo['tokenBase']/self.prices['lastPrice'])-self.base_mac)-fee))
                else:
                    outcome = float('{0:.8f}'.format(((tInfo['sellPrice']-tInfo['buyPrice'])*tInfo['tokenBase'])-fee))

                with open(self.orders_log_path, 'a') as file:
                    buyResp = 'Buy order, price: {0:.8f}, time: {1} [{2}] | '.format(tInfo['buyPrice'], buyTime, self.orderDesc['B'])
                    sellResp = 'Sell order, price: {0:.8f}, time: {1} [{2}], outcome: {3:.8f} [{4}]'.format(tInfo['sellPrice'], sellTime, self.orderDesc['S'], outcome, self.symbol)
                    file.write(buyResp+sellResp+'\n')
                    file.close()

                self.trade_information['overall'] += outcome
                self.trade_information['#Trades'] += 1

                self._setup_buy()
                self.runtime_state = 'COMPLETED_TRADE'
                logging.info('[BaseTrader] Completed sell order. [{0}]'.format(self.print_pair))


    def _trade_manager(self, indicators, candles):
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
        updateOrder = False
        order = None

        if tInfo['orderType']['S'] and tInfo['orderStatus']['S'] != 'LOCKED':
            ## Manage SELL orders/check conditions.
            logging.debug('[BaseTrader] Checking for Sell condition. [{0}]'.format(self.print_pair))

            new_order = TC.sell_conditions(
                self.custom_conditional_data,
                tInfo,
                indicators, 
                self.prices,
                candles)

            self.orderDesc['S'] = new_order['description']
            orderType = new_order['orderType']

            if orderType == 'Signal' and new_order['ptype'] == 'LIMIT' and new_order['price'] != tInfo['sellPrice']:
                updateOrder = True

            if self.trade_information['orderType']['S'] != orderType or updateOrder:
                if orderType == 'SIGNAL':
                    # If SIGNAL is set then place a order.
                    order = new_order
                elif orderType == 'STOP_LOSS':
                    # If STOP_LOSS is set then place a stop loss.
                    order = new_order
                elif orderType == 'WAIT':
                    # If WAIT is set then remove all orders and change order type to wait.
                    cancel_order_results = self.rest_api._cancel_order(self.order_id['S'])
                    logging.debug('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, str(cancel_order_results)))
                    self.trade_information['orderStatus']['S'] = None
                    self.trade_information['orderType']['S'] = 'WAIT'
                else:
                    logging.critical('[BaseTrader] The order type [{0}] is not currently available.'.format(orderType))

        elif tInfo['orderType']['B'] and tInfo['orderStatus']['B'] != 'LOCKED' and self.runtime_state != 'FORCE_PREVENT_BUY':
            ## Manage BUY orders/check conditions.
            logging.debug('[BaseTrader] Checking for Buy condition. [{0}]'.format(self.print_pair))

            new_order = TC.buy_conditions(
                self.custom_conditional_data,
                tInfo,
                indicators, 
                self.prices,
                candles)

            self.orderDesc['B'] = new_order['description']
            orderType = new_order['orderType']

            if orderType == 'Signal' and new_order['ptype'] == 'LIMIT' and new_order['price'] != tInfo['buyPrice']:
                updateOrder = True

            if self.trade_information['orderType']['B'] != orderType or updateOrder:
                if orderType == 'SIGNAL':
                    # If SIGNAL is set then place a order.
                    order = new_order
                elif orderType == 'WAIT':
                    # If WAIT is set then remove all orders and change order type to wait.
                    cancel_order_results = self.rest_api._cancel_order(self.order_id['B'])
                    logging.debug('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, str(cancel_order_results)))
                    self.trade_information['orderStatus']['B'] = None
                    self.trade_information['orderType']['B'] = 'WAIT'

                else:
                    logging.critical('[BaseTrader] The order type [{0}] is not currently available.'.format(orderType))

        ## Place Market Order.
        if order:
            logging.info('[BaseTrader] {0} placing order type {1}.'.format(self.print_pair, orderType))
            order_results = self._place_order(order)

            if order_results != None:
                logging.debug('[BaseTrader] {0} order placement results:\n{1}'.format(self.print_pair, str(order_results)))
                if order['side'] == 'BUY':
                    self.trade_information['orderType']['B'] = orderType
                    self.trade_information['orderStatus']['B'] = 'PLACED'
                else:
                    self.trade_information['orderType']['S'] = orderType
                    self.trade_information['orderStatus']['S'] = 'PLACED'


    def _place_order(self, order):
        ''' place order '''
        quantity = None

        if order['side'] == 'BUY':
            if self.btc_base_pair and INVERT_FOR_BTC_FIAT:
                quantity = float(self.trade_information['currencyLeft'])
            else:
                quantity = float(self.trade_information['currencyLeft'])/float(self.prices['bidPrice'])

            if self.order_id['B']:
                cancel_order_results = self._cancel_order(self.order_id['B'])
                logging.debug('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, str(cancel_order_results)))
                self.order_id['B'] = None

        elif order['side'] == 'SELL':
            if self.trading_asset != None:
                if self.btc_base_pair and INVERT_FOR_BTC_FIAT:
                    quantity = float(self.trading_asset[0])/float(self.prices['bidPrice'])
                else:
                    quantity = float(self.trading_asset[0])

                if self.order_id['S']:
                    cancel_order_results = self._cancel_order(self.order_id['S'])
                    logging.debug('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, str(cancel_order_results)))
                    self.order_id['S'] = None
            else:
                return

        if quantity:
            quantity = '{0:.{1}f}'.format(quantity, self.rules['LOT_SIZE'])

        if self.btc_base_pair and INVERT_FOR_BTC_FIAT:
            if order['side'] == 'BUY':
                side = 'SELL'
            else:
                side = 'BUY'
        else:
            side = order['side']

        if order['ptype'] == 'MARKET':
            logging.info('[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3}'.format(
                self.print_pair, 
                order['side'], 
                order['ptype'], 
                quantity))

            return(self.rest_api.place_order('SPOT', 
                symbol=self.symbol, 
                side=side, 
                type=order['ptype'], 
                quantity=quantity))

        elif order['ptype'] == 'LIMIT':
            logging.info('[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3} price:{4}'.format(
                self.print_pair, 
                order['side'], 
                order['ptype'], 
                quantity,
                order['price']))

            return(self.rest_api.place_order('SPOT', 
                symbol=self.symbol, 
                side=side, 
                type=order['ptype'], 
                timeInForce='GTC', 
                quantity=quantity,
                price=order['price']))

        elif order['ptype'] == 'STOP_LOSS_LIMIT':
            logging.info('[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3} price:{4}, stopPrice:{5}'.format(
                self.print_pair, 
                order['side'], 
                order['ptype'], 
                quantity,
                order['price'],
                order['price']))

            return(self.rest_api.place_order('SPOT', 
                symbol=self.symbol, 
                side=side, 
                type=order['ptype'], 
                timeInForce='GTC', 
                quantity=quantity,
                price=order['price'],
                stopPrice=order['price']))


    def _cancel_order(self, order_id):
        ''' cancel orders '''
        return(self.rest_api.cancel_order('SPOT', symbol=self.symbol, orderId=order_id))


    def _setup_sell(self):
        ''' Used to setup the trader for selling after a buy has been completed. '''
        self.trade_information['crossedThreshold'] = False
        self.trade_information['orderStatus']['B'] = None
        self.trade_information['currencyLeft'] = 0

        self.trade_information['orderType']['B'] = None
        self.trade_information['orderType']['S'] = 'WAIT'
        self.trade_information['updateOrder'] = True


    def _setup_buy(self):
        ''' Used to setup the trader for buying after a sell has been completed. '''
        self.trade_information['orderStatus']['S'] = None
        self.trade_information['sellPrice'] = 0
        self.trade_information['buyPrice'] = 0
        self.trade_information['currencyLeft'] = self.base_mac

        self.trade_information['orderType']['B'] = 'WAIT'
        self.trade_information['orderType']['S'] = None


    def get_trader_data(self):
        ''' This block is called to return data about the current trader '''
        return({
            'tradeInfo':self.trade_information,
            'prices':self.prices,
            'base':self.base_asset,
            'quote':self.quote_asset,
            'symbol':self.symbol,
            'state':self.runtime_state,
            'lastUpdate':self.last_update_time
        })
