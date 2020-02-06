#! /usr/bin/env python3

import time
import numpy as np

""" Base file used for my crypto  trading Algorithms, Indicators and formatting. """

"""
[######################################################################################################################]
[#############################################] TAS & INCICATORS SECTION [##############################################]
[#############################################]v^v^v^v^v^v^vv^v^v^v^v^v^v[##############################################]

### Indicators List ###
- BB
- RSI
- StochRSI
- Stochastic Oscillator
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
def get_BOLL(prices, ma_type=21, stDev=2):
	"""
	This function uses 2 parameters to calculate the BB-
	
	[PARAMETERS]
		prices	: A list of prices.
		ma_type	: BB ma type.
	
	[CALCULATION]
		---
	
	[RETURN]
		[{
		'M':float,
		'T':float,
		'B':float
		}, ... ]
	"""
	span = len(prices)-ma_type
	stdev = np.array([np.std(prices[i:(ma_type+i)+1]) for i in range(span)])
	sma = get_SMA(prices, ma_type)

	BTop = np.array([sma[i] + (stdev[i] * stDev) for i in range(span)])
	BBot = np.array([sma[i] - (stdev[i] * stDev) for i in range(span)])


	return [{
		"T":BTop[i], 
		"M":sma[i], 
		"B":BBot[i]} for i in range(span)]


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
	prices 	= np.flipud(np.array(prices))
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
		rsi[i] = 100 - 100 /(1+rs)

	fRSI = np.flipud(np.array(rsi[rsiType:]))

	return fRSI.round(2)


def get_stochastics(priceClose, priceHigh, priceLow, period=14):

	span = len(priceClose)-period
	stochastic = np.array([[priceHigh[i:period+i].max()-priceLow[i:period+i].min(), priceClose[i]-priceLow[i:period+i].min()] for i in range(span)])

	return stochastic


## This function is used to calculate and return the stochastics RSI indicator.
def get_stochRSI(prices, rsiPrim=14, rsiSecon=14, K=3, D=3):
	"""
	This function uses 3 parameters to calculate the  Stochastics RSI-
	
	[PARAMETERS]
		prices	: A list of prices.
		rsiType : The interval type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[{
		"%K":float,
		"%D":float
		}, ... ]
	"""
	span = len(prices)-rsiPrim-rsiSecon-K
	RSI = get_RSI(prices, rsiType=rsiPrim)
	
	return get_S_O(RSI, RSI, RSI, period=rsiSecon, K=K, D=D)


## This function is used to calculate and return the Stochastic Oscillator indicator.
def get_S_O(priceClose, priceHigh, priceLow, period=14, K=3, D=3):
	"""
	This function uses 5 parameters to calculate the  Stochastic Oscillator-
	
	[PARAMETERS]
		candles	: A list of prices.
		K_period : The interval for the inital K calculation.
		K_smooth: The smooting interval or the K period.
		D_smooth: The smooting interval or the K period.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		---
	
	[RETURN]
		[{
		"%K":float,
		"%D":float
		}, ... ]
	"""
	priceClose = np.array(priceClose)
	priceHigh = np.array(priceHigh)
	priceLow = np.array(priceLow)

	span = len(priceClose)-period
	stochastic = get_stochastics(priceClose, priceHigh, priceLow, period)

	HL_CL = np.array([((stochastic[:, 1][i] / stochastic[:, 0][i]) * 100) for i in range(span)])

	sto_K = get_SMA(HL_CL, K)
	sto_D = get_SMA(sto_K, D)

	return [{
		"%K":sto_K[i], 
		"%D":sto_D[i]} for i in range(len(sto_D))]


## This function is used to calculate and return SMA.
def get_SMA(prices, maPeriod, prec=8):
	"""
	This function uses 3 parameters to calculate the Simple Moving Average-
	
	[PARAMETERS]
		prices 	: A list of prices.
		ma_type : The interval type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		SMA = average of prices within a given period
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	span = len(prices) - maPeriod + 1
	ma_list = np.array([np.mean(prices[i:(maPeriod+i)]) for i in range(span)])

	return ma_list.round(prec)


