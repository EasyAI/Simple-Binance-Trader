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
    
    indicators.update({'macd':TI.get_MACD(close_prices)})

    return(indicators)


def other_conditions(custom_conditional_data, position_information, previous_trades, position_type, candles, indicators, symbol):
    can_order = True

    ## If trader has finished trade allow it to continue trading straight away.
    if position_information['market_status'] == 'COMPLETE_TRADE':
        position_information['market_status'] = 'TRADING'

    position_information.update({'can_order':can_order})
    return(custom_conditional_data, position_information)


def long_exit_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    macd = indicators['macd']

    if macd[0]['macd'] < macd[1]['macd'] and macd[1]['hist'] < macd[0]['hist']:
        return({'order_type':'SIGNAL', 
            'side':'SELL', 
            'description':'Long exit signal', 
            'order_type':'MARKET'})

    if trade_information['order_type'] == 'STOP_LOSS':
        return

    price = float('{0:.{1}f}'.format((trade_information['buy_price']-(trade_information['buy_price']*0.004)), pRounding))
    return({'order_type':'STOP_LOSS', 
            'side':'SELL', 
            'price':price,
            'stopPrice':price,
            'description':'Long exit stop-loss', 
            'order_type':'STOP_LOSS_LIMIT'})

    return({'order_type':'WAIT'})


def long_entry_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    macd = indicators['macd']

    if macd[0]['macd'] > macd[1]['macd'] and macd[1]['hist'] > macd[0]['hist']:
        return({'order_type':'SIGNAL', 
                'side':'BUY', 
                'description':'Long entry signal', 
                'order_type':'MARKET'})

    return({'order_type':'WAIT'})


def short_exit_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    pass


def short_entry_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    pass
