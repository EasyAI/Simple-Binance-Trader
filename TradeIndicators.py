#! /usr/bin/env python3

import sys
import numpy as np
import statistics as stat

""" Base file used for my crypto  trading Algorithms, Indicators and formatting. """

"""
[######################################################################################################################]
[#############################################] TAS & INCICATORS SECTION [##############################################]
[#############################################]v^v^v^v^v^v^vv^v^v^v^v^v^v[##############################################]

### Indicators List ###
- BB
- RSI
- StochRSI
- SMA
- EMA
- SS
- MACD
- TR
- ATR
- DM
- ADX_DI
- Ichimoku
"""



## This function is used to calculate and return the Bollinger Band indicator.
def get_BOLL(prices, SMA_Len=21):
	"""
	This function uses 2 parameters to calculate the BB-
	
	[PARAMETERS]
		prices	: A list of prices.
		SMA_Len	: BB ma type.
	
	[CALCULATION]
		---
	
	[RETURN]
		[{
		'M':float,
		'T':float,
		'B':float
		}, ... ]
	"""
	stdev 	= stat.stdev(prices[:SMA_Len])
	SMA 	= float("{0:.{1}f}".format(get_SMA(prices, SMA_Len)[0], 8))
	BTop 	= float("{0:.{1}f}".format(SMA + (stdev * 2), 8))
	BBot 	= float("{0:.{1}f}".format(SMA - (stdev * 2), 8))
	band 	= {"M":SMA, "T":BTop, "B":BBot}

	return(band)



## This function is used to calculate and return the RSI indicator.
def get_RSI(prices, rsiType=14):
	""" 
	This function uses 2 parameters to calculate the RSI-
	
	[PARAMETERS]
		prices	: The prices to be used.
		rsiType : The interval type.
	
	[CALCULATION]
		---
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	prices 	= list(reversed(prices))
	deltas 	= np.diff(prices)
	rsi 	= np.zeros_like(prices)
	seed 	= deltas[:rsiType+1]
	up 		= seed[seed>=0].sum()/rsiType
	down 	= abs(seed[seed<0].sum()/rsiType)
	rs 		= up/down
	rsi[-1] = 100 - 100 /(1+rs)

	for i in range(rsiType, len(prices)):
		cDeltas = deltas[i-1]

		if cDeltas > 0:
			upVal = cDeltas
			downVal = 0
		else:
			upVal = 0
			downVal = abs(cDeltas)

		up = (up*(rsiType-1)+upVal)/rsiType
		down = (down*(rsiType-1)+downVal)/rsiType

		rs = up/down
		rsi[i] = float("{0:.2f}".format(100 - 100 /(1+rs)))

	delIndex = []
	for i in range(len(rsi)):
		if rsi[i] == 0:
			delIndex.append(i)

	fRSI = np.delete(rsi, delIndex)

	return(list(reversed(fRSI)))



## This function is used to calculate and return the stochastics RSI indicator.
def get_stochRSI(prices, rsiType=14, ind_span=2):
	"""
	This function uses 3 parameters to calculate the  Stochastics RSI-
	
	[PARAMETERS]
		prices	: A list of prices.
		rsiType : The interval type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	sto_K, sto_D 	= [], []
	stochRSI 		= []
	av_HL, av_CL 	= [], []
	high_Low, curr_Low = [], []

	stoch = []

	RSI = get_RSI(prices)

	for i in range(ind_span+3):
		high_Low.append(max(RSI[i:rsiType+i])-min(RSI[i:rsiType+i]))
		curr_Low.append(RSI[i]-min(RSI[i:rsiType+i]))

	for i in range(ind_span):
		av_HL.append(get_SMA(high_Low[i:i+3], 3)[0])
		av_CL.append(get_SMA(curr_Low[i:i+3], 3)[0])

	for i in range(ind_span):
		sto_K.append(float("{0:.2f}".format((av_CL[i]/av_HL[i])*100)))

	return(sto_K)


