#! /usr/bin/env python3

'''
You will need to create your own conditions to allow the trader to place orders.
To allow a successful order to be placed you'll need to return data for the trader.
Below is an example of what one of these return statements will look like.

{'place':True, 'description':description, 'tType':'signal', 'price':price}

As shown in the above example this is a dictionary with 4 different elementsa

place: Let the trader know that a order is to be placed.
description: Small description for the order (help distinguish between many orders).
tType: Type of order being placed (right now only signal works)
price: The price the order should be placed at
'''

def sell_conditions(nInd, currMarket, tInfo, candles):
    ## Setup any sell conditions here. ##

    macd = nInd['MACD']

    lastPrice = currMarket['lastPrice']
    askPrice = currMarket['askPrice']
    bidPrice = currMarket['bidPrice']

    ## Simple MACD sell signal.
    if macd[0]['macd'] < macd[0]['signal']:
        description = 'Normal signal sell.'
        price = currMarket['askPrice']
        return({'place':True, 'description':description, 'tType':'signal', 'price':price})

    return({'place':False})


def buy_conditions(nInd, currMarket, tInfo, candles):
    ## Setup any buy conditions here ##

    macd = nInd['MACD']

    lastPrice = currMarket['lastPrice']
    askPrice = currMarket['askPrice']
    bidPrice = currMarket['bidPrice']
    
    ## Simple MACD buy signal.
    if macd[0]['hist'] > 0 and macd[0]['macd'] > macd[1]['macd']:
        description = 'Normal signal buy.'
        price = currMarket['bidPrice']
        return({'place':True, 'description':description, 'tType':'signal', 'price':price})

    return({'place':False})
