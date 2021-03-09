#! /usr/bin/env python3

'''
trader
'''
import os
import sys
import copy
import time
import logging
import datetime
import threading
import trader_configuration as TC


## Base commission fee with binance.
COMMISION_FEE = 0.00075

## Supported market.
SUPPORTED_MARKETS = ['SPOT', 'MARKET']

## Base layout used by the trader.
BASE_MARKET_LAYOUT = {
    'can_order':True,        # If the bot is able to trade in the current market.
    'price':0.0,             # The price related to BUY.
    'stopPrice':0.0,         # The stopPrice relate
    'stopLimitPrice':0.0,    # The stopPrice relate
    'tokens_holding':0.0,    # Amount of tokens being held.
    'order_id':None,         # The ID that is tied to the placed order.
    'order_status':0,        # The type of the order that is placed
    'order_side':'BUY',      # The status of the current order.
    'order_type':'WAIT',         
    'order_description':0,   # The description of the order.
    'order_market_type':None,# The market type of the order placed.
    'market_status':None
}

## Market extra required data.
TYPE_MARKET_EXTRA = {
    'loan_cost':0,
    'loan_id':None,
}


class BaseTrader(object):

    def __init__(self, quote_asset, base_asset, rest_api, socket_api=None, data_if=None):
        '''
        Initilize the trader object and setup all the dataobjects that will be used by the trader object.
        '''
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

        if socket_api:
            self.candle_enpoint = socket_api.get_live_candles
            self.depth_endpoint = socket_api.get_live_depths
            self.socket_api = socket_api
            self.data_if = None
        else:
            self.socket_api = None
            self.data_if = data_if
            self.candle_enpoint = data_if.get_candle_data
            self.depth_endpoint = data_if.get_depth_data

        ## Setup the default path for the trader by market beeing traded.
        self.orders_log_path = 'logs/order_{0}_log.txt'.format(symbol)

        ## Configuration settings are held here:
        self.configuration = {}
        
        ## Market price action is held here:
        self.market_prices = {}

        ## Wallet data is stored here:
        self.wallet_pair = None

        ## Custom conditional parameters are held here:
        self.custom_conditional_data = {}

        # Here the indicators are stored.
        self.indicators = {}

        ## Here market activity is held.
        self.market_activity = {}

        ## Here all buy/sell trades will be stored
        self.trade_recorder = []

        ## Data thats used to inform about the trader:
        self.state_data = {}

        ## Market rules are set here:
        self.rules = {}

        logging.debug('[BaseTrader][{0}] Initilized trader object.'.format(self.print_pair))


    def setup_initial_values(self, trading_type, run_type, filters):
        '''
        Initilize the values for all of the trader objects.
        '''
        logging.info('[BaseTrader][{0}] Initilizing trader object attributes with data.'.format(self.print_pair))

        ## Set intial values for the trader configuration.
        self.configuration.update({
            'trading_type':trading_type,
            'run_type':run_type,
            'base_asset':self.base_asset,
            'quote_asset':self.quote_asset,
            'symbol':'{0}{1}'.format(self.base_asset, self.quote_asset)
        })

        ## Set initial values for market price.
        self.market_prices.update({
            'lastPrice':0,
            'askPrice':0,
            'bidPrice':0
        })

        ## Set initial values for state data.
        self.state_data.update({
            'base_currency':0.0,    # The base mac value used as referance.
            'force_sell':False,     # If the trader should dump all tokens.
            'runtime_state':None,   # The state that actual trader object is at.
            'last_update_time':0    # The last time a full look of the trader was completed.
        })

        self.rules.update(filters)

        self.market_activity.update(copy.deepcopy(BASE_MARKET_LAYOUT))

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
            indicators = TC.technical_indicators(candles)
            self.indicators = indicators

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

                    self.custom_conditional_data, cp = TC.other_conditions(
                        self.custom_conditional_data, 
                        cp,
                        self.trade_recorder,
                        market_type,
                        candles,
                        indicators, 
                        self.configuration['symbol'])

                    ## For managing active orders.
                    if socket_buffer_symbol != None or self.configuration['run_type'] == 'TEST':
                        cp = self._order_status_manager(market_type, cp, socket_buffer_symbol)

                    ## For managing the placement of orders/condition checking.
                    if cp['can_order'] == True and self.state_data['runtime_state'] == 'RUN' and cp['market_status'] == 'TRADING':
                        tm_data = self._trade_manager(market_type, cp, indicators, candles)
                        cp = tm_data if tm_data else cp

                    if not cp['market_status']: 
                        cp['market_status'] = 'TRADING'

                    self.market_activity = cp

                    time.sleep(.1)

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
            print(order_seen)

            # Update order recorder.
            self.trade_recorder.append([time.time(), cp['price'], token_quantity, cp['order_description'], cp['order_side']])
            logging.info('[BaseTrader] Completed {0} order. [{1}]'.format(cp['order_side'], self.print_pair))

            if cp['order_side'] == 'BUY':
                cp['order_side'] = 'SELL'

            elif cp['order_side'] == 'SELL':
                cp['order_side'] = 'BUY'
                cp['order_market_type'] = None

                # If the trader is trading margin and the runtype is real then repay any loans.
                if self.configuration['trading_type']  == 'MARGIN':
                    if self.configuration['run_type'] == 'REAL' and cp['loan_cost'] != 0:
                        loan_repay_result = self.rest_api.repay_loan(asset=self.base_asset, amount=cp['loan_cost'])

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
            cp['price']             = 0.0
            cp['stopPrice']         = 0.0
            cp['stopLimitPrice']    = 0.0
            cp['order_id']          = None
            cp['order_status']      = None
            cp['order_description'] = None
            cp['order_type']        = 'COMPLETED'

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
                            token_quantity = wallet_pair[self.base_asset][0]
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
        -> Manager Sell Conditions.
            Manage the placed sell condition as well as monitor conditions for the sell side.
        -> Manager Buy Conditions.
            Manage the placed buy condition as well as monitor conditions for the buy side.
        -> Place Market Order.
            Place orders on the market with real and assume order placemanet with test.
        '''
        updateOrder = False

        # Set the consitions to look over.
        if cp['order_side'] == 'SELL':
            current_conditions = TC.long_exit_conditions if market_type == 'LONG' else TC.short_exit_conditions
            cp.update({'buy_price':self.trade_recorder[-1][1]})
        else:
            if self.state_data['runtime_state'] == 'FORCE_PREVENT_BUY' or cp['order_status'] == 'LOCKED':
                return
            current_conditions = TC.long_entry_conditions if market_type == 'LONG' else TC.short_entry_conditions

        logging.debug('[BaseTrader] Checking for {0} condition. [{1}]'.format(cp['order_side'], self.print_pair))
        new_order = current_conditions(self.custom_conditional_data, cp, indicators,  self.market_prices, candles, self.print_pair)
        if 'buy_price' in cp:
            del cp['buy_price']

        # If no order is to be placed just return.
        if not(new_order):
            return

        order = None
        if new_order['order_type'] != 'WAIT':
            cp['order_description'] = new_order['description']

            # Format the prices to be used.
            if 'price' in new_order:
                if 'price' in new_order:
                    new_order['price'] = '{0:.{1}f}'.format(float(new_order['price']), self.rules['TICK_SIZE'])
                if 'stopPrice' in new_order:
                    new_order['stopPrice'] = '{0:.{1}f}'.format(float(new_order['stopPrice']), self.rules['TICK_SIZE'])
                if float(new_order['price']) != cp['price']:
                    updateOrder = True

            # If order is to be placed or updated then do so.
            if cp['order_type'] != new_order['order_type'] or updateOrder:
                order = new_order

        else:
            # Wait will be used to indicate order reset.
            if cp['order_side'] == 'BUY':
                cp['order_market_type'] = None
            cp['order_status'] = None
            cp['order_type'] = 'WAIT'

        if cp['order_id'] != None and (new_order['order_type'] == 'WAIT' or order != None):
            cancel_order_results = self._cancel_order(cp['order_id'], cp['order_type'])
            cp['order_id'] = None

        ## Place Market Order.
        if order:
            order_results = self._place_order(market_type, cp, order)
            logging.debug('order: {0}\norder result:\n{1}'.format(order, order_results))

            # If errors are returned for the order then sort them.
            if 'code' in order_results['data']:
                ## used to catch error codes.
                if order_results['data']['code'] == -2010:
                    self.state_data['runtime_state'] = 'PAUSE_INSUFBALANCE'
                elif order_results['data']['code'] == -2011:
                    self.state_data['runtime_state'] = 'CHECK_ORDERS'
                return

            logging.info('[BaseTrader] {0} Order placed for {1}.'.format(self.print_pair, new_order['order_type']))
            logging.debug('[BaseTrader] {0} Order placement results:\n{1}'.format(self.print_pair, str(order_results['data'])))

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
                        cp['load_id'] = order_results['data']['load_id'] 
                        cp['loan_cost'] = order_results['data']['loan_cost']
                else:
                    cp['tokens_holding'] = order_results['data']['tester_quantity']

            # Update the live order id for real trades.
            if self.configuration['run_type'] == 'REAL':
                cp['order_id'] = order_results['data']['orderId']

            cp['price']         = float(order_price)
            cp['order_type']    = new_order['order_type']
            cp['order_status']  = 'PLACED'

            logging.info('update: {0}, type: {1}, status: {2}'.format(updateOrder, new_order['order_type'], cp['order_status']))
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
                    loan_get_result = self.rest_api.apply_for_loan(asset=self.base_asset, amount=f_quantity)
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
                logging.info('[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3} price:{4}, stopPrice:{5}'.format(self.print_pair, order['side'], order['order_type'], f_quantity,order['price'], order['stopPrice']))
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