#! /usr/bin/env python3
import os
import sys
import copy
import time
import logging
import datetime
import threading
import trader_configuration as TC

MULTI_DEPTH_INDICATORS = ['ema', 'sma', 'rma']
TRADER_SLEEP = 1

# Base commission fee with binance.
COMMISION_FEE = 0.00075

# Base layout for market pricing.
BASE_TRADE_PRICE_LAYOUT = {
    'lastPrice':0,           # Last price seen for the market.
    'askPrice':0,            # Last ask price seen for the market.
    'bidPrice':0             # Last bid price seen for the market.
}

# Base layout for trader state.
BASE_STATE_LAYOUT = {
    'base_currency':0.0,     # The base mac value used as referance.
    'force_sell':False,      # If the trader should dump all tokens.
    'runtime_state':None,    # The state that actual trader object is at.
    'last_update_time':0     # The last time a full look of the trader was completed.
}

# Base layout used by the trader.
BASE_MARKET_LAYOUT = {
    'can_order':True,        # If the bot is able to trade in the current market.
    'price':0.0,             # The price related to BUY.
    'buy_price':0.0,         # Buy price of the asset.
    'stopPrice':0.0,         # The stopPrice relate
    'stopLimitPrice':0.0,    # The stopPrice relate
    'tokens_holding':0.0,    # Amount of tokens being held.
    'order_point':None,      # Used to visulise complex stratergy progression points.
    'order_id':None,         # The ID that is tied to the placed order.
    'order_status':0,        # The type of the order that is placed
    'order_side':'BUY',      # The status of the current order.
    'order_type':'WAIT',     # Used to show the type of order
    'order_description':0,   # The description of the order.
    'order_market_type':None,# The market type of the order placed.
    'market_status':None     # Last state the market trader is.    
}

# Market extra required data.
TYPE_MARKET_EXTRA = {
    'loan_cost':0,           # Loan cost.
    'loan_id':None,          # Loan id.
}

