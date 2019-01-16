#! /usr/bin/env python3

"""
VERSION			: 6.5
PYTHON SCRIPT	: Trading_Bot.py
DESCRIPTION		: Trading bot object for Binance.
"""
import os
import sys
import time
import TradeIndicators as TI
from decimal import Decimal
from calls import Calls

## This is available time intervals.
TIME_INTERVALS = ["1m", "3m", "5m", "15m", "1h", "4h"]


class trader(object):

	def __init__(self, publicKey, privateKey, market, maxACurrency, timeInterval):

		## This section is for verifying the time intervals.
		if timeInterval not in TIME_INTERVALS:
			raise ValueError("{0} in-valid time interval.".format(timeInterval))

		## <----------------------------------| INITIAL VARIABLES |-----------------------------------> ##
		self.call 			= Calls(publicKey, privateKey)
		self.timeInt 		= timeInterval 									# This is used to hold the time interval.
		self.lastUpdateTime = {"U":0, "B":0, "S":0, "O":0, "rRSI":0, "candle":0, "Test":0}		# Timing used for bot, U - Updates, B - orderbook updates, O is for placing orders.
		self.fCandles 		= []											# This is used to hold formatted candles.
		## <------------------------------------------------------------------------------------------> ##

		## This is used to lead the filters for a specific market.
		filters = self.call.get_market_rules(market)

		## This sets up the LOT_SIZE for the market.
		if float(filters[2]["minQty"]) < 1.0:
			minQuantBase = (Decimal(filters[2]["minQty"])).as_tuple()
			LOT_SIZE = abs(int(len(minQuantBase.digits)+minQuantBase.exponent))+1
		else: LOT_SIZE = 0

		## This is used to set up the price precision for th market.
		tickSizeBase = (Decimal(filters[0]["tickSize"])).as_tuple()
		TICK_SIZE = abs(int(len(tickSizeBase.digits)+tickSizeBase.exponent))+1

		## This is used to get the markets minimal notation.
		MINIMUM_NOTATION = float(filters[3]["minNotional"])

		## <----------------------------------| MAIN tRADER VARIABLES |-----------------------------------> ##
		self.traderInfo = {							#
			"market":market,						# "market" this holds the current market that the bot is trading.
			"MAC":maxACurrency,						# "MAC" this holds the Maximum Allowed Currency the bot can trade with.
			"currencyLeft":maxACurrency,			# "currencyLeft" this holds the currency the bot has left to trade.
			"status":"RUNNING",						# "status" holds the current status of a bot ([RUNNING/STANDBY/TRADING_PAUSE])
			"CMI":{									# This section holds data based on the current market.
				"lastPrice":0,						# "lastPrice" this holds the last price of the market.
			},										#
			"CTI":{									# This section holds data relevent to the current trades.
				"buyPrice":0,						# "buyPrice" this holds the buy price for the bot.
				"sellPrice":0,						# "sellPrice" this holds the sell price of the bot.
				"tokenBase":0,						# "tokenBase" this holds the base tokens bought.
				"tradeTypes":{"B":"Wait","S":None},	# "tradeTypes" holds the current type of trade being carried out (B:[Wait/Signal/RSI] S:[Limit/Signal/Trail])
				"orderStatus":{"B":None, "S":None}	# "orderStatus" holds the status for the current order (B:[None/Placed/PF/Locked] S:[None/Placed/PF/Locked/PF_Sig])
			},										#
			"TS":{									# This section holds data relevent to trade statistics and settings
				"updateOrder":False,				# "updateOrder" this is used to determin if a placed order should be updated
				"#Trades":0,						# "#Trades" this holds the number of FULL trades made by this market.
				"overall":0,						# "overall" this holds the overall outcomes for this markets trades. 
			},										#
			"MR":{									# This section is for holding the market rules.
				"LOT_SIZE":LOT_SIZE,				# "LOT_SIZE" this is used to hold the lot size for a market.
				"TICK_SIZE":TICK_SIZE,				# "TICK_SIZE" this holds the tick size for a market.
				"MINIMUM_NOTATION":MINIMUM_NOTATION # "MINIMUM_NOTATION" this is used to hold the minimum notation for a market.
			},										#
			"Ind":{									# This section is for holding indicator data. [ADDIND]
				"MACD":0
			},										#				
			"time":0}								# "time" is used to hold update time (mainly for testing).
		## <----------------------------------------------------------------------------------------------> ##
		self.call.cancel_open_orders("ALL", market)

		## This section looks over previous order and checks if there is an unfinished trade and if so it will try and continue that trade.
		balanceBTC = self.call.get_balance("BTC")
		balanceToken = self.call.get_balance(market[market.index('-')+1:])
		lastPrice = self.call.get_market_summary("last", market)
		
		if (balanceToken['free']*lastPrice) >= MINIMUM_NOTATION:
			closedOrder = self.call.check_closed_orders("BUY", market)
			## This will load the last FILLED order and use that orders price as the buy price for display.
			if closedOrder["CALL"] != False:
				order = closedOrder['data']
				if order['status'] == 'FILLED':
					self.traderInfo["CTI"]["buyPrice"] = order["price"]

			self.traderInfo["CTI"]["tokenBase"]	= balanceToken['free']
			self.setup_sell()

		elif balanceBTC['free'] < maxACurrency:
			sys.exit("Not enough BTC to start trading gave bot {0}, free BTC is {1}".format(maxACurrency, balanceBTC['free']))



	def update(self, forceUpdate):
		"""
		This section is incharge of updating and getting data for indicators.
		"""
		intervalUpdate = False
		localTime 	= time.localtime()
		unixTime	= time.time()
		market 		= self.traderInfo["market"]
		call 		= self.call
		fcandles 	= self.fCandles


		"""##############					 ##############
		##############	 Timing For Bot Func 	############## 	
		"""##############					 ##############
		if self.timeInt[-1] == "m":
			currentTime = localTime[4]
		elif self.timeInt[-1] == "h":
			currentTime = localTime[3]

		## This sets up and for interval updates
		if (currentTime != self.lastUpdateTime["U"] and (currentTime % int(self.timeInt[0:-1]) == 0)) or (forceUpdate):
			self.lastUpdateTime["U"] = currentTime
			intervalUpdate = True

		## THis will update candles every 10s or on candle close.
		if (self.lastUpdateTime["candle"]+20) <= unixTime or intervalUpdate:
			self.lastUpdateTime["candle"] = unixTime
			fcandles = call.get_sorted_candles(market, self.timeInt, 400)
			self.traderInfo["CMI"]["lastPrice"] = fcandles["close"][0]

		## This is used for very simple error correction.
		if self.traderInfo["status"] == "STANDBY_ERROR":
			self.traderInfo["status"] = "RUNNING"

		try:
			## This section is for adding indicators [PLACEINDS]
			
			self.traderInfo["Ind"]["MACD"] = TI.get_MACD(fcandles["close"], 12, 26, 9, 4)

			## --------------------------------------->
		except Exception as e:
			print("Error with Indicators!")
			print(e)
			self.traderInfo["status"] = "STANDBY_ERROR"


		self.fCandles = fcandles


	def main(self):
		"""
		This is the main order loop for managing and placing orders/re-entries.
		"""
		tInfo = self.traderInfo

		if tInfo["CTI"]["orderStatus"]["B"] != None or tInfo["CTI"]["orderStatus"]["S"] != None:
			self.manage_order_status()

		if self.traderInfo["status"] == "RUNNING":
			self.trade_conditions()



	"""
	[#######################################################################################################################]
	[###################################################] Check Orders [####################################################]
	[#############################################]v^v^v^v^v^v^vv^v^v^v^v^v^v[##############################################]
	"""
	def manage_order_status(self):
		"""
		This is the manager for all and any orders.
		"""
		call = self.call
		tInfo = self.traderInfo
		market = tInfo['market']
		token = market[market.index('-')+1:]
		side = "BUY" if tInfo["CTI"]["tradeTypes"]["S"] == None else "SELL"
		manager = call.order_manager(tInfo, side)

		if manager["code"] != 210:
			print(manager, market)

		self.code_manager(manager["code"], side)
					
		if manager["code"] == 200:
			if side == "BUY":
				balance = call.get_balance(token)
				self.traderInfo["CTI"]["tokenBase"]	= balance['free']
				self.setup_sell()

			elif side == "SELL":
				fee = self.traderInfo["MAC"] * 0.0002
				self.traderInfo["TS"]["overall"] += float("{0:.8f}".format(((tInfo["CTI"]["sellPrice"]-tInfo["CTI"]["buyPrice"])*tInfo["CTI"]["tokenBase"])-fee))
				self.traderInfo["TS"]["#Trades"] += 1
				self.setup_buy()


	"""
	[#######################################################################################################################]
	[##################################################] Order Condition [##################################################]
	[#############################################]v^v^v^v^v^v^vv^v^v^v^v^v^v[##############################################]
	"""
	def trade_conditions(self):
		tInfo = self.traderInfo
		call = self.call
		market = tInfo["market"]
		updateOrder = tInfo["TS"]["updateOrder"]
		marketSummary = call.get_market_summary("orders", market)
		lastPrice = call.get_market_summary("last", market)
		order = {"place":False}
		orderSignal = False

		## locally declare indicators here [LOCIND]:
		MACD = tInfo["Ind"]["MACD"]


		## --------------------------------------->


		if tInfo["CTI"]["tradeTypes"]["S"] != None:
			"""##############					  ##############
			##############      SELL CONDITIONS 	 ############## 	
			"""##############					  ##############

			## Put SELL conditions here [TRADESELL]:

			if MACD[0]["fast"] < MACD[1]["fast"] and MACD[0]["fast"] < MACD[0]["slow"]:
				orderSignal = True
				price = marketSummary["askPrice"]
			elif lastPrice < tInfo["CTI"]["buyPrice"]-(tInfo["CTI"]["buyPrice"]*0.02):
				orderSignal = True
				price = lastPrice

			## --------------------------------------->

			## This is used to set up signal and also reset if there is no signal.
			if orderSignal:
				self.traderInfo["CTI"]["tradeTypes"]["S"] = "Signal"
			elif not(orderSignal) and tInfo["CTI"]["tradeTypes"]["S"] == "Signal":
				self.traderInfo["CTI"]["tradeTypes"]["S"] = "Wait"
				call.cancel_open_orders("ALL", market)

			## The below block is used to tell the bot to place a new SELL order.
			if self.traderInfo["CTI"]["tradeTypes"]["S"] == "Signal":
				if self.traderInfo["CTI"]["tradeTypes"]["S"] == "Signal" and (tInfo["CTI"]["orderStatus"]["S"] == None or updateOrder):
					if updateOrder: self.traderInfo["TS"]["updateOrder"] = False
					fprice = float("{0:.{1}f}".format(price, 8)) # This formats the SELL price before using it to place the order.
					order = {"place":True, "side":"SELL"} # This is used so the bot knows to place an order and what side to place it for.
				

		elif tInfo["CTI"]["tradeTypes"]["B"] != None:
			"""##############					 ##############
			##############		BUY CONDITIONS 		############## 	
			"""##############					 ##############

			## Put BUY conditions here [TRADEBUY]:

			if MACD[0]["fast"] > MACD[1]["fast"] and MACD[1]["fast"] > MACD[1]["slow"]: 
				orderSignal = True
				price = marketSummary["bidPrice"]

			## --------------------------------------->

			## This is used to set up signal and also reset if there is no signal.
			if orderSignal:
				self.traderInfo["CTI"]["tradeTypes"]["B"] = "Signal"
			elif not(orderSignal) and tInfo["CTI"]["tradeTypes"]["B"] == "Signal":
				self.traderInfo["CTI"]["tradeTypes"]["B"] = "Wait"
				call.cancel_open_orders("ALL", market)

			## The below block is used to tell the bot to place a new BUY order.
			if self.traderInfo["CTI"]["tradeTypes"]["B"] == "Signal":
				if self.traderInfo["CTI"]["tradeTypes"]["B"] == "Signal" and (tInfo["CTI"]["orderStatus"]["B"] == None or updateOrder):
					if updateOrder: self.traderInfo["TS"]["updateOrder"] = False
					fprice = float("{0:.{1}f}".format(price, 8)) # This formats the BUY price before using it to place the order.
					order = {"place":True, "side":"BUY"} # This is used so the bot knows to place an order and what side to place it for.


		## All orders to be placed will be managed via the trade manager.
		if order["place"]:
			manager = call.trade_manager(self.traderInfo, order["side"], fprice)
			print(manager, market) # for debugging to print out the orders returned status.
			self.code_manager(manager["code"], order["side"], price=fprice)



	def code_manager(self, code, side, **OPargs):
		"""
		This is used to manage the codes that the managers return and act acording to if its an error or a successfull call.
		"""
		tInfo = self.traderInfo

		if code == 0:
			## Unknown Error.
			pass
		elif code == 100:
			## Order has been placed.
			if side == "BUY":
				self.traderInfo["CTI"]["orderStatus"]["B"] = "Placed"
				self.traderInfo["CTI"]["buyPrice"] = OPargs["price"]
			else:
				self.traderInfo["CTI"]["orderStatus"]["S"] = "Placed"
				self.traderInfo["CTI"]["sellPrice"] = OPargs["price"]

			self.traderInfo["CTI"]["canOrder"] = False

		if code == 101:
			self.traderInfo["status"] = "STANDBY"

		elif code == 102 or code == 201:
			self.setup_sell()
			self.traderInfo["CTI"]["tradeTypes"]["B"] = None
			self.traderInfo["CTI"]["tradeTypes"]["S"] = "Wait"

		elif code == 103 or code == 202:
			self.setup_buy()
			self.traderInfo["CTI"]["tradeTypes"]["B"] = "Wait"
			self.traderInfo["CTI"]["tradeTypes"]["S"] = None

		elif code == 211:
			## Current order is part filled.
			if side == "BUY" and tInfo["CTI"]["orderStatus"]["B"] != "Order_Lock":
				self.traderInfo["CTI"]["orderStatus"]["B"] = "PF"

			if side == "SELL" and tInfo["CTI"]["orderStatus"]["S"] != "Order_Lock":
				self.traderInfo["CTI"]["orderStatus"]["S"] = "PF"

		elif code == 212:
			## Buy order needs locked.
			self.traderInfo["CTI"]["orderStatus"]["B"] = "Order_Lock"

		elif code == 213:
			## Sell order needs locked.
			self.traderInfo["CTI"]["orderStatus"]["S"] = "Order_Lock"

		else:
			pass



	def setup_sell(self):
		self.traderInfo["CTI"]["orderStatus"]["B"] 	= None
		self.traderInfo["CTI"]["tradeTypes"]["B"]	= None
		self.traderInfo["CTI"]["tradeTypes"]["S"] 	= "Wait"
		self.traderInfo["currencyLeft"]				= 0



	def setup_buy(self):
		self.traderInfo["CTI"]["orderStatus"]["S"]	= None
		self.traderInfo["CTI"]["tradeTypes"]["S"]	= None
		self.traderInfo["CTI"]["tradeTypes"]["B"]	= "Wait"
		self.traderInfo["CTI"]["tokensHolding"] 	= 0
		self.traderInfo["CTI"]["sellPrice"] 		= 0
		self.traderInfo["CTI"]["buyPrice"] 			= 0
		self.traderInfo["currencyLeft"]				= self.traderInfo["MAC"]



	def give_bot_info(self, newInfo):
		# This is used to give data to the bot.
		self.traderInfo = newInfo



	def get_bot_info(self):
		## This is used to return data about the bot.
		currenyTime = time.localtime()
		self.traderInfo["time"] = "{0}:{1}:{2}".format(currenyTime[3], currenyTime[4], currenyTime[5])
		return(self.traderInfo)


