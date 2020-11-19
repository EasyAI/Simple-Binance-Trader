#! /usr/bin/env python3

import time
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


def other_conditions(custom_conditional_data, position_information, position_type, candles, indicators, symbol, btc_base):
    custom_conditional_data = custom_conditional_data
    can_order = True

    if position_information['market_status'] == 'COMPLETE_TRADE':
        if position_information['sell_time'] > 60:
            position_information['market_status'] = 'TRADING'

    position_information.update({'can_order':can_order})
    return(custom_conditional_data, position_information)


def long_exit_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol, btc_base):
    '''
    The current order types that are supported are
    limit orders = LIMIT
    stop loss orders = STOP_LOSS_LIMIT
    market orders = MARKET
    '''
    ## Set the indicators used for sell conditions:
    macd = indicators['MACD']

    ## Logic for SELL conditions.
    if  macd[0]['macd'] < macd[0]['signal']:
        return({'order_type':'SIGNAL', 
            'side':'SELL', 
            'description':'Long exit signal', 
            'ptype':'MARKET'})

    return({'order_type':'WAIT'})


    '''if trade_information['long_order_type']['S'] == 'STOP_LOSS':
        return
    price = float('{0:.{1}f}'.format((trade_information['buy_price']-(trade_information['buy_price']*0.01)), pRounding))
    return({'order_type':'STOP_LOSS', 
            'side':'SELL', 
            'price':price,
            'stopPrice':price,
            'description':'Long exit stop-loss', 
            'ptype':'STOP_LOSS_LIMIT'})'''
    return({'order_type':'WAIT'})


def long_entry_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol, btc_base):
    '''
    The current order types that are supported are
    limit orders = LIMIT
    market orders = MARKET
    '''
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
