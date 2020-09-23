#! /usr/bin/env python3

import logging
import numpy as np
import technical_indicators as TI

## Minimum price rounding.
pRounding = 8

#time, open, high, low, close, volume

def technical_indicators(candles):
    indicators = {}

    open_prices     = [candle[1] for candle in candles]
    high_prices     = [candle[2] for candle in candles]
    low_prices      = [candle[3] for candle in candles]
    close_prices    = [candle[4] for candle in candles]
    
    indicators.update({'MACD':TI.get_MACD(close_prices)})
    indicators.update({'MFI':TI.get_MFI(candles)})
    indicators.update({'ADX':TI.get_ADX_DI(candles)})
    indicators.update({'MA_50':TI.get_SMA(close_prices, 50)})

    return(indicators)


def other_conditions(custom_conditional_data, trade_information, candles, indicators, symbol, btc_base):
    custom_conditional_data = custom_conditional_data
    can_trade_long = True
    can_trade_short = True

    trade_information.update({'can_order':{'short':can_trade_short,'long':can_trade_long}})
    return(custom_conditional_data, trade_information)


def long_exit_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol, btc_base):
    '''
    The current order types that are supported are
    limit orders = LIMIT
    stop loss orders = STOP_LOSS_LIMIT
    market orders = MARKET
    '''
    price = side = description = ptype = None
    orderType = 'WAIT'

    ## Set the indicators used to test the conditions:
    macd = indicators['MACD']

    ## Logic for SELL conditions.
    if  macd[0]['macd'] < macd[0]['signal']:
        return({'order_type':'SIGNAL', 
            'side':'SELL', 
            'description':'Long exit signal', 
            'ptype':'MARKET'})

    return({'order_type':'WAIT'})


def long_entry_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol, btc_base):
    '''
    The current order types that are supported are
    limit orders = LIMIT
    market orders = MARKET
    '''
    price = side = description = ptype = None
    orderType = 'WAIT'

    ## Set the indicators used to test the conditions:
    macd = indicators['MACD']

    ## Logic for BUY conditions.
    if macd[0]['hist'] > 0 and macd[0]['macd'] > macd[1]['macd'] and macd[0]['macd'] > macd[0]['signal']:
        return({'order_type':'SIGNAL', 
            'side':'BUY', 
            'description':'long entry signal', 
            'ptype':'MARKET'})

    return({'order_type':'WAIT'})


def short_exit_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol, btc_base):
    pass


def short_entry_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol, btc_base):
    pass