## This function is used to calculate and return EMA.
def get_EMA(prices, maPeriod, prec=8):
	"""
	This function uses 3 parameters to calculate the Exponential Moving Average-
	
	[PARAMETERS]
		prices 	: A list of prices.
		ma_type : The interval type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		weight = 2 / (maPerido + 1)
		EMA = ((close - prevEMA) * weight + prevEMA)
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	span = len(prices) - maPeriod
	EMA = np.zeros_like(prices[:span])
	weight = (2 / (maPeriod +1))
	SMA = get_SMA(prices[span:], maPeriod)
	seed = SMA + weight * (prices[span-1] - SMA)
	EMA[0] = seed

	for i in range(1, span):
		EMA[i] = (EMA[i-1] + weight * (prices[span-i-1] - EMA[i-1]))

	return np.flipud(EMA.round(prec))


## This function is used to calculate and return Rolling Moving Average.
def get_RMA(prices, maPeriod, prec=8):
	"""
	This function uses 3 parameters to calculate the Rolling Moving Average-
	
	[PARAMETERS]
		prices 	: A list of prices.
		SS_type : The interval type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		RMA = ((prevRMA * (period - 1)) + currPrice) / period
	
	[RETURN]
		[
		float,
		float,
		... ]
	"""
	span = len(prices) - maPeriod
	SS = np.zeros_like(prices[:span])
	SMA = get_SMA(prices[span:], maPeriod)
	seed = ((SMA * (maPeriod-1)) + prices[span-1]) / maPeriod
	SS[0] = seed

	for i in range(1, span):
		SS[i] = ((SS[i-1] * (maPeriod-1)) + prices[span-i-1]) / maPeriod

	return np.flipud(SS.round(prec))


## This function is used to calculate and return the the MACD indicator.
def get_MACD(prices, Efast=12, Eslow=26, signal=9):
	"""
	This function uses 5 parameters to calculate the Moving Average Convergence/Divergence-
	
	[PARAMETERS]
		prices 	: A list of prices.
		Efast	: Fast line type.
		Eslow	: Slow line type.
		signal 	: Signal line type.
		ind_span: The span of the indicator.
	
	[CALCULATION]
		MACDLine = fastEMA - slowEMA
		SignalLine = EMA of MACDLine
		Histogram = MACDLine - SignalLine
	
	[RETURN]
		[{
		'fast':float,
		'slow':float,
		'his':float
		}, ... ]
	"""
	fastEMA = get_EMA(prices, Efast)
	slowEMA = get_EMA(prices, Eslow)

	macdLine = np.subtract(fastEMA[:len(slowEMA)], slowEMA)
	signalLine = get_EMA(macdLine, signal)
	histogram = np.subtract(macdLine[:len(signalLine)], signalLine)

	return [({
		"macd":float("{0:.8f}".format(macdLine[i])), 
		"signal":float("{0:.8f}".format(signalLine[i])), 
		"hist":float("{0:.8f}".format(histogram[i]))}) for i in range(len(signalLine))]


## This function is used to calculate and return the True Range.
def get_trueRange(candles):
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
	highPrices = [candle[2] for candle in candles]
	lowPrices = [candle[3] for candle in candles]
	closePrices = [candle[4] for candle in candles]
	span = len(closePrices) - 1
	trueRange = []

	for i in range(span):
		## Get the true range CURRENT HIGH minus CURRENT LOW, CURRENT HIGH mins LAST CLOSE, CURRENT LOW minus LAST CLOSE.
		HL = highPrices[i] - lowPrices[i]
		H_PC = abs(highPrices[i] - closePrices[i+1])
		L_PC = abs(lowPrices[i] - closePrices[i+1])

		## True range is the max of all 3
		trueRange.append(max([HL, H_PC, L_PC]))

	return trueRange


## This function is used to calculate and return the Average True Range.
def get_ATR(candles, atrPeriod=14):
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
	trueRange = get_trueRange(candles)
	ATR = get_RMA(trueRange, atrPeriod)

	return ATR


## This is used to calculate the Direcional Movement.
def get_DM(candles):
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
	highPrices = [candle[2] for candle in candles]
	lowPrices = [candle[3] for candle in candles]
	span = len(highPrices) - 1
	PDM = np.zeros_like(highPrices[:span])
	NDM = np.zeros_like(highPrices[:span])

	for i in range(span):
		## UP MOVE: current high minus last high, DOWN MOVE: last low minus current low.
		upMove = highPrices[i] - highPrices[i+1]
		downMove = lowPrices[i+1] - lowPrices[i]

		## If MOVE is greater than other MOVE and greater than 0.
		PDM[i] = upMove if 0 < upMove > downMove else 0
		NDM[i] = downMove if 0 < downMove > upMove else 0

	return [PDM, NDM]


## This function is used to calculate and return the ADX indicator.
def get_ADX_DI(rCandles, adxLen=14, dataType="numpy"):
	"""
	This function uses 3 parameters to calculate the ADX-

	[PARAMETERS]
		candles	: Dict of candles.
		adx_type: The ADX type.
		adx_smooth: The smooting interval or the adx.
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

	if dataType == "normal":
		candles = np.array([[0, 
			rCandles["open"][i],
			rCandles["high"][i],
			rCandles["low"][i],
			rCandles["close"][i]]for i in range(len(rCandles["open"]))]).astype(np.float)

	elif dataType == "numpy":
		candles = rCandles

	baseIndLen = adxLen
	ADX_DI = []

	DM = get_DM(candles)
	ATR = get_ATR(candles, baseIndLen)
	PDM = get_RMA(DM[0], baseIndLen)
	NDM = get_RMA(DM[1], baseIndLen)

	newRange = len(ATR) if len(ATR) < len(PDM) else len(PDM)
	PDI = np.array([((PDM[i] / ATR[i]) * 100) for i in range(newRange)])
	NDI = np.array([((NDM[i] / ATR[i]) * 100) for i in range(newRange)])

	DI = np.array([(abs(PDI[i] - NDI[i]) / (PDI[i] + NDI[i]) * 100) for i in range(len(NDI))])

	ADX = get_SMA(DI, adxLen)

	return [({
		"ADX":float("{0:.2f}".format(ADX[i])), 
		"+DI":float("{0:.2f}".format(PDI[i])), 
		"-DI":float("{0:.2f}".format(NDI[i]))}) for i in range(len(ADX))]


