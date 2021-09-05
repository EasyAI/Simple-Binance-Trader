import logging
import numpy as np
import technical_indicators as TI

## Minimum price rounding.
pRounding = 8

def technical_indicators(candles):
    indicators = {}

    time_values     = [candle[0] for candle in candles]
    open_prices     = [candle[1] for candle in candles]
    high_prices     = [candle[2] for candle in candles]
    low_prices      = [candle[3] for candle in candles]
    close_prices    = [candle[4] for candle in candles]

    indicators.update({'macd':TI.get_MACD(close_prices, time_values=time_values, map_time=True)})

    indicators.update({'ema':{}})
    indicators['ema'].update({'ema200':TI.get_EMA(close_prices, 200, time_values=time_values, map_time=True)})

    return(indicators)

'''
--- Current Supported Order ---
    Below are the currently supported order types that can be placed which the trader
-- MARKET --
    To place a MARKET order you must pass:
        'side'              : 'SELL', 
        'description'       : 'Long exit signal', 
        'order_type'        : 'MARKET'
    
-- LIMIT STOP LOSS --
    To place a LIMIT STOP LOSS order you must pass:
        'side'              : 'SELL', 
        'price'             : price,
        'stopPrice'         : stopPrice,
        'description'       : 'Long exit stop-loss', 
        'order_type'        : 'STOP_LOSS_LIMIT'
-- LIMIT --
    To place a LIMIT order you must pass:
        'side'              : 'SELL', 
        'price'             : price,
        'description'       : 'Long exit stop-loss', 
        'order_type'        : 'LIMIT'
-- OCO LIMIT --
    To place a OCO LIMIT order you must pass:
        'side'              : 'SELL', 
        'price'             : price,
        'stopPrice'         : stopPrice,
        'stopLimitPrice'    : stopLimitPrice,
        'description'       : 'Long exit stop-loss', 
        'order_type'        : 'OCO_LIMIT'
--- Key Descriptions--- 
    Section will give brief descript of what each order placement key is and how its used.
        side            = The side the order is to be placed either buy or sell.
        price           = Price for the order to be placed.
        stopPrice       = Stop price to trigger limits.
        stopLimitPrice  = Used for OCO to to determine price placement for part 2 of the order.
        description     = A description for the order that can be used to identify multiple conditions.
        order_type      = The type of the order that is to be placed.
--- Candle Structure ---
    Candles are structured in a multidimensional list as follows:
        [[time, open, high, low, close, volume], ...]
'''


def other_conditions(custom_conditional_data, trade_information, previous_trades, position_type, candles, indicators, symbol):
    # Define defaults.
    can_order = True

    # Setup additional extra conditions for trading.
    if trade_information['market_status'] == 'COMPLETE_TRADE':
        trade_information['market_status'] = 'TRADING'

    trade_information.update({'can_order':can_order})
    return(custom_conditional_data, trade_information)


def long_exit_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    # Place Long exit (sell) conditions under this section.
    order_point = 0
    signal_id = 0
    macd = indicators['macd']

    if macd[0]['macd'] < macd[1]['macd']:
        order_point += 1
        if macd[1]['hist'] < macd[0]['hist']:
            return({'side':'SELL',
                'description':'LONG exit signal 1', 
                'order_type':'MARKET'})

    stop_loss_price = float('{0:.{1}f}'.format((trade_information['buy_price']-(trade_information['buy_price']*0.004)), pRounding))
    stop_loss_status = basic_stoploss_setup(trade_information, stop_loss_price, stop_loss_price, 'LONG')

    # Base return for waiting and updating order positions.
    if stop_loss_status:
        return(stop_loss_status)
    else:
        return({'order_point':'L_ext_{0}_{1}'.format(signal_id, order_point)})


def long_entry_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    # Place Long entry (buy) conditions under this section.
    order_point = 0
    signal_id = 0
    macd = indicators['macd']
    ema200 = indicators['ema']['ema200']

    if (candles[0][4] > ema200[0]):
        if macd[0]['macd'] > macd[1]['macd']:
            order_point += 1
            if macd[1]['hist'] > macd[0]['hist']:
                return({'side':'BUY',
                    'description':'LONG entry signal 1', 
                    'order_type':'MARKET'})

    # Base return for waiting and updating order positions.
    if order_point == 0:
        return({'order_type':'WAIT'})
    else:
        return({'order_type':'WAIT', 'order_point':'L_ent_{0}_{1}'.format(signal_id, order_point)})


def short_exit_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    ## Place Short exit (sell) conditions under this section.
    order_point = 0
    signal_id = 0
    macd = indicators['macd']

    if macd[0]['macd'] > macd[1]['macd']:
        order_point += 1
        if macd[1]['hist'] > macd[0]['hist']:
            return({'side':'SELL',
                'description':'SHORT exit signal 1', 
                'order_type':'MARKET'})

    stop_loss_price = float('{0:.{1}f}'.format((trade_information['buy_price']+(trade_information['buy_price']*0.004)), pRounding))
    stop_loss_status = basic_stoploss_setup(trade_information, stop_loss_price, stop_loss_price, 'SHORT')

    # Base return for waiting and updating order positions.
    if stop_loss_status:
        return(stop_loss_status)
    else:
        return({'order_point':'S_ext_{0}_{1}'.format(signal_id, order_point)})


def short_entry_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    ## Place Short entry (buy) conditions under this section.
    order_point = 0
    signal_id = 0
    macd = indicators['macd']
    ema200 = indicators['ema']['ema200']

    if (candles[0][4] < ema200[0]):
        if macd[0]['macd'] < macd[1]['macd'] and macd[0]['hist'] > macd[0]['macd']:
            order_point += 1
            if macd[1]['hist'] < macd[0]['hist']:
                return({'side':'BUY',
                    'description':'SHORT entry signal 1', 
                    'order_type':'MARKET'})

    # Base return for waiting and updating order positions.
    if order_point == 0:
        return({'order_type':'WAIT'})
    else:
        return({'order_type':'WAIT', 'order_point':'S_ent_{0}_{1}'.format(signal_id, order_point)})


def basic_stoploss_setup(trade_information, price, stop_price, position_type):
    # Basic stop-loss setup.
    if trade_information['order_type'] == 'STOP_LOSS_LIMIT':
        return

    return({'side':'SELL', 
        'price':price,
        'stopPrice':stop_price,
        'description':'{0} exit stop-loss'.format(position_type), 
        'order_type':'STOP_LOSS_LIMIT'})