## This function is used to calculate and return SMA.
def get_SMA(prices, ma_type, ind_span=2):
	"""
	This function uses 3 parameters to calculate the Simple Moving Average-
	
	[PARAMETERS]
		prices 	: A list of prices.
		ma_type : The interval type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	ma_list  = []

	for i in range(ind_span):
		ma_list.append(float("{0:.10f}".format(np.mean(prices[i:i+ma_type]))))

	return ma_list


## This function is used to calculate and return EMA.
def get_EMA(prices, ma_type, ind_span=2):
	"""
	This function uses 3 parameters to calculate the Exponential Moving Average-
	
	[PARAMETERS]
		prices 	: A list of prices.
		ma_type : The interval type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	weight 	= float("{0:.3f}".format(2/(ma_type+1)))
	SMA 	= get_SMA(prices[ind_span+2:], ma_type-1, 1)[0]
	seed 	= float("{0:.8f}".format(SMA + weight * (prices[ind_span] - SMA)))
	EMA 	= [seed]

	try:
		for i in range(ind_span+1):
			EMA.append(float("{0:.8f}".format((EMA[i] + weight * (prices[ind_span-i] - EMA[i])))))
	except Exception as e:
		print(prices)
		sys.exit(e)

	del EMA [:2]
	return(list(reversed(EMA)))



## This function is used to calculate and return Simple Smoothing.
def get_SS(prices, SS_type, ind_span=2):
	"""
	This function uses 3 parameters to calculate the Simple Smoothing-
	
	[PARAMETERS]
		prices 	: A list of prices.
		SS_type : The interval type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	SMA = get_SMA(prices[ind_span+2:], SS_type, 1)[0]
	seed = float("{0:.8f}".format((SMA-(SMA/SS_type))+prices[ind_span+1]))
	SS = [seed]

	for i in range(ind_span+1):
		SS.append(float("{0:.8f}".format((SS[i]-(SS[i]/SS_type))+prices[ind_span-i])))

	del SS [:2]
	return(list(reversed(SS)))



## This function is used to calculate and return the the MACD indicator.
def get_MACD(prices, Efast=12, Eslow=26, signal=9, ind_span=2):
	"""
	This function uses 5 parameters to calculate the Moving Average Convergence/Divergence-
	
	[PARAMETERS]
		prices 	: A list of prices.
		Efast	: Fast line type.
		Eslow	: Slow line type.
		signal 	: Signal line type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[{
		'fast':float,
		'slow':float,
		'his':float
		}, ... ]
	"""
	fast_EMA 	= get_EMA(prices, Efast, (60))
	slow_EMA 	= get_EMA(prices, Eslow, (60))
	MACD_line 	= []
	MACD 		= []

	for i in range(60):
		MACD_line.append(float("{0:.8f}".format(fast_EMA[i] - slow_EMA[i])))

	signal_line = get_SMA(MACD_line, signal, ind_span+30)[0:ind_span]

	for i in range(ind_span):
		histogram = MACD_line[i] - signal_line[i]
		MACD.append({"fast":MACD_line[i], "slow":signal_line[i], "his":histogram})

	return(MACD)



## This function is used to calculate and return the True Range.
def get_trueRange(candles, ind_span=2):
	"""
	This function uses 2 parameters to calculate the True Range-

	[PARAMETERS]
		candles	: Dict of candles.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	trueRange = []

	for i in range(ind_span):
		## Get the true range CURRENT HIGH minus CURRENT LOW, CURRENT HIGH mins LAST CLOSE, CURRENT LOW minus LAST CLOSE.
		HL = candles["high"][i] - candles["low"][i]
		H_PC = abs(candles["high"][i] - candles["close"][i+1])
		L_PC = abs(candles["low"][i] - candles["close"][i+1])

		## True range is the max of all 3
		trueRange.append(max(HL, max(H_PC, L_PC)))

	return(trueRange)