## This function is used to calculate and return the ichimoku indicator.
def get_Ichimoku(candles, tS_type=9, kS_type=26, sSB_type=52, dataType="numpy"):
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
	if dataType == "normal":
		highPrices = np.array(candles["high"]).astype(np.float)
		lowPrices = np.array(candles["low"]).astype(np.float)
		closePrices = np.array(candles["close"]).astype(np.float)

	elif dataType == "numpy":
		highPrices = [candle[2].astype(np.float) for candle in candles]
		lowPrices = [candle[3].astype(np.float) for candle in candles]
		closePrices = [candle[4].astype(np.float) for candle in candles]

	ichimoku = []
	span = len(lowPrices)

	tS = [((max(highPrices[i:tS_type+i]) + min(lowPrices[i:tS_type+i])) / 2) for i in range(span)]
	kS = [((max(highPrices[i:kS_type+i]) + min(lowPrices[i:kS_type+i])) / 2) for i in range(span)]

	sSA = [((kS[i] + tS[i]) / 2) for i in range(span)]

	sSB = [((max(highPrices[i:sSB_type+i]) + min(lowPrices[i:sSB_type+i])) / 2) for i in range(span)]

	return [({
		"Tenkan":float("{0:.8f}".format(tS[i])),
		"Kijun":float("{0:.8f}".format(kS[i])),
		"Senkou A":float("{0:.8f}".format(sSA[i])),
		"Senkou B":float("{0:.8f}".format(sSB[i])),
		"Chikou":float("{0:.8f}".format(closePrices[i]))}) for i in range(span)]


def get_CCI(rCandles, source, period=14, constant=0.015, dataType="numpy"):
	"""
	source is refering too where the typical price will come from. (high, low, close, all)

	CCI = (Typical Price  -  20-period SMA of TP) / (.015 x Mean Deviation)

	Typical Price (TP) = Close

	Constant = .015

	"""
	if dataType == "normal":
		candles = np.array([[0, 
				rCandles["open"][i],
				rCandles["high"][i],
				rCandles["low"][i],
				rCandles["close"][i]] for i in range(len(rCandles["open"]))]).astype(np.float)

	elif dataType == "numpy":
		candles = rCandles

	CCI = []

	if source == 'high':
		typicalPrice = np.array([candle[2] for candle in candles])
	elif source == 'low':
		typicalPrice = np.array([candle[3] for candle in candles])
	elif source == 'close':
		typicalPrice = np.array([candle[4] for candle in candles])
	elif source == 'all':
		typicalPrice = np.array([((candle[4]) / 1) for candle in candles])
	else:
		raise ValueError('Invalid CCI source. Make sure the CCI source is either; high, low, close, all')

	MAD = get_Mean_ABS_Deviation(typicalPrice, period)
	smTP = get_SMA(typicalPrice, period)

	for i in range(len(MAD)):
		CCI.append(((typicalPrice[i] - smTP[i]) / (constant * MAD[i])).round(2))

	return(CCI)


def get_Mean_ABS_Deviation(prices, period):
	"""
	There are four steps to calculating the Mean Deviation: 
	First, subtract the most recent 20-period average of the typical price from each period's typical price. 
	Second, take the absolute values of these numbers. 
	Third, sum the absolute values. 
	Fourth, divide by the total number of periods (20).
	"""
	partOneTwo = []
	partThreeFour = []

	sma = get_SMA(prices, period)

	for i,ma in enumerate(sma):
		partTwo = [abs(price - ma) for price in prices[i:i+period]]

		partThreeFour.append(np.mean(partTwo))

	return(partThreeFour)



def get_Force_Index(cPrices, volume, maPeriod=9):
	"""
	Force Index(1) = {Close (current period)  -  Close (prior period)} x Volume
	Force Index(13) = 13-period EMA of Force Index(1)
	"""
	span = len(cPrices) - 1

	baseValues = [(cPrices[i] - cPrices[i+1])*volume[i] for i in range(span)]

	forceIndex = get_EMA(baseValues, maPeriod)

	return(forceIndex)