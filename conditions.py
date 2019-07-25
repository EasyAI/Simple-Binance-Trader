#! /usr/bin/env python3

import time


def sell_conditions(nInd, currMarket, candles):
    '''
    Set sell conditions here.

    Make sure what you return a signal you return it as shown below:
    return({"place":True, "oType":orderType, "tType":"signal"}),
    Orer type can be left blank or you can specify the type of order.
    '''
    ma9 = nInd['MA9']
    ma21 = nInd['MA21']
    bb = nInd['BB']
    rsi = nInd['RSI']
    macd = nInd['MACD']
    ichi = nInd['Ichimoku']

    lastPrice = currMarket['lastPrice']
    askPrice = currMarket['askPrice']
    bidPrice = currMarket['bidPrice']

    if macd[0]['macd'] < macd[0]['signal']:
        orderType = "Normal signal sell."
        return({"place":True, "oType":orderType, "tType":"signal"})

    return({"place":False})


def buy_conditions(nInd, currMarket, candles):
    '''
    Set buy conditions here.

    Make sure what you return a signal you return it as shown below:
    return({"place":True, "oType":orderType, "tType":"signal"}),
    Orer type can be left blank or you can specify the type of order.
    '''
    ma9 = nInd['MA9']
    ma21 = nInd['MA21']
    bb = nInd['BB']
    rsi = nInd['RSI']
    macd = nInd['MACD']
    ichi = nInd['Ichimoku']

    lastPrice = currMarket['lastPrice']
    askPrice = currMarket['askPrice']
    bidPrice = currMarket['bidPrice']
    
    if macd[0]['hist'] > 0 and macd[0]['macd'] > macd[1]['macd']:
        orderType = "Normal signal buy."
        return({"place":True, "oType":orderType, "tType":"signal"})

    return({"place":False})
