#! /usr/bin/env python3

def fmt_Msymbol(exchange, market):
	"""
	Binance = MarketCoin (BTCLTC, BTCNEO)
	Bittrex = Coin-Market (BTC-LTC, BTC-NEO)
	"""
	fMarket = ""
	market = market.upper()

	try:
		if exchange == "binance":
			fMarket = market[market.index("-")+1:] + market[:market.index("-")]
		if exchange == "bittrex":
			fMarket = market

		return(fMarket)
	except ValueError:
		raise ValueError("Incorrect market format, Use (Market-Asset)")


def fmt_balance(exchange, balance):
	"""
	Used to format the balance to a global format.
	{"Token":, "Total":, "Available":, "unAvailable":}
	"""
	fBalance = {}

	if exchange == "bittrex":
		fBalance = {"Token":balance["Currency"], "Total":balance["Balance"], "Available":balance["Available"], "unAvailable":balance["Pending"]}
	if exchange == "binance":
		total = float(balance["free"]) + float(balance["locked"])
		fBalance = {"Token":balance["asset"], "Total":total, "Available":float(balance["free"]), "unAvailable":float(balance["locked"])}
	return(fBalance)


def fmt_market_sum(exchange, data):
	"""
	Global format for market summary
	{"Market":, "Last":, "Buy":, "Sell":}
	"""
	fSummary = {}

	if exchange == "binance":
		fSummary = {"Market":data["symbol"], "Last":float(data["price"]), "Buy":float(data["bidPrice"]), "Sell":float(data["askPrice"])}
	elif exchange == "bittrex": 
		fSummary = {"Market":data["MarketName"], "Last":data["Last"], "Buy":data["Bid"], "Sell":data["Ask"]}

	return(fSummary)


def fmt_candles(exchange, candles):
	"""
	Used to format the candles to a global format.
	{"OpenTime":, "Open":, "High":, "Low":, "Close":, "Volume":}
	"""
	candleFormat = {}
	newCandles = []

	for i in candles:
		if exchange == "binance":
			candleFormat = {"OpenTime":i[0], "Open":float(i[1]), "High":float(i[2]), "Low":float(i[3]), "Close":float(i[4]), "Volume":float(i[5])}
		if exchange == "bittrex":
			candleFormat = {"OpenTime":i["T"], "Open":i["O"], "High":i["H"], "Low":i["L"], "Close":i["C"], "Volume":i["V"]}
		newCandles.append(candleFormat)

	if exchange == "binance":
		newCandles.reverse()

	return(newCandles)


def fmt_orders(exchange, orders):
	"""
	Used to format the order data to a global format.
	{"Type":, "Quantity":, "QuantityRemaining":, "Price":, "PricePerUnit":,"Commission": , "Time":}
	"""
	orderFormat = {}
	newOrders = []

	if not(len(orders) == 0):
		for i in orders:
			if exchange == "bittrex":
				if i["OrderType"] == "LIMIT_SELL": orderType = "SELL"
				elif i["OrderType"] == "LIMIT_BUY": orderType = "BUY"
				orderFormat = {"Type":orderType, "ID":i["OrderUuid"], "Status":None, "Quantity":i["Quantity"], "QuantityRemaining":i["QuantityRemaining"], "Price":i["Price"], "PricePerUnit":i["PricePerUnit"], "Time":i["TimeStamp"]}
			if exchange == "binance":
				overall = float('%.8f' % round((float(i["origQty"]) * float(i["price"])),8))
				orderFormat = {"Type":i["side"], "ID":i["orderId"], "Status":i["status"], "Quantity":float(i["origQty"]), "QuantityRemaining":None, "Price":overall, "PricePerUnit":float(i["price"]), "Time":i["time"]}
			newOrders.append(orderFormat)

		if exchange == "binance":
			newOrders.reverse()
		return(newOrders)
	else: return("Empty")