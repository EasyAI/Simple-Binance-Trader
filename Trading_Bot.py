#! /usr/bin/python3

"""
PYTHON SCRIPT: Trading_Bot
DESCRIPTION: Fist usdt-BTC binance BOLL stage trading bot.
AUTHER: JohnL
"""
import os
import sys
import time
import json
import algs as CA
from decimal import Decimal
from gexchange import g_exchange

class trader(object):


	def __init__(self, publicKey, privateKey, market, currencyAmount, timeInterval, stopLossThreshold=0.5):
		self.exchange = g_exchange("binance", publicKey, privateKey)
		self.market = market
		self.timeInt = timeInterval
		self.stopLoss = stopLossThreshold/100

		allowedCurrency = float("{0:.{1}f}".format(currencyAmount, 7))

		filters = self.exchange.get_marketInfo(market)['filters']
		minQuantBase = (Decimal(filters[1]["minQty"])).as_tuple()
		tickSizeBase = (Decimal(filters[0]["tickSize"])).as_tuple()

		self.marketRules = {
			"minQty":abs(int(str(len(minQuantBase.digits)+minQuantBase.exponent)))+2,
			"tickSize":abs(int(str(len(tickSizeBase.digits)+tickSizeBase.exponent)))+1
		}

		## ----------------------------| MAIN VARIABLES |---------------------------->
		self.botTraderInfo = {					# 
			"lastPrice":0, 						# Holds current price
			"askPrice":0, 						# Holds Ask price
			"bidPrice":0, 						# Holds Bid price
			"buyPrice":0, 						# Holds Buy price
			"sellPrice":0, 						# Holds Sell price
			"tOutcome":0, 						# Holds outcome of trades
			"allowedCurrency":allowedCurrency, 	# Holds currency amount for trades
			"hAmount":0, 						# Holds the amount of assets held
			"orderPlaced": False,				# Holds if order placed or not
			"cTrade":"Buy",						# Holds the currenct trade type (BUY/SELL)
			"#Trades":0, 						# Holds overal number of trades
		}										#
		## --------------------------------------------------------------------------->

		## This section is for getting time interval dividers.
		if timeInterval == "1m": self.divider = 1
		elif timeInterval == "5m": self.divider = 5
		elif timeInterval == "30m": self.divider = 30
		else: raise ValueError("{0} in-valid time interval.".format(timeInterval))

		## This is for checing for an active trade.
		activeTrades = check_active_trades(self.exchange, market)

		if activeTrades == None:
			print("{0}: No".format(market[market.index("-")+1:]))
		elif type(activeTrades) == list:
			print("{0}: Yes".format(market[market.index("-")+1:]))
			self.botTraderInfo["buyPrice"] = activeTrades[0]
			self.botTraderInfo["hAmount"] = activeTrades[1]
			self.botTraderInfo["cTrade"] = "Sell"


		self.lastUpdateTime = 0
		self.fCandles = []
		self.MA8 = 0
		self.BOLL = []

	def update(self, forceUpdate):
		"""
		forceUpdate boll
		"""
		currentTime = time.localtime()
		exchange = self.exchange
		market = self.market
		marketSum = exchange.get_market_summary(market)
		timeInt = self.timeInt
		divider = self.divider
		lastUpdateTime = self.lastUpdateTime

		traderInfo = self.botTraderInfo

		## Used to find out when to update the candles in minuets.
		if (currentTime[4] != lastUpdateTime and (currentTime[4] % divider == 0)) or (forceUpdate):
			self.lastUpdateTime = currentTime[4]

			self.fCandles = self.get_candle_data(market, timeInt)
			
			self.BOLL = CA.calculate_BOLL(self.fCandles["close"][:21])

		self.botTraderInfo["lastPrice"] = marketSum["Last"]
		self.botTraderInfo["askPrice"] = marketSum["Sell"]
		self.botTraderInfo["bidPrice"] = marketSum["Buy"]


	def find_trade(self):
		"""
		This functionis to:
		- to calculate if there is any chance of a possible buy/sell.
		- Check if the order has been filled.
		- update any trailing orders.
		- update information based on trades.
		"""
		market = self.market
		exchange = self.exchange
		traderInfo = self.botTraderInfo
		stopLoss = self.stopLoss
		fCandles = self.fCandles

		### This section is for updating trade information and also for checking if orders have been filled or not ###
		if (self.botTraderInfo["orderPlaced"]):
			openOrders = exchange.get_orders_open(market)

			if openOrders == "Empty":
				if traderInfo["cTrade"] == "Buy":
					self.botTraderInfo["cTrade"] = "Sell"

				elif traderInfo["cTrade"] == "Sell":

					self.botTraderInfo["tOutcome"] += (self.botTraderInfo["sellPrice"]-self.botTraderInfo["buyPrice"])*((self.botTraderInfo["hAmount"]))
					self.botTraderInfo["hAmount"] = 0
					self.botTraderInfo["buyPrice"] = 0
					self.botTraderInfo["cTrade"] = "Buy"
					self.botTraderInfo["#Trades"] += 1

				self.botTraderInfo["sHigh"] = 0
				self.botTraderInfo["sCurrent"] = 0
				self.botTraderInfo["orderPlaced"] = False


		### This section is for setting up normal buys on the market ###
		if traderInfo["cTrade"] == "Buy":
			instruction = CA.calculate_BOLL_buy(self.BOLL, traderInfo["lastPrice"])

			if instruction == "Normal":
				## This is used to place an initial buy stoploss
				if self.set_buy('Normal'):
					self.botTraderInfo["orderPlaced"] = True
					print("new buy order")


		### This section is for setting up normal sells and stoplosses on the market ###
		if traderInfo["cTrade"] == "Sell":

			instruction = CA.calculate_BOLL_sell(self.BOLL, traderInfo["lastPrice"], traderInfo["buyPrice"])

			if traderInfo["lastPrice"] <= traderInfo["buyPrice"] - (traderInfo["lastPrice"]*stopLoss):
				if self.set_sell('Loss'):
					self.botTraderInfo["orderPlaced"] = True
					print("Loss sell")

			elif instruction == 'Low':
				if self.set_sell('Normal'):
					self.botTraderInfo["orderPlaced"] = True
					print("New sell order")


	def set_buy(self, oType):
		"""
		This is used to set a buy order or trailing buy onto the market.
		"""
		exchange = self.exchange
		traderInfo = self.botTraderInfo
		market = self.market
		orderOutcome = False


		if oType == 'Normal':
			price = "{0:.{1}f}".format(traderInfo["lastPrice"], self.marketRules["tickSize"])
			quantity = "{0:.{1}f}".format(traderInfo["allowedCurrency"]/float(price), self.marketRules["minQty"])

			orderOutcome = exchange.post_buy(market=market, quantity=quantity, price=price)
			self.botTraderInfo["hAmount"] = quantity
			self.botTraderInfo["buyPrice"] = price
			orderOutcome = True

		return(orderOutcome)


	def set_sell(self, oType):
		"""
		This is used to set a sell order or trailing sell onto the market.
		"""
		exchange = self.exchange
		traderInfo = self.botTraderInfo
		market = self.market
		cancel_open_orders(exchange, market)
		orderOutcome = False

		if oType == 'Normal':
			price = "{0:.{1}f}".format(traderInfo["lastPrice"], self.marketRules["tickSize"])
			quantity = "{0:.{1}f}".format(traderInfo["hAmount"], self.marketRules["minQty"])
			self.botTraderInfo["sellPrice"] = price

			orderOutcome = exchange.post_sell(market=market, quantity=quantity, price=price)
			orderOutcome = True

		elif oType == 'Loss':
			price = "{0:.{1}f}".format(traderInfo["lastPrice"], self.marketRules["tickSize"])
			quantity = "{0:.{1}f}".format(traderInfo["hAmount"], self.marketRules["minQty"])
			self.botTraderInfo["sellPrice"] = price

			orderOutcome = exchange.post_sell(market=market, quantity=quantity, price=price)
			orderOutcome = True

		return(orderOutcome)

				
	def print_out_statistics(self):
		## Just to print out stats for the user to see.
		traderInfo = self.botTraderInfo
		BOLL = self.BOLL
		stoploss = traderInfo['buyPrice']-(traderInfo['buyPrice']*(self.stopLoss))
		diffBOLL = "{0:.{1}f}".format((BOLL["T"]-BOLL["M"])/BOLL["M"]*100, 2)

		print("\nMarket: {0} | Trade Status: {1}ing | Outcome: {2:.7f} from {3} trades.".format(self.market.upper(), traderInfo['cTrade'], traderInfo['tOutcome'], traderInfo['#Trades']))
		print("Holding: {0:.7f} | Current: {1:.7f} | stop-loss: {2:.7f}".format(traderInfo['hAmount'], traderInfo['lastPrice'], stoploss))
		print("Buy Price: {0:.7f} | Sell Price: {1:.7f}".format(traderInfo['buyPrice'], traderInfo['sellPrice']))
		print("Top: {0:.7f} | Mid: {1:.7f} | Bot: {2:.7f} | % Diff(BOLL): {3}".format(BOLL['T'], BOLL['M'], BOLL['B'], diffBOLL))


	def get_candle_data(self, market, interval):
		## This function is for setting up the candles via the multiprocess setup.
		rCandles = {} #Stores raw candle data.
		candleInfo = {} #This holds the processed candle data.
		exchange = self.exchange

		rCandles = exchange.get_candles(market=market, interval=interval, limit="30")
		candleInfo = CA.sort_candle(rCandles)

		return (candleInfo)


	def get_bot_data(self):
		# This is used to return data about the bot.
		return(self.botTraderInfo)


def cancel_open_orders(exchange, market):
	openOrders = exchange.get_orders_open(market)

	if not(openOrders == "Empty"):
		for order in openOrders:
			exchange.cancel_order(market, order["ID"])

		if exchange.get_orders_open(market) == "Empty": return(True)
		else: return(False)


def check_active_trades(exchange, market):
	cancel_open_orders(exchange, market)
	marketAsset = exchange.get_balance(market[market.index("-")+1:])["Available"]
	marketCurrency = exchange.get_balance(market[:market.index("-")])["Available"]

	orders = exchange.get_orders_closed(market)

	## This checks and recent order to see if there is possibly an uncompleted trade that was made by the bot,
	## if so the bot will try to continue from the last trade.
	if not(orders == "Empty"): 
		for order in orders:
			if order["Status"] == "FILLED":
				if order["Type"] == "BUY":
					boughtPrice = order["PricePerUnit"]
					quantity = order["Quantity"]
						
					if (marketAsset >= quantity):
						return([boughtPrice, quantity])

				elif order["Type"] == "SELL":
					break
	return(None)