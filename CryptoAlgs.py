#! /usr/bin/env python3

import numpy as np
import statistics as stat

""" Base file used for my crypto  trading Algorithms, Indicators and formatting. """


"""
[######################################################################################################################]
[#############################################] TAS & INCICATORS SECTION [##############################################]
[#############################################]v^v^v^v^v^v^vv^v^v^v^v^v^v[##############################################]
"""


def calculate_BOLL(prices, SMA_Len=21, dp=8):
	"""
	This is used to calculate all 3 BOLL bands.
	SMA = 21, D = 2
	"""
	#print(prices)
	stdev = stat.stdev(prices[:SMA_Len])
	SMA = float("{0:.{1}f}".format(get_SMA(prices, SMA_Len)[0], dp))
	BTop = float("{0:.{1}f}".format(SMA + (stdev * 2), dp))
	BBot = float("{0:.{1}f}".format(SMA - (stdev * 2), dp))
	band = {"M":SMA, "T":BTop, "B":BBot}

	return(band)


def get_SMA(closePrices, ma_type, ma_Span=1, dp=8):
	"""
	This is used to get any amount of MAs.
	MA = for x closes + each and / by x.
	"""
	ma_list = []
	ma = 0
	ma_start = 0
	ma_end = ma_type

	for n in range(ma_Span):
		for price in range(ma_start, ma_end):
			ma += closePrices[-(1+price)]

		ma_start += 1
		ma_end += 1
		ma_list.insert(n, (float("{0:.{1}f}".format(ma/ma_type, dp))))
		ma = 0

	return ma_list


"""
[################################################################################################################################]
[######################################################] BUY/SELL SIGNALS [######################################################]
[######################################################]v^v^v^v^vv^v^v^v^v[######################################################]
"""


def calculate_MA_buy(current, ma_short, ma_long):
	""" 
	This is used to calculate a buy using MAs.
	Normal Buy = 7MA under the 21MA, 7MA is uptrending, the current price is lower than the 21MA.
	"""
	if ma_short[0] < ma_long[0]:
		if (ma_short[0 > ma_short[1]]) and (current < ma_long[0]):
			return ("Normal")
	return (None)


def calculate_MA_sell(currentPrice, closePrice, buyPrice, ma_short, ma_long, ma_boundy,lossThreshold=0.02):
	""" 
	This is used to calculate a sell using MAs.
	ma_short = the smallest MA span
	ma_long = the biggest MA span
	ma_boundry = the sell boundry

	Normal Sell = 7MA over the 21MA, last candle closing price is under the 7MA, current price is greater than 21MA.
	Stop Loss = MA7 is downtrending, current price is lower or equal to the stop loss.
	"""
	stopLoss = buyPrice - (buyPrice * (lossThreshold / 100))

	if (ma_short[0] > (ma_long[0])):
		if (closePrice < ma_boundry[0]) and (currentPrice > ma_long[0]):
			return ("Normal")
	elif (currentPrice <= stopLoss) and (ma_short[0] < ma_short[1]):
		return ("Loss")

	return (None)


def calculate_BOLL_buy(BOLL, currentPrice):
	"""
	This is used to calculate the BOLL band buy.
	Normal = Current price less than BOLL bottom.
	"""
	if currentPrice <= BOLL["B"]:
		return ("Normal")

	return (None)


def calculate_BOLL_sell(BOLL, currentPrice, buyPrice, lossThreshold=0.02):
	"""
	This is used to calculate the BOLL band sell.
	Low = If the price goes over the mid band and back under it will sell.
	High = Current price = BOLL band top price.
	"""
	stopLoss = buyPrice - (buyPrice * (lossThreshold / 100))
	BOLLDiff = 100 * (BOLL["M"] / (BOLL["T"] - BOLL["M"]))
	lowSellPrice = BOLL["M"] - ( BOLL["M"] * ((BOLL["M"] / 2) / 100))

	#if crossedMiddle and (currentPrice < (BOLL["M"] - ((BOLL["M"] - BOLL["B"])/2))):
	if currentPrice >= BOLL["M"]:
		#If price is dropped lower than half of the difference( if diff is 1% dont let price drop lower than 0.5%)
		return ("Low")
	elif currentPrice >= BOLL["T"]:
		#If the price goes up over the top line wait untill it crosses it and starts to drop to sell.
		return ("High")
	elif currentPrice <= stopLoss:
		return("Loss")
	# Add stop loss for any% and if stop loss is reached make sure that the 7ma is at 55 degree andgle or less before buying again

	return (None)


"""
[################################################################################################################################]
[#####################################################] FORMATTING SECTION [#####################################################]
[#####################################################]v^v^v^v^v^^v^v^v^v^v[#####################################################]
"""

def sort_candle(candles):
	"""
	Sorts the candles in a nice columns.
	"""
	candleInfo = {"open":[],"high":[],"low":[],"close":[],"volume":[]}

	for i in range(len(candles)):
		candleInfo["open"].insert(i, candles[i]["Open"])
		candleInfo["high"].insert(i, candles[i]["High"])
		candleInfo["low"].insert(i, candles[i]["Low"])
		candleInfo["close"].insert(i, candles[i]["Close"])
		candleInfo["volume"].insert(i, candles[i]["Volume"])

	return(candleInfo)
	
