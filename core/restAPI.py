#! /usr/bin/env python3

import os
import hmac
import time
import json
import logging
import requests
import numpy as np
from . import reqCheck
from hashlib import sha256
from urllib.parse import urlencode


## sets up the rest BASE for binances rest API.
REST_BASE = 'https://www.binance.com/api'


class BinanceREST:

    def __init__(self, market=None, api_key=None, api_secret=None):
        
        if reqCheck.test_ping():
            self.api_key = str(api_key) if api_key is not None else ''
            self.api_secret = str(api_secret) if api_secret is not None else ''

            if market is not None:
                token = market[market.index('-')+1:]
                self.market = ('%s%s' % (token, market[:market.index('-')])).upper()
                self.token = token.upper()
            else: self.market = ''
        else: 
            logging.info('Connection Error. (Failed Ping Test)')


    def get_market_rules(self):
        ''' This gets data from the current time to the last 24h. '''
        logging.info('REST: Getting market rules.')
        get_data = self.api_request('GET', '/v1/exchangeInfo', {})

        if not(get_data): 
            return(False)

        for element in get_data['symbols']:
            if self.token in element['symbol']:
                return(element['filters'])
                break

        logging.info('REST: No valid symbol (get_market_rules)')


    def get_balance(self, token=None):
        ''' This returns the balance for a specific token '''
        logging.info('REST: Getting balance.')

        get_data = self.api_signed_request('GET', '/v3/account', {})
        if not(get_data): 
            return(False)
        if token == None:
            token = self.token

        data = None
        if 'balances' in get_data:
            for wallet in get_data['balances']:
                if token == wallet['asset']:
                    data = {'asset':wallet['asset'], 'free':float(wallet['free']), 'locked':float(wallet['locked'])}
                    break
        if data:
            return(data)
        else:
            return(False)


    def get_market_summary(self):
        ''' This is used to get data about the market summary '''
        logging.info('REST: Getting market summary.')
        param = {'symbol':self.market}

        get_data = self.api_request('GET', '/v3/ticker/price', param)
        if not(get_data): 
            return(False)

        return(float(get_data['price']))


    def order_placer(self, mRules, tInfo, side, orderType, **OPargs):
        ''' This is used to place orders onto the exchange. '''
        if (self.cancel_open_orders('ALL')):
            logging.info('REST: Placing order.')
            ## This is used to format the price.
            if 'price' in OPargs:
                OPargs['price'] = '{0:.{1}f}'.format(OPargs['price'], mRules['TICK_SIZE'])

            ## This is used to find out where the quantity will be pulled from.
            if side == 'SELL':
                balance = self.get_balance()
                quantity = str(balance['free'])
            elif side == 'BUY':
                quantity = str(tInfo['currencyLeft']/float(OPargs['price']))

            ## This is quantity formatted for the api.
            LOT_SIZE = mRules['LOT_SIZE']+1
            fquantity = quantity[:quantity.index('.')+LOT_SIZE]

            if fquantity[-1] == '.':
                fquantity = fquantity.replace('.', '') 

            ## This is used to create the parameters for the order call.
            params = {'symbol':self.market, 'side':side, 'type':orderType, 'quantity':fquantity}
            if orderType != 'MARKET': params.update({'timeInForce':'GTC'})      
            params.update(OPargs)

            ## This is used to place an order on the market.
            get_data = self.api_signed_request('POST', '/v3/order', params)
            orderOutcome = {'code': 0, 'data':get_data} if get_data else {'code': 10, 'data':get_data}

        return(orderOutcome)


    def check_open_orders(self):
        ''' This is used to check the most recent open order on a specific market. '''
        logging.info('REST: Checking open orders.')
        orders = self.api_signed_request('GET', '/v3/openOrders', {'symbol':self.market})

        logging.info('REST: Open orders data: {0}'.format(orders))
        if orders == None:
            return(False)

        elif not(len(orders) == 0):
            return({'data':orders})

        elif orders == []: 
            return('Empty')

        else: 
            return(False)


    def cancel_open_orders(self, side):
        ''' This is used to cancel all open orders for a specified market. '''
        logging.info('REST: Canceling open orders.')
        orderCancled = False

        ## This is used to get the current open orders.
        while not(orderCancled):
            openOrders = self.check_open_orders()

            if openOrders != 'Empty':
                ## This checks if there is an open order.
                for order in openOrders['data']:

                    ## This checks the side of the order.
                    if order['side'] == side or side == 'ALL':

                        ## This sets up the parameters and then sends a DELETE request.
                        params = {'symbol':self.market, 'orderId':order['orderId']}
                        self.api_signed_request('DELETE', '/v3/order', params)

                        if self.get_balance()['locked'] == 0:
                            if self.check_open_orders() == 'Empty':
                                orderCancled = True
            else:
                orderCancled = True
        return(orderCancled)


    def check_closed_orders(self, side):
        ''' This is used to check the market to see if there are any open trades that can be found. '''
        logging.info('REST: Checking closed orders.')
        boughtPrice = 0

        get_data = (self.api_signed_request('GET', '/v3/allOrders', {'symbol':self.market}))
        if not(get_data): 
            return(False)
        orders = get_data
        orders.reverse()

        if not(orders == 'Empty'): 
            for order in orders:
                if order['side'] == side:

                    if order['status'] == 'FILLED':
                        ## This section is for loading in filled orders.
                        currencyBalance = self.get_balance()['free']
                        boughtPrice = float(order['price'])
                        quantity = float(order['origQty'])
                                        
                        if (currencyBalance >= quantity):
                            return({'CALL':True, 'data':{'status':'FILLED', 'quantity':quantity, 'price':boughtPrice}})
                        else:
                            break

                    elif order['status'] == 'CANCELED':
                        ## This section if for loading in part filled orders.
                        quantity = float(order['origQty'])
                        qRemaining = (quantity - float(order['executedQty']))
                        if qRemaining != quantity:
                            currencyBalance = self.get_balance()['free']

                            if currencyBalance >= qRemaining:
                                return({'CALL':True, 'data':{'status':'PART', 'quantityRemaining':qRemaining, 'Quantity':quantity, 'price':float(order['price'])}})
                            else:
                                break

        return({'CALL':False, 'data':{}})


    def get_klines(self, interval, market=None, **OPargs):
        '''
        This gets raw candles data from the binance exchange.

        Format is -
        [
            {
                time : int,
                open : float,
                high : float,
                low : float,
                close : float,
                volume : float
            }, ...
        ]
        '''
        logging.info('REST: Getting candles.')
        candles = {'time':[], 'open':[], 'high':[], 'low':[], 'close':[], 'volume':[]}

        if self.market == '':
            if '-' in market: market = '%s%s' % (market[4:], market[:3])
        else: market = self.market

        params = {'symbol':market, 'interval':interval}
        params.update(OPargs)

        rawCandles = self.api_request('GET', '/v1/klines', params)
        if not(rawCandles): 
            return(False)

        rawCandles.reverse()

        for can in rawCandles:
            candles['time'].append(int(can[0]))
            candles['open'].append(float(can[1]))
            candles['high'].append(float(can[2]))
            candles['low'].append(float(can[3]))
            candles['close'].append(float(can[4]))
            candles['volume'].append(float(can[5]))

        return(candles)


    def api_request(self, method, path, params=None):
        ''' This is used to create a normal request to the binance exchange. '''
        retries = 5
        urlQuery = '{0}{1}?{2}'.format(REST_BASE, path, urlencode(sorted(params.items())))

        if urlQuery[-1] == '?':
            urlQuery = urlQuery[:-1]

        while retries > 0:
            data = None
            try:
                api_resp = requests.request(method, urlQuery)
                data = api_resp.json()
            except Exception as error:
                data = {'fatal':{'type':'CONNECTION_ERROR', 'message':error}}

            if(reqCheck.data_check(data, urlQuery)):
                return(data)
            retries -= 1
            time.sleep(5)
                    
        logging.warning('REST: error getting data (reached max retry attempts) - normal request.')
        return(False)


    def api_signed_request(self, method, path, params=None):
        ''' This is used to create a signed request to the binance exchange. '''
        retries = 5
        param_encode = urlencode(sorted(params.items()))

        while retries > 0:
            data = None
            query = '{0}&timestamp={1}'.format(param_encode, int(time.time()*1000))
            signature = hmac.new(bytes(self.api_secret.encode('utf-8')), (query).encode('utf-8'), sha256).hexdigest()
            urlQuery = '{0}{1}?{2}&signature={3}'.format(REST_BASE, path, query, signature)

            try:
                api_resp = requests.request(method, urlQuery, headers={'X-MBX-APIKEY':self.api_key})
                data = api_resp.json()
            except Exception as error:
                data = {'fatal':{'type':'CONNECTION_ERROR','message':error}}

            if(reqCheck.data_check(data, urlQuery)):
                return(data)

            retries -= 1
            time.sleep(5)

        logging.warning('REST: error getting data (reached max retry attempts) - signed request.')
        return(False)