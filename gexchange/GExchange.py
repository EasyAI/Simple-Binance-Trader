#! /usr/bin/env python3

import hmac
import hashlib
import logging
import requests
import time
from .formats import *
from urllib.parse import urlencode

## Binance/Bittrex global api (ongoing work)
## Thanks to:
## Binance api: https://github.com/binance-exchange/binance-official-api-docs
## Bittrex: https://github.com/thebotguys/golang-bittrex-api

BASE_URL = {'binance':'https://www.binance.com/api', 'bittrex':'https://bittrex.com/api'}
TIME_FORMAT = {
	"bittrex":{"time":{"1m":"oneMin", "5m":"fiveMin", "30m":"thirtyMin", "1h":"hour"}},
	"binance":{"time":{"1m":"1m", "5m":"5m", "15m":"15m", "30m":"30m", "1h":"1h", "2h":"2h", "4h":"4h", "6h":"6h"}}
}

## Note not every function has support for both exchanges yet


class g_exchange(object):


	def __init__(self, exchange, api_key=None, api_secret=None):
		self.exchange = str(exchange).lower()
		self.api_key = str(api_key) if api_key is not None else ''
		self.api_secret = str(api_secret) if api_secret is not None else ''


	def get_exchangeInfo(self):
		"""
		This returns any CLOSED orders for a specified market.
		PARAMETERS
			None
		FORMAT
		{
			"timeZone":
			"serverTime":
			"rateLimits":
				[{
					"rateLimitType":"REQUESTS"
					"interval":"MINUTE"
					"limit":1200
				},
				{
					"rateLimitType":"REQUESTS"
					"interval":"SECOND"
					"limit":10
				},
				{
					"rateLimitType":"REQUESTS"
					"interval":"DAY"
					"limit":100000
				}
			"exchangeFilters": [],
			"symbols": [{
				"symbol": "ETHBTC",
				"status": "TRADING",
				"baseAsset": "ETH",
				"baseAssetPrecision": 8,
				"quoteAsset": "BTC",
				"quotePrecision": 8,
				"orderTypes": ["LIMIT", "MARKET"],
				"icebergAllowed": false,
				"filters": [{
					"filterType": "PRICE_FILTER",
					"minPrice": "0.00000100",
					"maxPrice": "100000.00000000",
					"tickSize": "0.00000100"
				}, {
					"filterType": "LOT_SIZE",
					"minQty": "0.00100000",
					"maxQty": "100000.00000000",
					"stepSize": "0.00100000"
				}, {
				 	"filterType": "MIN_NOTIONAL",
					"minNotional": "0.00100000"
				}]
  			}]
		}
		RETURN
			This returns everything about the exchange.
		"""
		ex = self.exchange
		data = None

		if ex == 'binance': 
			get_data = self.api_request('GET', '/v1/exchangeInfo', {})

		return(get_data)


	def get_balance(self, token):
		"""
		This is gets a global balance format for a coin.
		PARAMETERS
			Required.
			token = str (BTC)
		FORMAT
		{
			"Token": str (BTC), 
			"Total": float, 
			"Available": float, 
			"unAvailable": float
		}
		RETURN
			You will get balance data related to the token you passed.
		"""
		ex = self.exchange
		token = token.upper()
		data = None

		if ex == 'binance': 
			get_data = self.api_signed_request('GET', '/v3/account', {})
			for element in get_data['balances']:
				if token == element['asset']:
					data = element
					break
			if data == None: raise ValueError("Invalid Market")
		elif ex == "bittrex": 
			params = {"currency":token}
			data = self.api_signed_request('GET', '/v1.1/account/getbalance', params)["result"]

		return(fmt_balance(ex, data))


	def get_orderBook(self, market, **OPargs):
		"""
		This gets the orderbooks for a specific coin.
		PARAMETERS
			Required:
			market = str (BTC-LTC)
			Optional:
			limit = int
		"""
		ex = self.exchange
		fmarket = fmt_Msymbol(ex, market)

		if ex == 'binance': 
			param = {'symbol':fmarket}
			param.update(OPargs)
			data = self.api_request('GET', '/v1/depth', param)

		return(data)


	def get_marketInfo(self, market):
		"""
		This returns any CLOSED orders for a specified market.
		PARAMETERS
			market = str
		FORMAT
			symbols": [{
			"symbol": "ETHBTC",
			"status": "TRADING",
			"baseAsset": "ETH",
			"baseAssetPrecision": 8,
			"quoteAsset": "BTC",
			"quotePrecision": 8,
			"orderTypes": ["LIMIT", "MARKET"],
			"icebergAllowed": false,
			"filters": [{
				"filterType": "PRICE_FILTER",
				"minPrice": "0.00000100",
				"maxPrice": "100000.00000000",
				"tickSize": "0.00000100"
			}, {
				"filterType": "LOT_SIZE",
				"minQty": "0.00100000",
				"maxQty": "100000.00000000",
				"stepSize": "0.00100000"
			}, {
			 	"filterType": "MIN_NOTIONAL",
				"minNotional": "0.00100000"
			}]
		RETURN
			This returns information about a certain market.
		"""
		ex = self.exchange
		market = fmt_Msymbol(ex, market)
		data = None

		if ex == 'binance': 
			get_data = self.api_request('GET', '/v1/exchangeInfo', {})
			for element in get_data['symbols']:
				if market in element['symbol']:
					data = element
					break

		return(data)


	def get_market_summary(self, market):
		"""
		This will return a summary of a market in a global format
		PARAMETERS
			Require.
			market = str (BTC-LTC)
		FORMAT
		{
			"Market":str (BTC-LTC), 
			"Last":float, 
			"Buy":float, 
			"Sell":float
		}
		RETURN
			This will return a breif market summary of current prices along with the market.
		"""
		ex = self.exchange
		fmarket = fmt_Msymbol(ex, market)

		if ex == 'binance': 
			param = {'symbol':fmarket}
			data = self.api_request('GET', '/v3/ticker/bookTicker', param)
			data.update(self.api_request('GET', '/v3/ticker/price', param))
		elif ex == 'bittrex': 
			param = {'marketName':fmarket}
			data = self.api_request('GET', '/v2.0/pub/market/GetMarketSummary', param)['result']

		return(fmt_market_sum(ex, data))


	def post_buy(self, market, quantity, price, orderType="LIMIT", timeInForce="GTC", **OPargs):
		"""
		This is a global BUY order
		PARAMETERS
			Require.
			market = str
			quantity = float
			price = float
			Optional
			orderType = str
			timeInForce = str
			stopPrice = dec
			icebergQty = dec
		"""
		ex = self.exchange
		fmarket = fmt_Msymbol(ex, market)
		data = None

		if ex == 'binance':
			if 'stopPrice' in OPargs: OPargs['stopPrice'] = str(OPargs['stopPrice'])

			params = {'symbol':fmarket, 'side':'BUY', 'type':orderType, 'timeInForce': timeInForce, 'quantity':str(quantity), 'price':str(price)}
			params.update(OPargs)
			data = self.api_signed_request('POST', '/v3/order', params)
		elif ex == 'bittrex':
			params = {'market':fmarket, 'quantity':quantity, 'rate':price}
			data = self.api_signed_request('POST', '/v1.1/market/buylimit', params)

		if not(data == None): return(True)
		else: return(False)


	def post_sell(self, market, quantity, price, orderType="LIMIT", timeInForce="GTC", **OPargs):
		"""
		This is a global SELL order.
		PARAMETERS
			Require.
			market = str
			quantity = float
			price = float
			Optional
			orderType = str
			timeInForce = str
			stopPrice = dec
			icebergQty = dec
		"""
		ex = self.exchange
		fmarket = fmt_Msymbol(ex, market)
		data = None

		if ex == 'binance':
			if 'stopPrice' in OPargs: OPargs['stopPrice'] = str(OPargs['stopPrice'])

			params = {'symbol':fmarket, 'side':'SELL', 'type':orderType, 'timeInForce': timeInForce, 'quantity':str(quantity), 'price':str(price)}
			params.update(OPargs)
			data = self.api_signed_request('POST', '/v3/order', params)
		elif ex == 'bittrex':
			params = {'market':fmarket, 'quantity':quantity, 'rate':price}
			data = self.api_signed_request('POST', '/v1.1/market/selllimit', params)

		if not(data == None): return(True)
		else: return(False)


	def get_orders_closed(self, market):
		"""
		This returns any CLOSED orders for a specified market.
		PARAMETERS
			Required:
			market = str (BTC-LTC)
		FORMAT
		[{
			"Type": str (BUY or SELL), 
			"Quantity": float, 
			"QuantityRemaining": float or None, 
			"Price": float, 
			"PricePerUnit": float,
			"Commission": float or None, 
			"Time": time element
		}]
		RETURN
			You will get a list of CLOSED orders if any are present.
		"""
		ex = self.exchange
		fmarket = fmt_Msymbol(ex, market)

		if ex == 'binance':
			params = {'symbol':fmarket}
			data = self.api_signed_request('GET', '/v3/allOrders', params)
		elif ex == 'bittrex':
			params = {'market':fmarket}
			data = self.api_signed_request('GET', '/v1.1/account/getorderhistory', params)['result']

		return(fmt_orders(ex, data))

		
	def get_orders_open(self, market):
		"""
		This returns any OPEN orders for a specified market.
		PARAMETERS
			Required:
			market = str (BTC-LTC)
		FORMAT
		[{
			"Type": str (BUY or SELL), 
			"Quantity": float, 
			"QuantityRemaining": float or None, 
			"Price": float, 
			"PricePerUnit": float,
			"Commission": float or None, 
			"Time": time element
		}]
		RETURN
			You will get a list of OPEN orders if any are present.
		"""
		ex = self.exchange
		fmarket = fmt_Msymbol(ex, market)

		if ex == 'binance':
			params = {'symbol':fmarket}
			data = self.api_signed_request('GET', '/v3/openOrders', params)
		elif ex == 'bittrex':
			params = {'market':fmarket}
			data = self.api_signed_request('GET', '/v1.1/market/getopenorders', params)['result']

		return(fmt_orders(ex, data))


	def cancel_order(self, market, ID):
		"""
		This is used to CANCLE any open orders for a specific market
		PARAMETERS
			Required:
			market = str (BTC-LTC)
			timestamp = int (UNIX time)
		RETURN
			Will return True or False
		"""
		ex = self.exchange
		fmarket = fmt_Msymbol(ex, market)
		data = None

		if ex == 'binance':
			params = {'symbol':fmarket, 'orderId':ID}
			data = self.api_signed_request('DELETE', '/v3/order', params)
		elif ex == 'bittrex':
			pass
			params = {'OrderUuid':ID}
			data = self.api_signed_request('cancel', '/v1.1/market/cancel', params)['result']

		if not(data == None): return(True)
		else: return(False)


	def get_candles(self, market, interval, **OPargs):
		"""
		This returns all the markets for a specific coin
		PARAMETERS
			Required:
			market = str (BTC-LTC)
			interval = str (15m)
			Optional:
			limit = int (300)
		FORMAT
		[{
			"OpenTime": exchange time stamp,
			"Open": float,
			"High": float,
			"Low": float,
			"Close": float,
			"Volume": float
		}]
		RETURN
			You will get a list of candles returned.
		"""
		ex = self.exchange
		fmarket = fmt_Msymbol(ex, market)

		if ex == 'binance':
			params = {'symbol':fmarket, 'interval':TIME_FORMAT[ex]['time'][interval]}
			params.update(OPargs)
			data = self.api_request('GET', '/v1/klines', params)
		elif ex == 'bittrex':
			params = {'marketName':fmarket, 'tickInterval':TIME_FORMAT[ex]['time'][interval]}
			data = self.api_request('GET', '/v2.0/pub/market/GetTicks', params)['result']

		return(fmt_candles(ex, data))


	def get_24hr(self, market=None):
		"""
		This returns all the markets for a specific coin
		PARAMETERS
			Optional:
			market = str (BTC-LTC)
		FORMAT
		[{
			"OpenTime": exchange time stamp,
			"Open": float,
			"High": float,
			"Low": float,
			"Close": float,
			"Volume": float
		}]
		RETURN
			You will get the 24h candle data
		"""
		ex = self.exchange
		fmarket = fmt_Msymbol(ex, market)

		if ex == 'binance':
			if not(market == None):
				params = {'symbol':fmarket}
			
			data = self.api_request('GET', '/v1/ticker/24hr', params)

		return(data)


	def api_request(self, method, path, params=None):
		"""
		This is used to request public data from the exchange.
		"""
		ex = self.exchange
		recivedData = False

		while not(recivedData):
			api_resp = requests.request(method, BASE_URL[ex] + path, params=params)

			try:
				data = api_resp.json()
				recivedData = True
			except Exception as e:
				if not(self.ping): time.sleep(10) 

		if(self.exchange_error_check(data)):
			return(data)


	def api_signed_request(self, method, path, params=None):
		"""
		This is used to request secret data from the exchange.
		"""
		ex = self.exchange
		recivedData = False
		param_encode = urlencode(sorted(params.items()))
		if self.api_key == '' or self.api_secret == '':
			raise ValueError("Make sure you use your API key/secret")

		while not(recivedData):
			timeStamp = str(int(time.time() * 1000))

			if ex == 'binance':
				query = param_encode + '&timestamp=' + timeStamp
				signature = hmac.new(bytes(self.api_secret.encode('utf-8')), (query).encode('utf-8'), hashlib.sha256).hexdigest()
				query += '&signature=' + signature
				api_resp = requests.request(method, BASE_URL[ex] + path + '?' + query, headers={'X-MBX-APIKEY':self.api_key})

			if ex == 'bittrex':
				url = BASE_URL[ex] + path + '?' + param_encode + '&nonce=' + timeStamp + '&apikey=' + self.api_key
				signature = hmac.new(bytes(self.api_secret.encode('utf-8')), (url).encode('utf-8'), hashlib.sha512).hexdigest()
				api_resp = requests.request(method,  url, headers={'apisign':signature})

			try:
				data = api_resp.json()
			except Exception as e: 
				if not(self.ping): time.sleep(10) 

			if(self.exchange_error_check(data)):
				recivedData = True

		return(data)


	def exchange_error_check(self, data):
		ex = self.exchange
		errorMsg = None

		if data == None: errorMsg == "Was unable to get the data."
		elif 'msg' in data:
			errorMsg = data['msg']
		elif 'message' in data:
			if not(data['message'] == ''):
				errorMsg = data['message']

		if errorMsg == None: 
			return(True)
		elif errorMsg == "Timestamp for this request is outside of the recvWindow.":
			return(False)
		else: 
			raise ValueError(errorMsg)


	def ping(self):
		"""
		This returns a response to a ping request
		"""
		ex = self.exchange

		if ex == 'binance': fullPath = BASE_URL[ex] + '/v1/ping'
		elif ex == 'bittrex': fullPath = 'https://socket.bittrex.com/signalr/ping'

		if requests.request('GET', fullPath): return(True)
		else: return(False)