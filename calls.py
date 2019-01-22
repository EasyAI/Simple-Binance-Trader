#! /usr/bin/env python3

"""
This is a optimized api for calling/dealing with binance data
"""

import hmac
import hashlib
import logging
import requests
import time
import sys
import os
import TradeIndicators as TI
from urllib.parse import urlencode


BASE_API = 'https://www.binance.com/api'
BASE_WAPI = 'https://api.binance.com/wapi'

"""

ORDERS ERROR CODES:

GLOABAL
0 - Unknown error

TRADER CODES:
100 - Successfully place order on the market.
101 - Not enough BTC available to place an initial buy order.
102 - Not enough BTC left for the bot to place a new buy order.
103 - Not enough tokens left to place a sell order.

ORDER CODES:
200 - Order has been filled
201 - There is enough bot the bot to begin setting sell orders.
202 - There is not enough for the bot to set a sell order so it needs to buy more.
210 - There is currencly an active order on the market.
211 - The currenct active order on the market is part filled.
212 - The currenct buy order needs to be locked.
213 - THe currenct sell order needs to be loocked.
"""
LOGS_FILE_PATH 	= os.getcwd()+"/extra/"
logFileName 	= ("{0}_errors_log.txt".format(LOGS_FILE_PATH))

class Calls(object):
	"""
	This entire object is used to get calls from binance and manage them.
	"""


	def __init__(self, api_key=None, api_secret=None):
		self.api_key = str(api_key) if api_key is not None else ''
		self.api_secret = str(api_secret) if api_secret is not None else ''


		logFile = open(logFileName, 'w')
		logFile.write(" ")
		logFile.close()



	def trade_manager(self, tInfo, side, price, orderType="LIMIT"):
		"""
		The order manager is used when trying to place an order and will return data based on the status of the order that was placed.
		"""
		market 	= tInfo["market"]
		token 	= market[market.index('-')+1:]
		message = None
		code 	= None

		if tInfo["CTI"]["tradeTypes"]["B"] != None:
			## This deals with the buy side for checking balances.
			if tInfo["currencyLeft"] > tInfo["MR"]["MINIMUM_NOTATION"]:
				# This checks if there is enought currency left to place a buy order.
				balance = self.get_balance("BTC")
				if balance['free'] <= tInfo["currencyLeft"]:
					# This checks if there is enough btc to place a buy order.
					code, message = 101, "Not enough BTC to placed initial buy."
			else:
				code, message = 102, "Not enough currency left to place new buy."

		if tInfo["CTI"]["tradeTypes"]["S"] != None:
			lastPrice 	= self.get_market_summary("last", tInfo["market"])
			balance 	= self.get_balance(token)

			## This deals with the sell side of checking balances.
			if (balance['locked']+balance['free'])*lastPrice <= tInfo["MR"]["MINIMUM_NOTATION"]:
				## This checks if there is enough balance to place a sell order.
				code, message = 103, "Not enough {0} to place sell order.".format(tInfo['market'])

		if code == None:
			if self.cancel_open_orders(side, market):
				balance 	= self.get_balance(token)
				orderResult = self.set_order(tInfo, side, orderType, price=price)

				if orderResult:
					code, message = 100, "Order placed."
				else:
					code, message = 0, "Unknown error placing order."

		return({"code":code, "msg":message})



	def order_manager(self, tInfo, side):
		"""
		This function is used to manage current orders for a specifit market, this checks the state of the orders (filled, partfilled, e.c.t).
		"""
		market 	= tInfo["market"]
		token 	= market[market.index('-')+1:]
		message = None
		code 	= None
		oOrder 	= self.check_open_orders(market)

		if oOrder != "Empty":
			## This first part is for checking an active order.
			try:
				order = oOrder['data'][0]
				## This will be used to let the bot know the current order is placed.
				code, message = 210, "Order is placed."
				if order['side'] == side:
					if order['status'] == "PARTIALLY_FILLED":
						## This will be used to let the bot know the current order is part filled.
						code, message = 211, "Order is part filled"
						
						## This block checks buy and sell orders and will be used to determin if a new order can be placed.
						if side == "BUY":
							## This will check the bots current BTC left and check if it has enough BTC left to place a new order.
							if tInfo["currencyLeft"] <= tInfo["MR"]["MINIMUM_NOTATION"]:
								code, message = 212, "Buy order lock."

						elif side == "SELL":
							## This will check if there is enough of the traded token to place a new order.
							lastPrice 	= self.get_market_summary("last", tInfo["market"])
							balance 	= self.get_balance(token)
							if (balance['locked']+balance['free'])*lastPrice <= tInfo["MR"]["MINIMUM_NOTATION"]:
								code, message = 213, "Sell order lock."
			except Exception as e:
				print_out(e, oOrder)

		else:
			## This second part is for checking the current traded token and BTC amounts before placing.
			tradeDone = False
			lastPrice 	= self.get_market_summary("last", market)
			balance 	= self.get_balance(token)

			if tInfo["CTI"]["tradeTypes"]["S"] != None:
				## This checks the current wallet on the traded token if the bot is selling.
				if balance["free"]*lastPrice <= tInfo["MR"]["MINIMUM_NOTATION"]:
					if tInfo["CTI"]["orderStatus"]["S"] != None:
						tradeDone = True
				else:
					## This is used to check if there is an inavlid amount left to sell if no order is placed.
					code, message = 202, "Invalid amount to sell."

			elif tInfo["CTI"]["tradeTypes"]["B"] != None:
				## This checks the current wallet on the BTC if the bot is buying.
				if balance["free"]*lastPrice > tInfo["MR"]["MINIMUM_NOTATION"]:
					if tInfo["CTI"]["orderStatus"]["B"] != None:
						tradeDone = True
				else:
					## This checks the bot while its on buy to see if there is enough of the trader token to place a missed order.
					code, message = 201, "Already existing balance"

				if tInfo["CTI"]["tradeTypes"]["B"] == "wait" and balance['locked'] > 0:
					## This cancels all orders if the bot condition is no longer true.
					self.cancel_open_orders("ALL", market)

			if tradeDone:
				## This will be returned if a trade has been declared done by the manager.
				code, message = 200, "Finished order."

		return({"code":code, "msg":message})



	def set_order(self, tInfo, side, orderType, **OPargs):
		"""
		This is used to place orders onto the exchange.
		"""
		orderOutcome = False
		market 	= tInfo["market"]
		token 	= market[market.index('-')+1:]

		## This is used to format the price.
		if 'price' in OPargs:
			OPargs['price'] = "{0:.{1}f}".format(OPargs['price'], tInfo["MR"]["TICK_SIZE"])

		## This is used to find out where the quantity will be pulled from.
		if side == "SELL":
			balance = self.get_balance(token)
			quantity = str(balance['free'])
		elif side == "BUY":
			quantity = str(tInfo["currencyLeft"]/float(OPargs['price']))

		## This is quantity formatted for the api.
		LOT_SIZE = tInfo["MR"]["LOT_SIZE"]+1
		fquantity = quantity[:quantity.index('.')+LOT_SIZE]

		if fquantity[-1] == '.':
			fquantity = fquantity.replace('.', '') 

		## This is used to create the parameters for the order call.
		params = {'symbol':fmt_market(market), 'side':side, 'type':orderType, 'quantity':fquantity}
		if orderType != "MARKET": params.update({'timeInForce':'GTC'})		
		params.update(OPargs)

		try:
			## This is used to place an order on the market.
			data = None
			data = self.api_signed_request('POST', '/v3/order', params)
			orderOutcome = True if data != None else False

		except ValueError as error:
			print_out(data, error)
			return(False)
		except Exception as error:
			print_out(data, error)
			return(False)
			
		return(orderOutcome)



	def check_open_orders(self, market):
		"""
		This is used to check the most recent open order on a specific market.
		"""
		orders = self.api_signed_request('GET', '/v3/openOrders', {'symbol':fmt_market(market)})

		if not(len(orders) == 0):
			return({'data':orders})

		else: return('Empty')



	def cancel_open_orders(self, side, market):
			"""
			This is used to cancel all open orders for a specified market.
			"""
			orders = ""
			retries = 0
			maxRetries = 5
			token = market[market.index('-')+1:]
			orderCancled = False

			## This is used to get the current open orders.
			while not(orderCancled):
				openOrders = self.check_open_orders(market)

				if openOrders != 'Empty':
					## This checks if there is an open order.
					for order in openOrders['data']:

						## This checks the side of the order.
						if order['side'] == side or side == 'ALL':

							## This sets up the parameters and then sends a DELETE request.
							params = {'symbol':fmt_market(market), 'orderId':order['orderId']}
							self.api_signed_request('DELETE', '/v3/order', params)

							if self.get_balance(token)['locked'] == 0:
								if self.check_open_orders(market) == 'Empty':
									orderCancled = True

					if retries >= maxRetries:
						raise ValueError(openOrders,"cancel error")
					retries += 1

				else: orderCancled = True

			return(orderCancled)



	def check_closed_orders(self, side, market):
		"""
		This is used to check the market to see if there are any open trades that can be found.
		"""
		overallQuantity = 0
		ordersFound = 0
		boughtPrice = 0
		token 		= market[market.index('-')+1:]
		orders = (self.api_signed_request('GET', '/v3/allOrders', {'symbol':fmt_market(market)}))
		orders.reverse()

		if not(orders == "Empty"): 
			for order in orders:
				if order['side'] == side:

					if order['status'] == "FILLED":
						## This section is for loading in filled orders.
						currencyBalance = self.get_balance(token)['free']
						boughtPrice = float(order['price'])
						quantity = float(order['origQty'])
							
						if (currencyBalance >= quantity):
							return({"CALL":True, "data":{"status":"FILLED", "quantity":quantity, "price":boughtPrice}})
						else:
							break

					elif order['status'] == "CANCELED":
						## This section if for loading in part filled orders.
						quantity = float(order['origQty'])
						qRemaining = (quantity - float(order["executedQty"]))
						if qRemaining != quantity:
							currencyBalance = self.get_balance(token)['free']

							if currencyBalance >= qRemaining:
								return({"CALL":True, "data":{"status":"PART", "quantityRemaining":qRemaining, "Quantity":quantity, "price":float(order['price'])}})
							else:
								break

		return({"CALL":False, "data":{}})



	def get_sorted_candles(self, market, interval, limit):
		"""
		This is used to get the candles for a specific market and the interval.
		"""
		sortedCandles = None
		candles = None
		recivedData = False
		retries = 0
		maxRetries = 5

		try:
			candles = self.get_candles(market, interval, limit=limit)

			sortedCandles = TI.sort_candle(candles, "binance")
		except Exception as e:
			print_out(e, candles)

		return(sortedCandles)



	def get_candles(self, market, interval, **OPargs):
		"""
		This gets raw candles data from the binance exchange.
		"""
		params = {'symbol':fmt_market(market), 'interval':interval}
		params.update(OPargs)
		return(fmt_candles(self.api_request('GET', '/v1/klines', params)))



	def get_market_summary(self, typeData, market):
		"""
		This is used to get data about the market sumary
		"""
		param = {'symbol':fmt_market(market)}
		data = None

		try:
			if typeData == "orders":
				data = self.api_request('GET', '/v3/ticker/bookTicker', param)
				fData = {"bidPrice":float(data["bidPrice"]), "askPrice":float(data["askPrice"])}
			elif typeData == "last":
				data = self.api_request('GET', '/v3/ticker/price', param)
				fData = float(data["price"])
		except Exception as e:
			print_out(e, data)

		return(fData)



	def get_market_rules(self, market):
		"""
		This gets data from the current time to the last 24h.
		"""
		market = fmt_market(market)
		data = None

		get_data = self.api_request('GET', '/v1/exchangeInfo', {})

		for element in get_data['symbols']:
			if market in element['symbol']:
				data = element["filters"]
				break

		return(data)



	def get_24h(self, market):
		"""
		This gets data from the current time to the last 24h.
		"""
		params = {'symbol':fmt_market(market)}	
		return(self.api_request('GET', '/v1/ticker/24hr', params))



	def get_balance(self, token):
		"""
		This returns the balance for a specific token
		"""
		get_data = self.api_signed_request('GET', '/v3/account', {})
		data = None
		try:
			for element in get_data['balances']:
				if token == element['asset']:
					data = {'asset':element['asset'], 'free':float(element['free']), 'locked':float(element['locked'])}
					break
				
			if data == None: raise ValueError("Invalid Market")
		except Exception as e:
			message = "{0},{1}".format(e, get_data)
			sys.exit()

		return(data)



	def get_order_books(self, market, **OPargs):
		"""
		This gets data about the current orderbooks of a market.
		"""
		param = {'symbol':fmt_market(market)}
		param.update(OPargs)
		return(self.api_request('GET', '/v1/depth', param))



	def api_request(self, method, path, params=None):
		"""
		This is used to request public data from the exchange.
		"""
		data = None
		recivedData = False
		retries = 0
		maxRetries = 5
		query = path + str(params)

		while not(recivedData):
			api_resp = requests.request(method, BASE_API + path, params=params)

			try:
				data = api_resp.json()
			except Exception as e:
				print_out(query, error)
				data = {"error":{"message":error}}

			if(exchange_error_check(data, "")):
				recivedData = True
			elif retries >= maxRetries:
				sys.exit("error getting data (reached max retries)")
			else:
				retries += 1

		return(data)



	def api_signed_request(self, method, path, params=None):
		"""
		This is used to request secret data from the exchange.
		"""
		data = None
		recivedData = False
		retries = 0
		maxRetries = 5
		param_encode = urlencode(sorted(params.items()))

		if self.api_key == '' or self.api_secret == '':
			raise ValueError("Make sure you use your API key/secret")

		while not(recivedData):
			query = "%s&timestamp=%s" % (param_encode, int(time.time() * 1000))
			signature = hmac.new(bytes(self.api_secret.encode('utf-8')), (query).encode('utf-8'), hashlib.sha256).hexdigest()
			urlQuery = "%s%s?%s&signature=%s" % (BASE_API, path, query, signature)

			api_resp = requests.request(method, urlQuery, headers={'X-MBX-APIKEY':self.api_key})

			try:
				data = api_resp.json()
			except Exception as error:
				data = {"error":{"message":error}}

			if(exchange_error_check(data, query)):
				recivedData = True
			elif retries >= maxRetries:
				sys.exit("error getting data (reached max retries)")
			else:
				retries += 1
					
		return(data)



