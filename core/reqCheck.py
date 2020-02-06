#! /usr/bin/env python3

'''
reqCheck

'''
import os
import time
import logging
import requests


def data_check(data, urlQuery):
    ''' This will check the data recived from the exchange to see if there are any errors and handles them. '''

    logMessage = 'data: {0}, query: {1}'.format(data, urlQuery)

    if 'fatal' in data:
        error = data['fatal']['message']
        errorMsg = 'error: {0}, query: {1}'.format(error, urlQuery)
        logging.warning(errorMsg)
        return(0, '')

    elif data == None:
        logging.warning('Data was empty.')
        return(0, '')

    elif 'code' in data:
        if str(data['code']) == '-1003':
            ## code -1003 : Too many requests (>1200 per min).
            logging.warning(logMessage)
            time.sleep(30)
            return(0, '')
        elif str(data['code']) == '-1013':
            ## code -1013 : Invalid quantity for placing order.
            logging.warning(logMessage)
            return(-1, str(data['code']))
        elif str(data['code']) == '-1021':
            ## code -1021 : Request outside of the recive window.
            logging.warning(logMessage)
            time.sleep(4)
            return(0, '')
        elif str(data['code']) == '-2010':
            ## code -2010 : Account has insufficient balance for request.
            logging.warning('[{0}] msg: {2}'.format(logMessage, data['code'], data['msg']))
            return(-1, str(data['code']))
        else:
            logging.warning('NEW ERROR: [{0}] code: {1}, msg: {2}'.format(logMessage, data['code'], data['msg']))
            return(-1, str(data['code']))

    return(1, '')


def test_ping():
    ''' This is used to send a basic ping request out to test connectivity, if successfull then testing connectivity to the exchange. '''
    retries = 5
    fullPath = 'https://www.binance.com/api/v1/ping'

    while retries > 0:
        binanceResponse = requests.request('GET', fullPath)
        if 'Response' in str(binanceResponse):
            return(True)
        time.sleep(2)
        retries -= 1

    logging.warning('connection issue: can\'t ping exchange.')
    return(False)