## This function is used to calculate and return the Average True Range.
def get_ATR(candles, atr_type=14, ind_span=2):
	"""
	This function uses 3 parameters to calculate the Average True Range-
	
	[PARAMETERS]
		candles	: Dict of candles.
		atr_type: The ATR type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	ATR = []
	trueRange = []

	trueRange = get_trueRange(candles, (atr_type+ind_span))
	ATR = get_EMA(trueRange, atr_type, (ind_span))

	return(ATR)


## This is used to calculate the Direcional Movement.
def get_DM(candles, ind_span=2):
	"""
	This function uses 2 parameters to calculate the positive and negative Directional Movement-
	
	[PARAMETERS]
		candles	: Dict of candles.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[[
		float,
		float
		], ... ]
	"""
	PDM = []
	NDM = []

	for i in range(ind_span):
		## UP MOVE: current high minus last high, DOWN MOVE: last low minus current low.
		upMove = float("{0:.8f}".format(candles["high"][i] - candles["high"][i+1]))
		downMove = float("{0:.8f}".format(candles["low"][i+1] - candles["low"][i]))

		## If MOVE is greater than other MOVE and greater than 0.
		PDM.append(upMove if 0 < upMove > downMove else 0)
		NDM.append(downMove if 0 < downMove > upMove else 0)

	return([PDM, NDM])



## This function is used to calculate and return the ADX indicator.
def get_ADX_DI(candles, adx_type=14, adx_smooth=14, ind_span=2):
	"""
	This function uses 4 parameters to calculate the ADX-

	[PARAMETERS]
		candles	: Dict of candles.
		adx_type: The ADX type.
		adx_smooth: THe smooting interval or the adx.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[{
		'ADX':float,
		'+DI':float,
		'-DI':float
		}, ... ]
	"""
	ADX_DI 	= []
	ADX 	= []
	PDI 	= []
	NDI 	= []
	DI 		= []

	trueRange = get_trueRange(candles, ((adx_type*2)+ind_span+adx_smooth)+28)
	DM 	= get_DM(candles, ((adx_type*2)+ind_span+adx_smooth)+25)
	ATR = get_SS(trueRange, adx_type, (adx_type+ind_span+adx_smooth)+26)
	PDM = get_SS(DM[0], adx_type, (adx_type+ind_span+adx_smooth)+26)
	NDM = get_SS(DM[1], adx_type, (adx_type+ind_span+adx_smooth)+26)

	for i in range(ind_span+adx_type+adx_smooth+24):
		PDI.append((PDM[i]/ATR[i]) * 100)
		NDI.append((NDM[i]/ATR[i]) * 100)

	for i in range(ind_span+adx_type+adx_smooth+22):
		DI.append(abs(PDI[i]-NDI[i])/(PDI[i]+NDI[i]) * 100)

	ADX = get_SMA(DI, adx_type, ind_span+adx_smooth+20)

	for i in range(adx_smooth):
		ADX_2dp = float("{0:.2f}".format(ADX[i]))
		PDI_2dp = float("{0:.2f}".format(PDI[i]))
		NDI_2dp = float("{0:.2f}".format(NDI[i]))

		ADX_DI.append({"ADX":ADX_2dp, "+DI":PDI_2dp, "-DI":NDI_2dp})

	return(ADX_DI[0:ind_span])



## This function is used to calculate and return the ichimoku indicator.
def get_Ichimoku(candles, tS_type=9, kS_type=26, sSB_type=52, ind_span=2):
	"""
	This function uses 5 parameters to calculate the Ichimoku Cloud-

	[PARAMETERS]
		candles	: Dict of candles.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		Tenkan-sen 		= (9-day high + 9-day low) / 2
		Kijun-sen 		= (26-day high + 26-day low) / 2
		Senkou Span A 	= (Tenkan-sen + Kijun-sen) / 2 (This is usually plotted 26 intervals ahead)
		Senkou Span B 	= (52-day high + 52-day low) / 2 (This is usually plotted 26 intervals ahead)
		Chikou Span 	= current close (This is usually plotted 26 intervals behind)
	
	[RETURN]
		[{
		'Temka':float,
		'Kijun':float,
		'Senkou A':float,
		'Senkou B':float,
		'Chikou':float
		}, ... ]
	"""
	ichimoku = []
	tS = 0
	kS = 0
	sSA = 0
	sSB = 0
	cS = 0
	ichimoku = []

	for i in range(ind_span):

		tS = (max(candles["high"][i:tS_type+i])+min(candles["low"][i:tS_type+i]))/2
		kS = (max(candles["high"][i:kS_type+i])+min(candles["low"][i:kS_type+i]))/2
		sSA = (kS+tS)/2
		sSB = (max(candles["high"][i:sSB_type+i])+min(candles["low"][i:sSB_type+i]))/2
		cS = candles["close"][i]

		fTS = float("{0:.8f}".format(tS))
		fKS = float("{0:.8f}".format(kS))
		fSSA = float("{0:.8f}".format(sSA))
		fSSB = float("{0:.8f}".format(sSB))
		fCS = float("{0:.8f}".format(cS))

		ichimoku.append({'Tenkan':fTS, 'Kijun':fKS, 'Senkou A':fSSA, 'Senkou B':fSSB, 'Chikou':fCS})

	return(ichimoku)



def get_stage_segments(trade, startPrice, inc=False, minInc=7):
	segments 	= []
	startPrec 	= 0.0007 if trade is 'Buy' else 0.001
	incPrec		= 0

	for i in range(100):
		precPrice = startPrice*(startPrec*i)

		if inc and i >= minInc:
			incPrec += 0.00025
			extraPrice = startPrice*incPrec

		if trade == 'Buy':
			if inc and i >= minInc: segments.append(float("{0:.8f}".format((startPrice-precPrice)-extraPrice)))
			else: segments.append(float("{0:.8f}".format(startPrice-precPrice)))

		elif trade == 'Sell':
			if inc and i >= minInc: segments.append(float("{0:.8f}".format((startPrice+precPrice)+extraPrice)))
			else: segments.append(float("{0:.8f}".format(startPrice+precPrice)))

	return(segments)


"""
[################################################################################################################################]
[#####################################################] FORMATTING SECTION [#####################################################]
[#####################################################]v^v^v^v^v^^v^v^v^v^v[#####################################################]
"""

def sort_candle(candles, exchange):
	"""
	Sorts the candles into nice columns. (This is to set candles up in a format that can be used by the above functions)
	"""
	candleInfo = {"open":[],"high":[],"low":[],"close":[],"volume":[]}

	if exchange.lower() == "binance":
		## This orders candles recived in the raw binance exchange format.
		for i in range(len(candles)):
			candleInfo["open"].insert(i, candles[i]["Open"])
			candleInfo["high"].insert(i, candles[i]["High"])
			candleInfo["low"].insert(i, candles[i]["Low"])
			candleInfo["close"].insert(i, candles[i]["Close"])
			candleInfo["volume"].insert(i, candles[i]["Volume"])

	elif exchange.lower() == "bittrex":
		## This orders candles recived in the raw bittrex exchange format.
		for i in range(len(candles)):
			candlesInfo["open"].insert(i, candles[i]["O"])
			candlesInfo["high"].insert(i, candles[i]["H"])
			candlesInfo["low"].insert(i, candles[i]["L"])
			candlesInfo["close"].insert(i, candles[i]["C"])
			candlesInfo["volume"].insert(i, candles[i]["V"])

	elif exchange.lower() == "bitmex":
		## This orders candles recived in the raw bitmex exchange format.
		for i in range(len(candles)):
			candleInfo["open"].insert(i, candles[i]["open"])
			candleInfo["high"].insert(i, candles[i]["high"])
			candleInfo["low"].insert(i, candles[i]["low"])
			candleInfo["close"].insert(i, candles[i]["close"])
			candleInfo["volume"].insert(i, candles[i]["volume"])

	return(candleInfo)
	