def exchange_error_check(data, query):
	"""
	This section is used to handle any error messages that may be recived by the exchange.
	"""
	if "error" in data or data == None:
		error = data["error"]["message"]
		if error == "Timestamp for this request is outside of the recvWindow, getting new timestamp.":
			time.sleep(2.5)
		elif error in ["Connection aborted", "HTTPSConnectionPool", "NewConnectionError"]:
			print_out(error, query)
			ping()
		else:
			print_out(error, query)
			raise ValueError(error)
		return(False)

	return(True)



def ping():
	"""
	This returns a response to a ping request
	"""
	retries = 0
	maxRetries = 5
	fullPath = '%s/v1/ping' % (BASE_API)
	hostname = "www.google.com"

	while retries < maxRetries:
		time.sleep(10)
		response = os.system("ping -c 1 " + hostname)

		if response == 0:
			binanceResponse = requests.request('GET', fullPath)
			if "Response" in str(binanceResponse):
				return(True)

		retries += 1
		print("connection error, retries {0} out of {1}".format(retries, maxRetries))
	
	return(False)



def fmt_market(market):
	"""
	Used to format the market for binance.
	"""
	market = market.upper()

	try:
		return("%s%s" % (market[market.index("-")+1:], market[:market.index("-")]))
	except ValueError:
		raise ValueError("Incorrect market format, Use (Market-Asset)")



def fmt_candles(candles):
	"""
	Used to format the candles to a global format.
	{"OpenTime":, "Open":, "High":, "Low":, "Close":, "Volume":}
	"""
	newCandles = [{"OpenTime":i[0], "Open":float(i[1]), "High":float(i[2]), "Low":float(i[3]), "Close":float(i[4]), "Volume":float(i[5])} for i in candles]
	newCandles.reverse()

	return(newCandles)


def print_out(error, query=""):
	## Just to print out trade info to log files.
	currentTime 	= time.localtime()
	fTime 			= "{0}:{1}:{2}".format(currentTime[3], currentTime[4], currentTime[5])

	errorStr = "{0} | ERROR: {1}, queryif: {2}".format(fTime, error, query)

	logFile = open(logFileName, 'a')
	logFile.write(errorStr+"\n")
	logFile.close()