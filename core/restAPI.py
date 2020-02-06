#! /usr/bin/env python3

'''
restAPI

'''
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

    def __init__(self, api_key=None, api_secret=None):
        logging.debug('REST: Initilizing the REST api.')

        self.callCounter = 0
        
        if reqCheck.test_ping():
            self.api_key = str(api_key) if api_key is not None else ''
            self.api_secret = str(api_secret) if api_secret is not None else ''

        else: 
            logging.debug('Connection Error. (Failed Ping Test)')


    def get_market_rules(self):
        ''' This is used to get the rules of a market (min-bid, lot-size, e.t.c) '''
        logging.debug('REST: Getting market rules.')

        requestedData = self.api_request('GET', '/v1/exchangeInfo', {})

        if not requestedData:
            return

        return(requestedData['symbols'])


    def get_lastPrice(self, symbol):
        ''' This is used to get the rules of a market (min-bid, lot-size, e.t.c) '''
        logging.debug('REST: Getting market rules.')

        requestedData = self.api_request('GET', '/v3/ticker/price', {'symbol':symbol})

        if not requestedData:
            return

        return(requestedData)


    def get_market_summary(self, symbol):
        ''' This is used to get data about the market summary '''
        logging.debug('REST: Getting market summary.')

        param = {'symbol':symbol}

        requestedData = self.api_request('GET', '/v1/ticker/24hr', param)

        if not requestedData:
            return

        return(requestedData)


    def get_orderBook(self, symbol, **OPargs):
        ''' This returns the order books for a symbol '''
        logging.debug('REST: Getting order books.')

        param = {'symbol':symbol}
        param.update(OPargs)
        requestedData = self.api_request('GET', '/v1/depth', param)

        if not requestedData:
            return

        return(requestedData)


    def get_balance(self, token=None):
        ''' This returns the balance for a specific token '''
        logging.debug('REST: Getting current balance.')

        requestedData = self.api_signed_request('GET', '/v3/account', {})

        if not requestedData:
            return

        if token:
            try:
                if requestedData != 'requestedData':
                    for wallet in requestedData['balances']:
                        if token == wallet['asset']:
                            returnData = {'asset':wallet['asset'], 'free':float(wallet['free']), 'locked':float(wallet['locked'])}
                            break

                    return(returnData)
            except:
                logging.exception('balances issue : [{0}]'.format(requestedData))
                return
        else:
            returnDict = {}
            for wallet in requestedData['balances']:
                returnDict.update({wallet['asset']:{'free':wallet['free'], 'locked':wallet['locked']}})

            return(returnDict)

        return


    def order_placer(self, symbol, mRules, tInfo, side, orderType, **OPargs):
        ''' This is used to place orders onto the exchange. '''
        logging.debug('REST: Attempting to place a {0} order on the exchange'.format(side))

        orderOutcome = False

        if (self.cancel_open_orders('ALL', symbol)):
            ## This is used to format the price.
            if 'price' in OPargs:
                OPargs['price'] = '{0:.{1}f}'.format(OPargs['price'], mRules['TICK_SIZE'])

            ## This is used to find out where the quantity will be pulled from.
            if side == 'SELL':
                token = symbol[:-3]
                balance = self.get_balance(token)
                quantity = str(balance['free'])
            elif side == 'BUY':
                quantity = str(tInfo['currencyLeft']/float(OPargs['price']))

            ## This is quantity formatted for the api.
            LOT_SIZE = mRules['LOT_SIZE']+1
            fquantity = quantity[:quantity.index('.')+LOT_SIZE]

            if fquantity[-1] == '.':
                fquantity = fquantity.replace('.', '') 

            ## This is used to create the parameters for the order call.
            params = {'symbol':symbol, 'side':side, 'type':orderType, 'quantity':fquantity}
            if orderType != 'MARKET': params.update({'timeInForce':'GTC'})      
            params.update(OPargs)

            ## This is used to place an order on the market.
            requestedData = self.api_signed_request('POST', '/v3/order', params)

            try:
                if requestedData[0] == False:
                    orderOutcome = {'code': 1, 'data':requestedData[1]}
            except:
                if requestedData:
                    orderOutcome = {'code': 0, 'data':requestedData}

        return(orderOutcome)


    def check_open_orders(self, symbol):
        ''' This is used to check the most recent open order on a specific market. '''
        logging.debug('REST: Checking current open orders.')
        
        orders = self.api_signed_request('GET', '/v3/openOrders', {'symbol':symbol})

        if orders:
            if len(orders) != 0:
                return({'data':orders})

        return('Empty')


    def cancel_open_orders(self, side, symbol):
        ''' This is used to cancel all open orders for a specified market. '''
        logging.debug('REST: Canceling open orders for {0}.'.format(side))
        
        orderCanceled = False

        ## This is used to get the current open orders.
        while not(orderCanceled):
            openOrders = self.check_open_orders(symbol)

            if openOrders != 'Empty':
                ## This checks if there is an open order.
                for order in openOrders['data']:

                    ## This checks the side of the order.
                    if order['side'] == side or side == 'ALL':

                        ## This sets up the parameters and then sends a DELETE request.
                        params = {'symbol':symbol, 'orderId':order['orderId']}
                        cancelStatus = self.api_signed_request('DELETE', '/v3/order', params)

                        if cancelStatus:
                            if cancelStatus['status'] == 'CANCELED':
                                orderCanceled = True
                        else:
                            orderCanceled = True
            else:
                orderCanceled = True
        return orderCanceled


    def check_closed_orders(self, side, symbol):
        ''' This is used to check the market to see if there are any open trades that can be found. '''
        logging.debug('REST: Checking closed orders for {0}.'.format(side))

        requestedData = self.api_signed_request('GET', '/v3/allOrders', {'symbol':symbol})

        if not requestedData:
            return

        if requestedData != 'Empty': 
            boughtPrice = 0
            requestedData.reverse()

            for order in requestedData:
                if order['side'] == side:
                    token = symbol[:-3]

                    if order['status'] == 'FILLED':
                        ## This section is for loading in filled orders.
                        
                        currencyBalance = self.get_balance(token)['free']
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
                            currencyBalance = self.get_balance(token)['free']

                            if currencyBalance >= qRemaining:
                                return({'CALL':True, 'data':{'status':'PART', 'quantityRemaining':qRemaining, 'Quantity':quantity, 'price':float(order['price'])}})
                            else:
                                break

        return({'CALL':False, 'message':'No closed orders found.'})


    def get_klines(self, interval, symbol, **OPargs):
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
        logging.debug('REST: Getting candles.')

        candles = {'time':[], 'open':[], 'high':[], 'low':[], 'close':[], 'volume':[]}

        params = {'symbol':symbol, 'interval':interval}
        params.update(OPargs)

        rawCandles = self.api_request('GET', '/v1/klines', params)

        if not rawCandles:
            return

        try:
            rawCandles.reverse()

            for can in rawCandles:
                candles['time'].append(int(can[0]))
                candles['open'].append(float(can[1]))
                candles['high'].append(float(can[2]))
                candles['low'].append(float(can[3]))
                candles['close'].append(float(can[4]))
                candles['volume'].append(float(can[5]))

            return candles
        except:
            logging.exception('candles issue : [{0}]'.format(rawCandles))


    def api_request(self, method, path, params=None):
        ''' This is used to create a normal request to the binance exchange. '''
        retries = 10

        urlQuery = '{0}{1}?{2}'.format(REST_BASE, path, urlencode(sorted(params.items())))
        if urlQuery[-1] == '?':
            urlQuery = urlQuery[:-1]

        logging.debug('REST: Attempting request: [{0}]'.format(urlQuery))

        while retries > 0:
            self.callCounter += 1
            data = None

            try:
                api_resp = requests.request(method, urlQuery)
                data = api_resp.json()
            except Exception as error:
                data = {'fatal':{'type':'CONNECTION_ERROR', 'message':error}}

            checkCode = reqCheck.data_check(data, urlQuery)

            if checkCode[1] == '':
                if(checkCode[0] == 1):
                    return(data)
                elif(checkCode[0] == 0):
                    retries -= 1
            else:
                if(checkCode[0] == -1):
                    return False

        return False


    def api_signed_request(self, method, path, params=None):
        ''' This is used to create a signed request to the binance exchange. '''
        retries = 10

        param_encode = urlencode(sorted(params.items()))

        while retries > 0:
            self.callCounter += 1
            data = None
            query = '{0}&timestamp={1}'.format(param_encode, int(time.time()*1000))
            signature = hmac.new(bytes(self.api_secret.encode('utf-8')), (query).encode('utf-8'), sha256).hexdigest()
            urlQuery = '{0}{1}?{2}&signature={3}'.format(REST_BASE, path, query, signature)

            logging.debug('REST: Attempting request: [{0}]'.format(urlQuery))

            try:
                api_resp = requests.request(method, urlQuery, headers={'X-MBX-APIKEY':self.api_key})
                data = api_resp.json()
            except Exception as error:
                data = {'fatal':{'type':'CONNECTION_ERROR','message':error}}

            checkCode = reqCheck.data_check(data, urlQuery)

            if checkCode[1] == '':
                if(checkCode[0] == 1):
                    return(data)
                elif(checkCode[0] == 0):
                    retries -= 1
            else:
                if(checkCode[0] == -1):
                    return False

        return False