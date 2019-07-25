#! /usr/bin/env python3

import os
import logging
import requests


def data_check(data, urlQuery):
    ''' This will check the data recived from the exchange to see if there are any errors and handles them. '''

    logMessage = 'data: {0}, query: {1}'.format(data, urlQuery)

    if 'error' in data:
        error = data['error']['message']
        errorMsg = 'error: {0}, query: {1}'.format(error, urlQuery)
        logging.warning(errorMsg)
        return(False)

    elif data == None:
        logging.warning('Data was empty.')
        return(False)

    elif 'code' in data:
        if str(data['code']) in ['-1013', '-1021']:
            '''
            code -1013 : Invalid quantity for placing order.
            code -1021 : Request outside of the recive window.
            '''
            logging.warning(logMessage)
            pass

        elif str(data['code']) in ['-1003']:
            '''
            code -1003 : Too many requests (>1200 per min).
            '''
            logging.warning(logMessage)
            time.sleep(30)

        else:
            logging.warning('NEW ERROR: [{0}]'.format(logMessage))

        return(False)
    return(True)


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