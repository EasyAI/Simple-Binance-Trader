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
        
        # Holds the trade indicators.
        self.indicators = {}

        self.orders_log_path = 'order_log.txt'

        # Force sell is set if a active trade is found on script reset.
        self.force_sell = False

        self.run_type       = None
        self.market_type    = None

        # Holds the current symbolic pair of the market being traded.
        self.btc_base_pair  = True if base_asset == 'BTC' else False
        self.print_pair     = '{0}-{1}'.format(quote_asset, base_asset)
        self.symbol         = symbol
        self.quote_asset    = quote_asset
        self.base_asset     = base_asset

        self.trade_only_one = True
        
        # Holds current market information.
        self.prices = {
            'lastPrice':0,   # Last price.
            'askPrice':0,    # Ask price.
            'bidPrice':0}    # Bid price.

        self.custom_conditional_data = {}

        self.trade_information = {
            'loan_cost':{'long':False, 'short':False},
            'loan_id':{'long':False, 'short':False},
            'can_order':{'long':False, 'short':False},
            'buy_price':{'long':0, 'short':0},          # 'buy_price' this holds the buy price for the bot.
            'sell_price':{'long':0, 'short':0},         # 'sell_price' this holds the sell price of the bot. 
            'long_order_type':{'B':'WAIT', 'S':None},   # B/S will represent BUY/SELL or entry/exit.
            'long_order_status':{'B':None, 'S':None},   # 
            'long_order_desc':{'B':None, 'S':None},     #
            'long_order_id':{'B':None,'S':None},        #
            'short_order_type':{'B':'WAIT', 'S':None},  # 
            'short_order_status':{'B':None, 'S':None},  #
            'short_order_desc':{'B':None, 'S':None},    #
            'short_order_id':{'B':None,'S':None},       #
            'market_states':{'long':None, 'short':None} #
        }

        # Holds information on current/past trades of the trader.
        self.trader_stats = {
            'wallet_pair':None,
            'last_update_time':0,
            'runtime_state':'STOP',
            'base_mac':0,                           #
            'buy_time': {'long':0, 'short':0},       #
            'currency_left':{'long':0, 'short':0},  # 'currency_left' this holds the currency the bot has left to trade.
            'tester_quantity':{'long':0, 'short':0},# 
            'tokens_holding':{'long':0, 'short':0}, # 'tokens_holding' this holds the base tokens bought.
            '#Trades':{'long':0, 'short':0},        # '#Trades' this holds the number of FULL trades made by this market.
            'overall':{'long':0, 'short':0}         # 'overall' this holds the overall outcomes for this markets trades.
        }        

        # Holds the rules required for the market.
        self.rules = filters


    def start(self, market_type, run_type, MAC, wallet_pair, reload_settings=False, open_orders=None):
        '''
        Start the trader.
        Requires: MAC (Max Allowed Currency, the max amount the trader is allowed to trade with in BTC).

        -> Check for previous trade.
            If a recent, not closed traded is seen, or leftover currency on the account over the min to place order then set trader to sell automatically.
        
        ->  Start the trader thread. 
            Once all is good the trader will then start the thread to allow for the market to be monitored.
        '''
        logging.debug('[BaseTrader] Starting trader {0}.'.format(self.print_pair))
        sock_symbol = self.base_asset+self.quote_asset

        while True:
            if self.socket_api.get_live_candles()[sock_symbol] and ('a' in self.socket_api.get_live_depths()[sock_symbol]):
                break

        self.run_type                       = run_type
        self.market_type                    = market_type
        self.trader_stats['runtime_state']  = 'SETUP'
        self.trader_stats['wallet_pair']    = wallet_pair
        
        if not(reload_settings):
            if self.rules['isFiat'] == True and self.rules['invFiatToBTC']:
                MAC = self.socket_api.get_live_candles()[sock_symbol]*float(MAC)
            else:
                MAC = float(MAC)

            self.trader_stats['base_mac']               = MAC
            self.trader_stats['currency_left']['long']  = MAC
            self.trader_stats['currency_left']['short'] = MAC

        ## Start the main of the trader in a thread.
        logging.debug('[BaseTrader] Starting trader main thread {0}.'.format(self.print_pair))
        trader_thread = threading.Thread(target=self._main)
        trader_thread.start()
        return(True)


    def stop(self):
        ''' 
        Stop the trader.

        -> Trader cleanup.
            To gracefully stop the trader and cleanly eliminate the thread as well as market orders.
        '''
        logging.debug('[BaseTrader] Stopping trader {0}.'.format(self.print_pair))

        if self.trade_information['order_type']['S'] == None:
            self.trade_information['order_status']['B'] = 'FORCE_PREVENT_BUY'

            while True:
                if self.trade_information['order_type']['S'] == None:
                    break
                time.sleep(10)

        else:
            self.rest_api.cancel_open_orders('ALL', self.symbol)

        self.trader_stats['runtime_state'] = 'STOP'
        return(True)


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
        last_wallet_update_time = 0

        if self.market_type == 'SPOT':
            market_types = ['long']
        elif self.market_type  == 'MARGIN':
            market_types = ['long', 'short']

        while self.trader_stats['runtime_state'] != 'STOP':
            ## Call the update function for the trader.
            candles = self.socket_api.get_live_candles()[sock_symbol]
            books_data = self.socket_api.get_live_depths()[sock_symbol]
            indicators = TC.technical_indicators(candles)
            self.indicators = indicators
            logging.debug('[BaseTrader] Collected trader data from socket. [{0}]'.format(self.print_pair))

            socket_buffer_global = self.socket_api.socketBuffer

            if sock_symbol in self.socket_api.socketBuffer:
                socket_buffer_symbol = self.socket_api.socketBuffer[sock_symbol]
            else:
                socket_buffer_symbol = None

            if self.run_type == 'REAL':
                ## Pull account balance data via the SPOT user data stream endpoint to update wallet pair information.
                if 'outboundAccountInfo' in socket_buffer_global:
                    if last_wallet_update_time != socket_buffer_global['outboundAccountInfo']['E']:
                        self.trader_stats['wallet_pair'], last_wallet_update_time = self.update_wallets(socket_buffer_global)
                            
            self.prices = {
                'lastPrice':candles[0][4],
                'askPrice':books_data['a'][0][0],
                'bidPrice':books_data['b'][0][0]}

            if not self.trader_stats['runtime_state'] in ['STANDBY', 'FORCE_STANDBY', 'FORCE_PAUSE']:
                ## Call for custom conditions that can be used for more advanced managemenet of the trader.
                self.custom_conditional_data, self.trade_information = TC.other_conditions(
                    self.custom_conditional_data, 
                    self.trade_information, 
                    candles,
                    indicators, 
                    self.print_pair,
                    self.btc_base_pair)

                for market_type in market_types:
                    ## logic to force only short or long to be activly traded, both with still monitor passivly tho.
                    if self.trade_only_one:
                        if (self.trade_information['long_order_type']['B'] != 'WAIT' or self.trade_information['long_order_type']['S'] != None) and market_type == 'short':
                            continue
                        elif (self.trade_information['short_order_type']['B'] != 'WAIT' or self.trade_information['short_order_type']['S'] != None) and market_type == 'long':
                            continue

                    logging.debug('[BaseTrader] {0} Checking for {1}'.format(self.print_pair, market_type))

                    ## For managing active orders.
                    if socket_buffer_symbol != None or self.run_type == 'TEST':
                        self._order_status_manager(market_type, socket_buffer_symbol)

                    ## For managing the placement of orders/condition checking.
                    if self.trade_information['can_order'][market_type] == True:
                        if self.trader_stats['runtime_state'] == 'RUN' and self.trade_information['market_states'][market_type] == 'TRADING':
                            self._trade_manager(market_type, indicators, candles)

                        if self.trade_information['market_states'][market_type] == 'COMPLETE_TRADE':
                            self.trade_information['market_states'][market_type] = 'TRADING'

                    if self.trader_stats['runtime_state'] == 'SETUP':
                        self.trade_information['market_states'][market_type] = 'TRADING'

                    time.sleep(0.2)

            current_localtime = time.localtime()
            self.trader_stats['last_update_time'] = '{0}:{1}:{2}'.format(current_localtime[3], current_localtime[4], current_localtime[5])

            if self.trader_stats['runtime_state'] == 'SETUP':
                self.trader_stats['runtime_state'] = 'RUN'

            if self.run_type == 'REAL':
                pass
        

    def _order_status_manager(self, market_type, socket_buffer_symbol):
        '''
        This is the manager for all and any active orders.

        -> Check orders (Test/Real).
            This checks both the buy and sell side for test orders and updates the trader accordingly.

        -> Monitor trade outcomes.
            Monitor and note down the outcome of trades for keeping track of progress.
        '''
        current_order_type = '{0}_order_type'.format(market_type)
        current_order_desc = '{0}_order_desc'.format(market_type)
        current_order_id = '{0}_order_id'.format(market_type)
        current_order_status = '{0}_order_status'.format(market_type)

        active_trade = False
        if self.run_type == 'REAL':
            # Manage order reports sent via the socket.
            if 'executionReport' in socket_buffer_symbol:
                order_seen = socket_buffer_symbol['executionReport']
                tInfo = self.trade_information
                all_active_orders = [tInfo['long_order_id']['B'], tInfo['long_order_id']['S'], tInfo['short_order_id']['B'], tInfo['short_order_id']['S']]

                if not(order_seen['i'] in all_active_orders):
                    # Blocked is used to allow force buys.
                    if market_type == 'long':
                        active_trade = True
                else:
                    # Manage trader placed orders via order ID's to prevent order conflict.
                    all_mt_trades = [tInfo[current_order_id]['B'], tInfo[current_order_id]['S']]
                    if order_seen['i'] in all_mt_trades:
                        active_trade = True
        else:
            # Basic update for test orders.
            if self.trade_information[current_order_status]['B'] == 'PLACED' or self.trade_information[current_order_status]['S'] == 'PLACED':
                active_trade = True
                order_seen = None

        if active_trade:
            # Determine the current state of an order.
            tInfo = self.trade_information
            side = 'BUY' if tInfo[current_order_type]['S'] == None else 'SELL'
            trade_done, tokens_bought = self._check_active_trade(side, market_type, order_seen)
        else:
            return

        ## Monitor trade outcomes.
        if trade_done:
            if self.run_type == 'REAL':
                print(order_seen)
            print('Finished {0} trade for {1}'.format(side, self.print_pair))

            if side == 'BUY':
                # Here all the necissary variables and values are added to signal a completion on a buy trade.
                self.trader_stats['tokens_holding'][market_type] = tokens_bought
                self.trader_stats['buy_time'][market_type] = time.time()
                self._setup_sell(market_type)

                logging.info('[BaseTrader] Completed buy order. [{0}]'.format(self.print_pair))

            elif side == 'SELL':
                # Here all the necissary variables and values are added to signal a completion on a sell trade.
                tokens_holding = self.trader_stats['tokens_holding'][market_type]
                fee = tokens_holding*COMMISION_FEE

                sellTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                buyTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.trader_stats['buy_time'][market_type]))

                if market_type == 'short':
                    if self.run_type == 'REAL':
                        loan_repay_result = self.rest_api.repay_loan(asset=self.base_asset, amount=self.trade_information['loan_cost'][market_type])

                if self.rules['isFiat'] == True and self.rules['invFiatToBTC']:
                    outcome = float('{0:.8f}'.format(((tInfo['sell_price'][market_type]-tInfo['buy_price'][market_type])*(tokens_holding/tInfo['sell_price'][market_type]))))
                else: 
                    outcome = float('{0:.8f}'.format(((tInfo['sell_price'][market_type]-tInfo['buy_price'][market_type])*tokens_holding)))

                with open(self.orders_log_path, 'a') as file:
                    buyResp = 'marketType:{3}, Buy order, price: {0:.8f}, time: {1} [{2}] | '.format(tInfo['buy_price'][market_type], buyTime, tInfo[current_order_desc]['B'], market_type)
                    sellResp = 'Sell order, price: {0:.8f}, time: {1} [{2}], outcome: {3:.8f} [{4}]'.format(tInfo['sell_price'][market_type], sellTime, tInfo[current_order_desc]['S'], outcome, self.symbol)
                    file.write(buyResp+sellResp+'\n')
                    file.close()

                self.trader_stats['overall'][market_type] += outcome
                self.trader_stats['#Trades'][market_type] += 1

                self._setup_buy(market_type)
                self.trade_information['market_states'][market_type] = 'COMPLETE_TRADE'
                logging.info('[BaseTrader] Completed sell order. [{0}]'.format(self.print_pair))


    def _check_active_trade(self, side, market_type, order_seen):
        tInfo = self.trade_information
        trade_done = False
        tokens_bought = None
        current_order_status = '{0}_order_status'.format(market_type)
            
        if side == 'BUY':
            if self.run_type == 'REAL':
                if order_seen['S'] == 'BUY' or (market_type == 'short' and order_seen['S'] == 'SELL'):
                    self.trade_information['buy_price'][market_type] = float(order_seen['L'])

                    if market_type == 'long':
                        target_wallet = self.base_asset
                        target_quantity = float(order_seen['q'])
                    elif market_type == 'short':
                        target_wallet = self.quote_asset
                        target_quantity = float(order_seen['q'])*float(order_seen['L'])

                    if order_seen['X'] == 'FILLED' and target_wallet in self.trader_stats['wallet_pair']:
                        wallet_pair = self.trader_stats['wallet_pair']
                        if wallet_pair[target_wallet][0] >= target_quantity:
                            trade_done = True
                            tokens_bought = wallet_pair[self.base_asset][0]
                    elif order_seen['X'] == 'PARTIALLY_FILLED' and tInfo[current_order_status]['B'] != 'LOCKED':
                        self.trade_information[current_order_status]['B'] = 'LOCKED'
            else:
                if market_type == 'long':
                    if tInfo['buy_price'][market_type] <= self.prices['lastPrice']:
                        trade_done = True
                        tokens_bought = self.trader_stats['tester_quantity'][market_type]
                elif market_type == 'short':
                    if tInfo['buy_price'][market_type] >= self.prices['lastPrice']:
                        trade_done = True
                        tokens_bought = self.trader_stats['tester_quantity'][market_type]

        elif side == 'SELL':
            if self.run_type == 'REAL':
                if order_seen['S'] == 'SELL' or (market_type == 'short' and order_seen['S'] == 'BUY'):
                    self.trade_information['sell_price'][market_type] = float(order_seen['L'])

                    if order_seen['X'] == 'FILLED':
                        trade_done = True
                    elif order_seen['X'] == 'PARTIALLY_FILLED' and tInfo[current_order_status]['S'] != 'LOCKED':
                        self.trade_information[current_order_status]['S'] = 'LOCKED'
            else:
                if market_type == 'long':
                    if tInfo['sell_price'][market_type] >= self.prices['lastPrice']:
                        trade_done = True
                elif market_type == 'short':
                    if tInfo['sell_price'][market_type] <= self.prices['lastPrice']:
                        trade_done = True
        return(trade_done, tokens_bought)


    def _trade_manager(self, market_type, indicators, candles):
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
        current_order_type = '{0}_order_type'.format(market_type)
        current_order_status = '{0}_order_status'.format(market_type)
        current_order_desc = '{0}_order_desc'.format(market_type)
        current_order_id = '{0}_order_id'.format(market_type)

        if tInfo[current_order_type]['S'] and tInfo[current_order_status]['S'] != 'LOCKED':
            ## Manage SELL orders/check conditions.
            logging.debug('[BaseTrader] Checking for Sell condition. [{0}]'.format(self.print_pair))

            if market_type == 'long':
                new_order = TC.long_exit_conditions(
                    self.custom_conditional_data,
                    tInfo,
                    indicators, 
                    self.prices,
                    candles,
                    self.print_pair,
                    self.btc_base_pair)
            elif market_type == 'short':
                new_order = TC.short_exit_conditions(
                    self.custom_conditional_data,
                    tInfo,
                    indicators, 
                    self.prices,
                    candles,
                    self.print_pair,
                    self.btc_base_pair)

            if not(new_order):
                return

            orderType = new_order['order_type']

            if orderType != 'WAIT':
                self.trade_information[current_order_desc]['S'] = new_order['description']
                if self.run_type == 'TEST' and new_order['ptype'] == 'MARKET':
                    updateOrder = True
                elif 'price' in new_order:
                    if 'price' in new_order:
                        new_order['price'] = '{0:.{1}f}'.format(float(new_order['price']), self.rules['TICK_SIZE'])
                        if 'stopPrice' in new_order:
                            new_order['stopPrice'] = '{0:.{1}f}'.format(float(new_order['stopPrice']), self.rules['TICK_SIZE'])
                    
                    if float(new_order['price']) != float(tInfo['sell_price'][market_type]):
                        updateOrder = True

            if self.trade_information[current_order_type]['S'] != orderType or updateOrder:
                if orderType == 'SIGNAL':
                    # If SIGNAL is set then place a order.
                    order = new_order
                elif orderType == 'STOP_LOSS':
                    # If STOP_LOSS is set then place a stop loss.
                    order = new_order
                elif orderType == 'WAIT':
                    # If WAIT is set then remove all orders and change order type to wait.
                    cancel_order_results = self._cancel_order(tInfo[current_order_id]['S'])
                    logging.debug('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, str(cancel_order_results)))
                    self.trade_information[current_order_status]['S'] = None
                    self.trade_information[current_order_type]['S'] = 'WAIT'
                else:
                    logging.critical('[BaseTrader] The order type [{0}] is not currently available.'.format(orderType))

        elif tInfo[current_order_type]['B'] and tInfo[current_order_status]['B'] != 'LOCKED' and self.trader_stats['runtime_state'] != 'FORCE_PREVENT_BUY':
            ## Manage BUY orders/check conditions.
            logging.debug('[BaseTrader] Checking for Buy condition. [{0}]'.format(self.print_pair))

            if market_type == 'long':
                new_order = TC.long_entry_conditions(
                    self.custom_conditional_data,
                    tInfo,
                    indicators, 
                    self.prices,
                    candles,
                    self.print_pair,
                    self.btc_base_pair)
            elif market_type == 'short':
                new_order = TC.short_entry_conditions(
                    self.custom_conditional_data,
                    tInfo,
                    indicators, 
                    self.prices,
                    candles,
                    self.print_pair,
                    self.btc_base_pair)

            if not(new_order):
                return

            orderType = new_order['order_type']

            if orderType != 'WAIT':
                self.trade_information[current_order_desc]['B'] = new_order['description']
                if self.run_type == 'TEST' and new_order['ptype'] == 'MARKET':
                    updateOrder = True
                elif 'price' in new_order:
                    if 'price' in new_order:
                        new_order['price'] = '{0:.{1}f}'.format(float(new_order['price']), self.rules['TICK_SIZE'])
                        if 'stopPrice' in new_order:
                            new_order['stopPrice'] = '{0:.{1}f}'.format(float(new_order['stopPrice']), self.rules['TICK_SIZE'])
                    
                    if float(new_order['price']) != float(tInfo['buy_price'][market_type]):
                        updateOrder = True

            if self.trade_information[current_order_type]['B'] != orderType or updateOrder:
                if orderType == 'SIGNAL':
                    # If SIGNAL is set then place a order.
                    order = new_order
                elif orderType == 'WAIT':
                    # If WAIT is set then remove all orders and change order type to wait.
                    cancel_order_results = self._cancel_order(tInfo[current_order_id]['B'])
                    logging.debug('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, str(cancel_order_results)))
                    self.trade_information[current_order_status]['B'] = None
                    self.trade_information[current_order_type]['B'] = 'WAIT'
                else:
                    logging.critical('[BaseTrader] The order type [{0}] is not currently available.'.format(orderType))

        ## Place Market Order.
        if order:
            order_results = self._place_order(market_type, order)
            logging.debug('order: {0}\norder result:\n{1}'.format(order, order_results))

            if 'code' in order_results:
                ## used to catch error codes.
                return

            if order_results != None:
                logging.info('[BaseTrader] {0} Order placed for {1}.'.format(self.print_pair, orderType))
                logging.debug('[BaseTrader] {0} Order placement results:\n{1}'.format(self.print_pair, str(order_results)))

                if order['side'] == 'BUY':
                    if 'price' in order_results:
                        self.trade_information['buy_price'][market_type] = float(order_results['price'])

                    if self.run_type == 'REAL':
                        self.trade_information[current_order_id]['B'] = order_results['orderId']

                    self.trade_information[current_order_type]['B'] = orderType
                    self.trade_information[current_order_status]['B'] = 'PLACED'
                else:
                    if 'price' in order_results:
                        self.trade_information['sell_price'][market_type] = float(order_results['price'])

                    if self.run_type == 'REAL':
                        self.trade_information[current_order_id]['S'] = order_results['orderId']

                    self.trade_information[current_order_type]['S'] = orderType
                    self.trade_information[current_order_status]['S'] = 'PLACED'

                logging.info('order status: {0}'.format(current_order_status))
                logging.info('update: {0}, type: {1}, status: {2}'.format(updateOrder, orderType, self.trade_information[current_order_status]))


    def _place_order(self, market_type, order):
        ''' place order '''
        current_order_id = '{0}_order_id'.format(market_type)

        ## Setup the price to be the correct precision.

        ## Calculate the quantity amount for the BUY/SELL side for long/short real/test trades.
        quantity = None
        if order['side'] == 'BUY':
            quantity = float(self.trader_stats['currency_left'][market_type])/float(self.prices['bidPrice'])

            if self.run_type == 'REAL':
                if self.trade_information[current_order_id]['B']:
                    print("order id:", self.trade_information[current_order_id]['B'])
                    cancel_order_results = self._cancel_order(self.trade_information[current_order_id]['B'])
                    logging.info('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, str(cancel_order_results)))

        elif order['side'] == 'SELL':
            if self.run_type == 'REAL':
                tokens_holding = self.trader_stats['wallet_pair'][self.base_asset][0]
            else:
                tokens_holding = self.trader_stats['tokens_holding'][market_type]

            if market_type == 'long':
                quantity = float(tokens_holding)
            elif market_type == 'short':
                if self.run_type == 'REAL':
                    for asset in self.rest_api.get_account(api_type='MARGIN')['userAssets']:
                        if asset['asset'] == self.base_asset:
                            quantity = float(asset['borrowed'])+float(asset['interest'])
                            break
                else:
                    quantity = float(tokens_holding)

            if self.run_type == 'REAL':
                if self.trade_information[current_order_id]['S']:
                    print("order id:", self.trade_information[current_order_id]['S'])
                    cancel_order_results = self._cancel_order(self.trade_information[current_order_id]['S'])
                    logging.info('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, str(cancel_order_results)))
        else:
            return
        
        logging.info('wallet pair: {0}'.format(self.trader_stats['wallet_pair']))
        logging.info('quantity: {0}'.format(quantity))

        ## Setup the quantity to be the correct precision.
        if quantity:
            split_quantity = str(quantity).split('.')
            quantity = float(split_quantity[0]+'.'+split_quantity[1][:self.rules['LOT_SIZE']])

        logging.info('quantity: {0}'.format(quantity))

        ## Place orders for both SELL/BUY sides for both TEST/REAL run types.
        if self.run_type == 'REAL':

            ## Convert BUY to SELL if the order is a short (for short orders are inverted)
            if market_type == 'long':
                side = order['side']
            elif market_type == 'short':
                if order['side'] == 'BUY':
                    ## Calculate the quantity required for a short loan.
                    loan_get_result = self.rest_api.apply_for_loan(asset=self.base_asset, amount=quantity)
                    print(self.base_asset, quantity)
                    print(loan_get_result)
                    self.trade_information['loan_id'][market_type] = loan_get_result['tranId']
                    self.trade_information[current_order_id]['S'] = None
                    self.trade_information['loan_cost'][market_type] = quantity
                    side = 'SELL'
                else:
                    side = 'BUY'

            if self.rules['isFiat'] == True and self.rules['invFiatToBTC']:
                side = 'SELL' if order['side'] == 'BUY' else 'BUY'

            if order['ptype'] == 'MARKET':
                logging.info('[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3}'.format(
                    self.print_pair, 
                    order['side'], 
                    order['ptype'], 
                    quantity))

                return(self.rest_api.place_order(self.market_type, 
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

                return(self.rest_api.place_order(self.market_type, 
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
                    order['stopPrice']))

                return(self.rest_api.place_order(self.market_type, 
                    symbol=self.symbol, 
                    side=side, 
                    type=order['ptype'], 
                    timeInForce='GTC', 
                    quantity=quantity,
                    price=order['price'],
                    stopPrice=order['price']))

        else:
            if order['ptype'] == 'MARKET':
                price = self.prices['lastPrice']
            else:
                price = order['price']
            self.trader_stats['tester_quantity'][market_type] = float(quantity)

            return({'action':'PLACED_TEST_ORDER', 'price':price})


    def _cancel_order(self, order_id):
        ''' cancel orders '''
        if self.run_type == 'REAL':
            return(self.rest_api.cancel_order(self.market_type, symbol=self.symbol, orderId=order_id))
        return('CANCLED_TEST_ORDER')


    def _setup_sell(self, market_type):
        ''' Used to setup the trader for selling after a buy has been completed. '''
        current_order_type = '{0}_order_type'.format(market_type)
        current_order_status = '{0}_order_status'.format(market_type)
        current_order_id = '{0}_order_id'.format(market_type)

        self.trader_stats['currency_left'][market_type]     = 0

        self.trade_information[current_order_id]['B']       = None
        self.trade_information[current_order_status]['B']   = None
        self.trade_information[current_order_type]['B']     = None
        self.trade_information[current_order_type]['S']     = 'WAIT'


    def _setup_buy(self, market_type):
        ''' Used to setup the trader for buying after a sell has been completed. '''
        current_order_type = '{0}_order_type'.format(market_type)
        current_order_status = '{0}_order_status'.format(market_type)
        current_order_desc = '{0}_order_desc'.format(market_type)
        current_order_id = '{0}_order_id'.format(market_type)

        self.trade_information['sell_price'][market_type]   = 0
        self.trade_information['buy_price'][market_type]    = 0
        self.trader_stats['currency_left'][market_type]     = self.trader_stats['base_mac']
        self.trader_stats['tokens_holding'][market_type]    = 0

        self.trade_information[current_order_id]['S']       = None
        self.trade_information[current_order_desc]['S']     = None
        self.trade_information[current_order_status]['S']   = None
        self.trade_information[current_order_type]['S']     = None
        self.trade_information[current_order_desc]['B']     = None
        self.trade_information[current_order_type]['B']     = 'WAIT'


    def get_trader_data(self):
        ''' This block is called to return data about the current trader '''
        return({
            'market':self.print_pair,
            'customConditional':self.custom_conditional_data,
            'tradeInfo':self.trade_information,
            'traderStats':self.trader_stats,
            'prices':self.prices,
            'rules':self.rules
        })


    def check_open_order(self, open_orders):
        pass


    def update_wallets(self, socket_buffer_global):
        last_wallet_update_time = socket_buffer_global['outboundAccountInfo']['E']
        foundBase = False
        foundQuote = False
        wallet_pair = {}

        for wallet in socket_buffer_global['outboundAccountInfo']['B']:
            if wallet['a'] == self.base_asset:
                wallet_pair.update({self.base_asset:[float(wallet['f']), float(wallet['l'])]})
                foundBase = True
            elif wallet['a'] == self.quote_asset:
                wallet_pair.update({self.quote_asset:[float(wallet['f']), float(wallet['l'])]})
                foundQuote = True

            if foundQuote and foundBase:
                break

        if not(foundBase):
            wallet_pair.update({self.base_asset:[0.0, 0.0]})
        if not(foundQuote):
            wallet_pair.update({self.quote_asset:[0.0, 0.0]})

        logging.info('[BaseTrader] New account data pulled, wallets updated. [{0}]'.format(self.print_pair))
        return(wallet_pair, last_wallet_update_time)