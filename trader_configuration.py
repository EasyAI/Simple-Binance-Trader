#! /usr/bin/env python3

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

    return(indicators)


def other_conditions(custom_conditional_data, trade_information):
    custom_conditional_data = {}
    can_order = True


    trade_information.update({'canOrder':can_order})
    return(custom_conditional_data, trade_information)


def sell_conditions(custom_conditional_data, trade_information, indicators, prices, candles):
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

    ## Logic for testing conditions.
    if  macd[0]['macd'] < macd[0]['signal']:
        orderType = 'SIGNAL'
        side = 'SELL'
        description = 'Signal buy order'
        ptype = 'MARKET'

    elif False:
        price = ''
        orderType = 'STOP_LOSS'
        side = 'SELL'
        description = 'Signal buy order'
        ptype = 'STOP_LOSS_LIMIT'

    return({'price':price, 'orderType':orderType, 'side':side, 'description':description, 'ptype':ptype})


def buy_conditions(custom_conditional_data, trade_information, indicators, prices, candles):
    macd = indicators['MACD']

    price = ''
    orderType = 'WAIT'
    side = ''
    description = ''
    ptype = ''

    if macd[0]['hist'] > 0 and macd[0]['macd'] > macd[1]['macd'] and macd[0]['macd'] > macd[0]['signal']:
        orderType = 'SIGNAL'
        side = 'BUY'
        description = 'Signal buy order'
        ptype = 'MARKET'

    return({'price':price, 'orderType':orderType, 'side':side, 'description':description, 'ptype':ptype})