class BaseTrader(object):
    def __init__(self, quote_asset, base_asset, rest_api, socket_api=None, data_if=None):
        # Initilize the main trader object.
        symbol = '{0}{1}'.format(base_asset, quote_asset)

        ## Easy printable format for market symbol.
        self.print_pair = '{0}-{1}'.format(quote_asset, base_asset)
        self.quote_asset = quote_asset
        self.base_asset = base_asset

        logging.info('[BaseTrader][{0}] Initilizing trader object and empty attributes.'.format(self.print_pair))

        ## Sets the rest api that will be used by the trader.
        self.rest_api = rest_api

        if socket_api == None and data_if == None:
            logging.critical('[BaseTrader][{0}] Initilization failed, bot must have either socket_api OR data_if set.'.format(self.print_pair))
            return

        ## Setup socket/data interface.
        self.data_if = None
        self.socket_api = None

        if socket_api:
            ### Setup socket for live market data trading.
            self.candle_enpoint = socket_api.get_live_candles
            self.depth_endpoint = socket_api.get_live_depths
            self.socket_api = socket_api
        else:
            ### Setup data interface for past historic trading.
            self.data_if = data_if
            self.candle_enpoint = data_if.get_candle_data
            self.depth_endpoint = data_if.get_depth_data

        ## Setup the default path for the trader by market beeing traded.
        self.orders_log_path = 'logs/order_{0}_log.txt'.format(symbol)
        self.configuration = {}
        self.market_prices = {}
        self.wallet_pair = None
        self.custom_conditional_data = {}
        self.indicators = {}
        self.market_activity = {}
        self.trade_recorder = []
        self.state_data = {}
        self.rules = {}

        logging.debug('[BaseTrader][{0}] Initilized trader object.'.format(self.print_pair))


    def setup_initial_values(self, trading_type, run_type, filters):
        # Initilize trader values.
        logging.info('[BaseTrader][{0}] Initilizing trader object attributes with data.'.format(self.print_pair))

        ## Populate required settings.
        self.configuration.update({
            'trading_type':trading_type,
            'run_type':run_type,
            'base_asset':self.base_asset,
            'quote_asset':self.quote_asset,
            'symbol':'{0}{1}'.format(self.base_asset, self.quote_asset)
        })
        self.rules.update(filters)

        ## Initilize default values.
        self.market_activity.update(copy.deepcopy(BASE_MARKET_LAYOUT))
        self.market_prices.update(copy.deepcopy(BASE_TRADE_PRICE_LAYOUT))
        self.state_data.update(copy.deepcopy(BASE_STATE_LAYOUT))

        if trading_type == 'MARGIN':
            self.market_activity.update(copy.deepcopy(TYPE_MARKET_EXTRA))

        logging.debug('[BaseTrader][{0}] Initilized trader attributes with data.'.format(self.print_pair))


    def start(self, MAC, wallet_pair, open_orders=None):
        '''
        Start the trader.
        Requires: MAC (Max Allowed Currency, the max amount the trader is allowed to trade with in BTC).
        -> Check for previous trade.
            If a recent, not closed traded is seen, or leftover currency on the account over the min to place order then set trader to sell automatically.
        
        ->  Start the trader thread. 
            Once all is good the trader will then start the thread to allow for the market to be monitored.
        '''
        logging.info('[BaseTrader][{0}] Starting the trader object.'.format(self.print_pair))
        sock_symbol = self.base_asset+self.quote_asset

        if self.socket_api != None:
            while True:
                if self.socket_api.get_live_candles()[sock_symbol] and ('a' in self.socket_api.get_live_depths()[sock_symbol]):
                    break

        self.state_data['runtime_state'] = 'SETUP'
        self.wallet_pair = wallet_pair
        self.state_data['base_currency'] = float(MAC)

        ## Start the main of the trader in a thread.
        threading.Thread(target=self._main).start()
        return(True)


    def stop(self):
        ''' 
        Stop the trader.
        -> Trader cleanup.
            To gracefully stop the trader and cleanly eliminate the thread as well as market orders.
        '''
        logging.debug('[BaseTrader][{0}] Stopping trader.'.format(self.print_pair))

        self.state_data['runtime_state'] = 'STOP'
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

        if self.configuration['trading_type'] == 'SPOT':
            position_types = ['LONG']
        elif self.configuration['trading_type'] == 'MARGIN':
            position_types = ['LONG', 'SHORT']

        ## Main trader loop
        while self.state_data['runtime_state'] != 'STOP':
            # Pull required data for the trader.
            candles = self.candle_enpoint(sock_symbol)
            books_data = self.depth_endpoint(sock_symbol)
            self.indicators = TC.technical_indicators(candles)
            indicators = self.strip_timestamps(self.indicators)

            logging.debug('[BaseTrader] Collected trader data. [{0}]'.format(self.print_pair))

            socket_buffer_symbol = None
            if self.configuration['run_type'] == 'REAL':

                if sock_symbol in self.socket_api.socketBuffer:
                    socket_buffer_symbol = self.socket_api.socketBuffer[sock_symbol]

                # get the global socket buffer and update the wallets for the used markets.
                socket_buffer_global = self.socket_api.socketBuffer
                if 'outboundAccountPosition' in socket_buffer_global:
                    if last_wallet_update_time != socket_buffer_global['outboundAccountPosition']['E']:
                        self.wallet_pair, last_wallet_update_time = self.update_wallets(socket_buffer_global)
            
            # Update martket prices with current data
            if books_data != None:
                self.market_prices = {
                    'lastPrice':candles[0][4],
                    'askPrice':books_data['a'][0][0],
                    'bidPrice':books_data['b'][0][0]}

            # Check to make sure there is enough crypto to place orders.
            if self.state_data['runtime_state'] == 'PAUSE_INSUFBALANCE':
                if self.wallet_pair[self.quote_asset][0] > self.state_data['base_currency']:
                    self.state_data['runtime_state'] = 'RUN' 

            if not self.state_data['runtime_state'] in ['STANDBY', 'FORCE_STANDBY', 'FORCE_PAUSE']:
                ## Call for custom conditions that can be used for more advanced managemenet of the trader.

                for market_type in position_types:
                    cp = self.market_activity

                    if cp['order_market_type'] != market_type and cp['order_market_type'] != None:
                        continue

                    ## For managing active orders.
                    if socket_buffer_symbol != None or self.configuration['run_type'] == 'TEST':
                        cp = self._order_status_manager(market_type, cp, socket_buffer_symbol)

                    ## For checking custom conditional actions
                    self.custom_conditional_data, cp = TC.other_conditions(
                        self.custom_conditional_data, 
                        cp,
                        self.trade_recorder,
                        market_type,
                        candles,
                        indicators, 
                        self.configuration['symbol'])

                    ## For managing the placement of orders/condition checking.
                    if cp['can_order'] and self.state_data['runtime_state'] == 'RUN' and cp['market_status'] == 'TRADING':
                        if cp['order_type'] == 'COMPLETE':
                            cp['order_type'] = 'WAIT'

                        tm_data = self._trade_manager(market_type, cp, indicators, candles)
                        cp = tm_data if tm_data else cp

                    if not cp['market_status']: 
                        cp['market_status'] = 'TRADING'

                    self.market_activity = cp

                    time.sleep(TRADER_SLEEP)

            current_localtime = time.localtime()
            self.state_data['last_update_time'] = '{0}:{1}:{2}'.format(current_localtime[3], current_localtime[4], current_localtime[5])

            if self.state_data['runtime_state'] == 'SETUP':
                self.state_data['runtime_state'] = 'RUN'
        

    def _order_status_manager(self, market_type, cp, socket_buffer_symbol):
        '''
        This is the manager for all and any active orders.
        -> Check orders (Test/Real).
            This checks both the buy and sell side for test orders and updates the trader accordingly.
        -> Monitor trade outcomes.
            Monitor and note down the outcome of trades for keeping track of progress.
        '''
        active_trade = False
        
        if self.configuration['run_type'] == 'REAL':
            # Manage order reports sent via the socket.
            if 'executionReport' in socket_buffer_symbol:
                order_seen = socket_buffer_symbol['executionReport']

                # Manage trader placed orders via order ID's to prevent order conflict.
                if order_seen['i'] == cp['order_id']:
                    active_trade = True

                elif cp['order_status'] == 'PLACED':
                    active_trade = True

        else:
            # Basic update for test orders.
            if cp['order_status'] == 'PLACED':
                active_trade = True
                order_seen = None

        trade_done = False
        if active_trade:
            # Determine the current state of an order.
            if self.state_data['runtime_state'] == 'CHECK_ORDERS':
                self.state_data['runtime_state'] = 'RUN'
                cp['order_status'] = None
            cp, trade_done, token_quantity = self._check_active_trade(cp['order_side'], market_type, cp, order_seen)

        ## Monitor trade outcomes.
        if trade_done:
            if self.configuration['run_type'] == 'REAL':
                print('order seen: ')
                print(order_seen)

            # Update order recorder.
            self.trade_recorder.append([time.time(), cp['price'], token_quantity, cp['order_description'], cp['order_side']])
            logging.info('[BaseTrader] Completed {0} order. [{1}]'.format(cp['order_side'], self.print_pair))

            if cp['order_side'] == 'BUY':
                cp['order_side'] = 'SELL'
                cp['order_point'] = None
                cp['buy_price'] = self.trade_recorder[-1][1]

            elif cp['order_side'] == 'SELL':
                cp['order_side'] = 'BUY'
                cp['buy_price'] = 0.0
                cp['order_point'] = None
                cp['order_market_type'] = None

                # If the trader is trading margin and the runtype is real then repay any loans.
                if self.configuration['trading_type']  == 'MARGIN':
                    if self.configuration['run_type'] == 'REAL' and cp['loan_cost'] != 0:
                        loan_repay_result = self.rest_api.margin_accountRepay(asset=self.base_asset, amount=cp['loan_cost'])

                # Format data to print it to a file.
                trB = self.trade_recorder[-2]
                trS = self.trade_recorder[-1]

                buyTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trB[0]))
                sellTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trS[0]))

                outcome = ((trS[1]-trB[1])*trS[2])

                trade_details = 'BuyTime:{0}, BuyPrice:{1:.8f}, BuyQuantity:{2:.8f}, BuyType:{3}, SellTime:{4}, SellPrice:{5:.8f}, SellQuantity:{6:.8f}, SellType:{7}, Outcome:{8:.8f}\n'.format(
                    buyTime, trB[1], trB[2], trB[3], sellTime, trS[1], trS[2], trS[3], outcome) # (Sellprice - Buyprice) * tokensSold
                with open(self.orders_log_path, 'a') as file:
                    file.write(trade_details)

                # Reset trader variables.
                cp['market_status']     = 'COMPLETE_TRADE'
            cp['order_type']        = 'COMPLETE'
            cp['price']             = 0.0
            cp['stopPrice']         = 0.0
            cp['stopLimitPrice']    = 0.0
            cp['order_id']          = None
            cp['order_status']      = None
            cp['order_description'] = None

        return(cp)


    def _check_active_trade(self, side, market_type, cp, order_seen):
        trade_done = False
        token_quantity = None

        if side == 'BUY':
            if self.configuration['run_type'] == 'REAL':
                if order_seen['S'] == 'BUY' or (market_type == 'SHORT' and order_seen['S'] == 'SELL'):
                    cp['price'] = float(order_seen['L'])

                    if market_type == 'LONG':
                        target_wallet = self.base_asset
                        target_quantity = float(order_seen['q'])
                    elif market_type == 'SHORT':
                        target_wallet = self.quote_asset
                        target_quantity = float(order_seen['q'])*float(order_seen['L'])

                    if order_seen['X'] == 'FILLED' and target_wallet in self.wallet_pair:
                        wallet_pair = self.wallet_pair
                        if wallet_pair[target_wallet][0] >= target_quantity:
                            trade_done = True
                            token_quantity = float(order_seen['q'])
                    elif order_seen['X'] == 'PARTIALLY_FILLED' and cp['order_status'] != 'LOCKED':
                        cp['order_status'] = 'LOCKED'
            else:
                if market_type == 'LONG':
                    trade_done = True if ((self.market_prices['lastPrice'] <= cp['price']) or (cp['order_type'] == 'MARKET')) else False
                elif market_type == 'SHORT':
                    trade_done = True if ((self.market_prices['lastPrice'] >= cp['price']) or (cp['order_type'] == 'MARKET')) else False
                token_quantity = cp['tokens_holding']

        elif side == 'SELL':
            if self.configuration['run_type'] == 'REAL':
                if order_seen['S'] == 'SELL' or (market_type == 'SHORT' and order_seen['S'] == 'BUY'):
                    if order_seen['X'] == 'FILLED':
                        cp['price'] = float(order_seen['L'])
                        token_quantity = float(order_seen['q'])
                        trade_done = True
                    elif order_seen['X'] == 'PARTIALLY_FILLED' and cp['order_status'] != 'LOCKED':
                        cp['order_status'] = 'LOCKED'
            else:
                if market_type == 'LONG':
                    if cp['order_type'] != 'STOP_LOSS_LIMIT':
                        trade_done = True if ((self.market_prices['lastPrice'] >= cp['price']) or (self.market_prices['lastPrice'] >= cp['stopLimitPrice']) or (cp['order_type'] == 'MARKET')) else False
                    else:
                        trade_done = True if (self.market_prices['lastPrice'] <= cp['price']) else False

                elif market_type == 'SHORT':
                    if cp['order_type'] != 'STOP_LOSS_LIMIT':
                        trade_done = True if ((self.market_prices['lastPrice'] <= cp['price']) or (cp['order_type'] == 'MARKET')) else False
                    else:
                        trade_done = True if (self.market_prices['lastPrice'] >= cp['price']) else False
                token_quantity = cp['tokens_holding']
        return(cp, trade_done, token_quantity)


    def _trade_manager(self, market_type, cp, indicators, candles):
        ''' 
        Here both the sell and buy conditions are managed by the trader.
        -
        '''


        # Check for entry/exit conditions.

        ## If order status is locked then return.
        if cp['order_status'] == 'LOCKED':
            return

        ## Select the correct conditions function dynamically.
        if cp['order_side'] == 'SELL':
            current_conditions = TC.long_exit_conditions if market_type == 'LONG' else TC.short_exit_conditions

        elif cp['order_side'] == 'BUY':
            ### If the bot is forced set to froce prevent buy return.
            if self.state_data['runtime_state'] == 'FORCE_PREVENT_BUY':
                return

            current_conditions = TC.long_entry_conditions if market_type == 'LONG' else TC.short_entry_conditions


        # Check condition check results.
        logging.debug('[BaseTrader] Checking for {0} {1} condition. [{2}]'.format(cp['order_side'], market_type, self.print_pair))
        new_order = current_conditions(self.custom_conditional_data, cp, indicators,  self.market_prices, candles, self.print_pair)
                
        ## If no new order is returned then just return.
        if not(new_order):
            return

        ## Update order point.
        if 'order_point' in new_order:
            cp['order_point'] = new_order['order_point']

        order = None

        ## Check for a new possible order type update.
        if 'order_type' in new_order:

            ### If order type update is not WAIT then update the current order OR cancel the order.
            if new_order['order_type'] != 'WAIT':
                print(new_order)
                cp['order_description'] = new_order['description']

                #### Format the prices to be used.
                if 'price' in new_order:
                    if 'price' in new_order:
                        new_order['price'] = '{0:.{1}f}'.format(float(new_order['price']), self.rules['TICK_SIZE'])
                    if 'stopPrice' in new_order:
                        new_order['stopPrice'] = '{0:.{1}f}'.format(float(new_order['stopPrice']), self.rules['TICK_SIZE'])

                    if float(new_order['price']) != cp['price']:
                        order = new_order
                else:
                    #### If the order type has changed OR the placement price has been changed update the order with the new price/type.
                    if cp['order_type'] != new_order['order_type']:
                        order = new_order

            else:
                #### Cancel the order.
                cp['order_status'] = None
                cp['order_type'] = 'WAIT'

                #### Only reset market type IF its buy or as margin allows for 2 market types.
                if cp['order_side'] == 'BUY':
                    cp['order_market_type'] = None

                #### Cancel active order if one is placed.
                if cp['order_id'] != None and new_order['order_type'] == 'WAIT':
                    cancel_order_results = self._cancel_order(cp['order_id'], cp['order_type'])
                    cp['order_id'] = None

                return(cp)

        # Place a new market order.
        if order:
            order_results = self._place_order(market_type, cp, order)
            logging.info('order: {0}\norder result:\n{1}'.format(order, order_results))

            # Error handle for binance related errors from order placement:
            if 'code' in order_results['data']:
                if order_results['data']['code'] == -2010:
                    self.state_data['runtime_state'] = 'PAUSE_INSUFBALANCE'
                elif order_results['data']['code'] == -2011:
                    self.state_data['runtime_state'] = 'CHECK_ORDERS'
                return

            logging.info('[BaseTrader] {0} Order placed for {1}.'.format(self.print_pair, new_order['order_type']))
            logging.info('[BaseTrader] {0} Order placement results:\n{1}'.format(self.print_pair, str(order_results['data'])))

            if 'type' in order_results['data']:
                if order_results['data']['type'] == 'MARKET':
                    price1 = order_results['data']['fills'][0]['price']
                else:
                    price1 = order_results['data']['price']
            else: price1 = None

            # Set the price the order was placed at.
            price2 = None
            if 'price' in order:
                price2 = float(order['price'])
                if price1 == 0.0 or price1 == None: 
                    order_price = price2
                else: order_price = price1
            else: order_price = price1

            if 'stopPrice' in order:
                cp['stopPrice'] == ['stopPrice']

            # Setup the test order quantity and setup margin trade loan.
            if order['side'] == 'BUY':
                cp['order_market_type'] = market_type

                if self.configuration['run_type'] == 'REAL':
                    if self.configuration['trading_type'] == 'MARGIN' and 'loan_id' in order_results['data']:
                        cp['loan_id'] = order_results['data']['loan_id'] 
                        cp['loan_cost'] = order_results['data']['loan_cost']
                else:
                    cp['tokens_holding'] = order_results['data']['tester_quantity']

            # Update the live order id for real trades.
            if self.configuration['run_type'] == 'REAL':
                cp['order_id'] = order_results['data']['orderId']

            cp['price']         = float(order_price)
            cp['order_type']    = new_order['order_type']
            cp['order_status']  = 'PLACED'

            logging.info('type: {0}, status: {1}'.format(new_order['order_type'], cp['order_status']))
            return(cp)


    def _place_order(self, market_type, cp, order):
        ''' place order '''

        ## Calculate the quantity amount for the BUY/SELL side for long/short real/test trades.
        quantity = None
        if order['side'] == 'BUY':
            quantity = float(self.state_data['base_currency'])/float(self.market_prices['bidPrice'])

        elif order['side'] == 'SELL':
            if 'order_prec' in order:
                quantity = ((float(order['order_prec']/100))*float(self.trade_recorder[-1][2]))
            else:
                quantity = float(self.trade_recorder[-1][2])

        if self.configuration['run_type'] == 'REAL' and cp['order_id']:
            cancel_order_results = self._cancel_order(cp['order_id'], cp['order_type'])
            if 'code' in cancel_order_results:
                return({'action':'ORDER_ISSUE', 'data':cancel_order_results})

        ## Setup the quantity to be the correct precision.
        if quantity:
            split_quantity = str(quantity).split('.')
            f_quantity = float(split_quantity[0]+'.'+split_quantity[1][:self.rules['LOT_SIZE']])

        logging.info('Order: {0}'.format(order))

        ## Place orders for both SELL/BUY sides for both TEST/REAL run types.
        if self.configuration['run_type'] == 'REAL':
            rData = {}
            ## Convert BUY to SELL if the order is a short (for short orders are inverted)
            if market_type == 'LONG':
                side = order['side']
            elif market_type == 'SHORT':
                if order['side'] == 'BUY':
                    ## Calculate the quantity required for a short loan.
                    loan_get_result = self.rest_api.margin_accountBorrow(asset=self.base_asset, amount=f_quantity)
                    rData.update({'loan_id':loan_get_result['tranId'], 'loan_cost':f_quantity})
                    side = 'SELL'
                else:
                    side = 'BUY'

            if order['order_type'] == 'OCO_LIMIT':
                logging.info('[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3} price:{4}, stopPrice:{5}, stopLimitPrice:{6}'.format(self.print_pair, order['side'], order['order_type'], f_quantity,order['price'], order['stopPrice'], order['stopLimitPrice']))
                rData.update(self.rest_api.place_order(self.configuration['trading_type'], symbol=self.configuration['symbol'], side=side, type=order['order_type'], timeInForce='GTC', quantity=f_quantity, price=order['price'], stopPrice=order['stopPrice'], stopLimitPrice=order['stopLimitPrice']))
                return({'action':'PLACED_MARKET_ORDER', 'data':rData})

            elif order['order_type'] == 'MARKET':
                logging.info('[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3}'.format(self.print_pair, order['side'], order['order_type'], f_quantity))
                rData.update(self.rest_api.place_order(self.configuration['trading_type'], symbol=self.configuration['symbol'], side=side, type=order['order_type'], quantity=f_quantity))
                return({'action':'PLACED_MARKET_ORDER', 'data':rData})

            elif order['order_type'] == 'LIMIT':
                logging.info('[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3} price:{4}'.format(self.print_pair, order['side'], order['order_type'], f_quantity, order['price']))
                rData.update(self.rest_api.place_order(self.configuration['trading_type'], symbol=self.configuration['symbol'], side=side, type=order['order_type'], timeInForce='GTC', quantity=f_quantity, price=order['price']))
                return({'action':'PLACED_LIMIT_ORDER', 'data':rData})

            elif order['order_type'] == 'STOP_LOSS_LIMIT':
                logging.info('[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3} price:{4}, stopPrice:{5}'.format(self.print_pair, order['side'], order['order_type'], f_quantity, order['price'], order['stopPrice']))
                rData.update(self.rest_api.place_order(self.configuration['trading_type'], symbol=self.configuration['symbol'], side=side, type=order['order_type'], timeInForce='GTC', quantity=f_quantity, price=order['price'], stopPrice=order['stopPrice']))
                return({'action':'PLACED_STOPLOSS_ORDER', 'data':rData})

        else:
            placed_order = {'type':'test', 'price':0, 'tester_quantity':float(f_quantity)}
            
            if order['order_type'] == 'OCO_LIMIT':
                placed_order.update({'stopPrice':order['stopPrice'], 'stopLimitPrice':order['stopLimitPrice']})

            if order['order_type'] == 'MARKET':
                placed_order.update({'price':self.market_prices['lastPrice']})
            else:
                placed_order.update({'price':order['price']})

            return({'action':'PLACED_TEST_ORDER', 'data':placed_order})


    def _cancel_order(self, order_id, order_type):
        ''' cancel orders '''
        if self.configuration['run_type'] == 'REAL':
            if order_type == 'OCO_LIMIT':
                cancel_order_result = self.rest_api.cancel_oco_order(symbol=self.configuration['symbol'])
            else:
                cancel_order_result = self.rest_api.cancel_order(self.configuration['trading_type'], symbol=self.configuration['symbol'], orderId=order_id)
            logging.debug('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, cancel_order_result))
            return(cancel_order_result)
        logging.debug('[BaseTrader] {0} cancel order.'.format(self.print_pair))
        return(True)


    def get_trader_data(self):
        ''' Access that is availble for the traders details. '''
        trader_data = {
            'market':self.print_pair,
            'configuration':self.configuration,
            'market_prices':self.market_prices,
            'wallet_pair':self.wallet_pair,
            'custom_conditions':self.custom_conditional_data,
            'market_activity':self.market_activity,
            'trade_recorder':self.trade_recorder,
            'state_data':self.state_data,
            'rules':self.rules
        }

        return(trader_data)


    def strip_timestamps(self, indicators):

        base_indicators = {}

        for ind in indicators:
            if ind in MULTI_DEPTH_INDICATORS:
                base_indicators.update({ind:{}})
                for sub_ind in indicators[ind]:
                    base_indicators[ind].update({sub_ind:[ val[1] for val in indicators[ind][sub_ind] ]})
            else:
                base_indicators.update({ind:[ val[1] for val in indicators[ind] ]})

        return(base_indicators)


    def update_wallets(self, socket_buffer_global):
        ''' Update the wallet data with that collected via the socket '''
        last_wallet_update_time = socket_buffer_global['outboundAccountPosition']['E']
        foundBase = False
        foundQuote = False
        wallet_pair = {}

        for wallet in socket_buffer_global['outboundAccountPosition']['B']:
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