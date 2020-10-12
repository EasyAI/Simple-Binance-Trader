#! /usr/bin/env python3

'''
Botcore

'''
import os
import sys
import time
import json
import hashlib
import logging
import threading
from decimal import Decimal
from flask_socketio import SocketIO
from flask import Flask, render_template, url_for, request

## Binance API modules
from binance_api import rest_master
from binance_api import socket_master

from . import trader
from . import handler

APP         = Flask(__name__)
SOCKET_IO   = SocketIO(APP)

##
BOT_CORE    = None

host_ip = ''
host_port = ''

ALL_BTC_PAIRS = ['USDT', 'BKRW' 'TUSD', 'BUSD', 'USDC', 'PAX', 'AUD', 'BIDR', 'DAI', 'EUR', 'GBP', 'IDRT', 'NGN', 'RUB', 'TRY', 'ZAR', 'UAH']
INVERT_FOR_BTC_FIAT = False


@APP.context_processor
def override_url_for():
    return(dict(url_for=dated_url_for))


def dated_url_for(endpoint, **values):
    '''
    This is uses to overide the normal cache for loading static resources.
    '''
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(APP.root_path,
                                    endpoint,
                                    filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)


@APP.route('/', methods=['GET'])
def control_panel():
    web_updater_thread = threading.Thread(target=web_updater)
    web_updater_thread.start()

    start_up_data = {'hostIP':host_ip, 
                    'hostPort':host_port}

    print(start_up_data)

    return(render_template('main_page.html', data=start_up_data))


@APP.route('/rest-api/v1/add_trader', methods=['POST'])
def add_trader():
    print(request.get_json())
    return(json.dumps({'call':True}))


@APP.route('/rest-api/v1/trader_update', methods=['POST'])
def update_trader():
    post_data = request.get_json()
    current_trader = None
    for trader in BOT_CORE.trader_objects:
        if trader.symbol == post_data['market']:
            current_trader = trader
            break

    if current_trader == None:
        return(json.dumps({'call':False}))

    elif post_data['action'] == 'remove':
        trader.stop()
    elif post_data['action'] == 'start':
        if trader.runtime_state == 'FORCE_PAUSE':
            trader.runtime_state = 'RUN'

    elif post_data['action'] == 'pause':
        if trader.runtime_state == 'RUN':
            trader.runtime_state = 'FORCE_PAUSE'

    else:
        return(json.dumps({'call':False}))

    return(json.dumps({'call':True}))


@APP.route('/rest-api/v1/get_trader_data', methods=['GET'])
def get_trader_data():
    print(request.get_json())
    return(json.dumps({'call':True, 'data':BOT_CORE.get_trader_data()}))


@APP.route('/rest-api/v1/get_trader_indicators', methods=['GET'])
def get_trader_indicators():
    print(request.get_json())
    return(json.dumps({'call':True, 'data':BOT_CORE.get_trader_indicators()}))


@APP.route('/rest-api/v1/test', methods=['GET'])
def test_rest_call():
    return(json.dumps({'call':True,'data':'Hello World'}))


def web_updater():
    lastHash = None

    while True:
        if BOT_CORE.coreState == 'RUN':
            traderData = BOT_CORE.get_trader_data()
            currHash = hashlib.md5(str(traderData).encode())

            if lastHash != currHash:
                lastHash = currHash
                SOCKET_IO.emit('current_traders_data', {'data':traderData})

        time.sleep(.25)


class BotCore():

    def __init__(self, runType, marketType, publicKey, privateKey, MAC, trading_markets, candle_Interval, max_candles, max_depth, order_log_path):
        ''' 
        
        '''
        logging.info('[BotCore] Initilizing the BotCore object.')

        self.rest_api = rest_master.Binance_REST(publicKey, privateKey)
        self.order_log_path = order_log_path

        self.run_type       = runType
        self.market_type    = marketType

        self.max_candles = max_candles
        self.max_depth = max_depth

        logging.info('[BotCore] Initilizing BinancesSOCK object.')
        self.socket_api = socket_master.Binance_SOCK()

        ## Trader settings.
        self.MAC = MAC
        self.candle_Interval = candle_Interval

        self.trader_objects = []
        self.trading_markets = trading_markets

        self.coreState = 'READY'


    def start(self):
        '''
        
        '''
        logging.info('[BotCore] Starting the BotCore object.')
        self.coreState = 'SETUP'

        logging.info('[BotCore] Collecting market info.')

        market_rules = handler.read_cache_file(0)

        if not(handler.read_cache_file(0)):
            market_rules = self.rest_api.get_exchange_info()
            handler.save_cache_file(0, market_rules)
            market_rules = market_rules['symbols']
        else:
            market_rules = market_rules['data']['symbols']

        ## check markets
        found_markets = []
        not_supported = []
        for market in market_rules:
            fmtMarket = '{0}-{1}'.format(market['quoteAsset'], market['baseAsset'])

            ## If the current market is not in the trading markets list then skip.
            if not fmtMarket in self.trading_markets:
                continue

            found_markets.append(fmtMarket)

            if self.market_type == 'MARGIN':
                if market['isMarginTradingAllowed'] == False: 
                    not_supported.append(fmtMarket)
                    continue

            elif self.market_type == 'SPOT':
                if market['isSpotTradingAllowed'] == False: 
                    not_supported.append(fmtMarket)
                    continue

            filters = market['filters']

            ## This is used to setup min quantity
            if float(filters[2]['minQty']) < 1.0:
                minQuantBase = (Decimal(filters[2]['minQty'])).as_tuple()
                lS = abs(int(len(minQuantBase.digits)+minQuantBase.exponent))+1
            else: lS = 0

            ## This is used to set up the price precision for the market.
            tickSizeBase = (Decimal(filters[0]['tickSize'])).as_tuple()
            tS = abs(int(len(tickSizeBase.digits)+tickSizeBase.exponent))+1

            ## This is used to get the markets minimal notation.
            mN = float(filters[3]['minNotional'])

            isFiat = True if market['baseAsset'] in ALL_BTC_PAIRS else False

            market_rules = {'LOT_SIZE':lS, 'TICK_SIZE':tS, 'MINIMUM_NOTATION':mN, 'isFiat':isFiat, 'invFiatToBTC':INVERT_FOR_BTC_FIAT}

            self.trader_objects.append(trader.BaseTrader(
                market['baseAsset'], 
                market['quoteAsset'],
                market_rules,
                self.socket_api,
                self.rest_api))

        ## Show markets that dont exist on the binance exchange.
        not_found = ''
        for market in self.trading_markets:
            if market not in found_markets:
                not_found += ' '+str(market)

        if not_found != '':
            print_str = 'Following market pairs do no exist:'+not_found
            print(print_str)

        ## Show markets that dont support the market type
        not_support_text = ''
        for market in not_supported:
            if market not in not_support_text:
                not_support_text += ' '+str(market)

        if not_support_text != '':
            print_str = 'Following market pairs are not supported for {0}:'.format(self.market_type)+not_support_text
            print(print_str)

        valid_tading_markets = [market for market in found_markets if market not in not_supported]

        ## setup the socket
        for market in valid_tading_markets:
            self.socket_api.set_candle_stream(symbol=market, interval=self.candle_Interval)
            self.socket_api.set_manual_depth_stream(symbol=market, update_speed='1000ms')

        self.socket_api.set_userDataStream(self.rest_api, self.market_type)

        self.socket_api.BASE_CANDLE_LIMIT = self.max_candles
        self.socket_api.BASE_DEPTH_LIMIT = self.max_depth

        self.socket_api.build_query()
        self.socket_api.set_live_and_historic_combo(self.rest_api)

        self.socket_api.start()

        ## check for active trades
        if self.run_type == 'REAL':
            user_info = self.rest_api.get_account(self.market_type)
            if self.market_type == 'SPOT':
                wallet_balances = user_info['balances']
            elif self.market_type == 'MARGIN':
                wallet_balances = user_info['userAssets']
            current_tokens = {}
            
            for balance in wallet_balances:
                total_balance = (float(balance['free']) + float(balance['locked']))
                if total_balance > 0:
                    current_tokens.update({balance['asset']:[
                                        float(balance['free']),
                                        float(balance['locked'])]})

            open_orders = self.rest_api.get_open_orders(self.market_type)
        else:
            current_tokens = {'BTC':[float(self.MAC), 0.0]}
            open_orders = None

        cached_traders_data = handler.read_cache_file(1)

        ## start/setup traders
        logging.info('[BotCore] Starting the trader objects.')
        for trader_ in self.trader_objects:
            wallet_pair = {}
            openOrder = None
            trader_.orders_log_path = self.order_log_path
            current_trader_cache = False
            currSymbol = "{0}{1}".format(trader_.base_asset, trader_.quote_asset)

            if cached_traders_data:
                for cached_trader in cached_traders_data['data']:
                    m_split = cached_trader['market'].split('-')
                    if (m_split[1]+m_split[0]) == currSymbol:
                        trader_.custom_conditional_data = cached_trader['customConditional']
                        trader_.trade_information = cached_trader['tradeInfo']
                        trader_.trader_stats = cached_trader['traderStats']
                        current_trader_cache = True

            if open_orders != None:
                for order in open_orders:
                    if order['symbol'] == currSymbol:
                        openOrder = order
                        break

            if trader_.quote_asset in current_tokens:
                wallet_pair.update({trader_.quote_asset:current_tokens[trader_.quote_asset]})

            if trader_.base_asset in current_tokens:
                wallet_pair.update({trader_.base_asset:current_tokens[trader_.base_asset]})

            trader_.start(self.market_type, self.run_type, self.MAC, wallet_pair, current_trader_cache, openOrder)

        logging.debug('[BotCore] Starting connection manager thread.')
        CM_thread = threading.Thread(target=self._connection_manager)
        CM_thread.start()

        logging.debug('[BotCore] Starting file manager thread.')
        FM_thread = threading.Thread(target=self._file_manager)
        FM_thread.start()

        logging.info('[BotCore] BotCore successfully started.')
        self.coreState = 'RUN'


    def stop(self):
        '''  '''
        if self.socket_api.socketRunning:
            self.socket_api.ws.close()

        for trader_ in self.traderObjects:
            trader_.stop()

        self.coreState = 'STOP'


    def _file_manager(self):
        while self.coreState != 'STOP':
            time.sleep(15)

            traders_data = self.get_trader_data()['traders']
            handler.save_cache_file(1, traders_data)


    def _connection_manager(self):
        '''  '''
        update_time = 0
        retryCounter = 1

        time.sleep(20)

        while self.coreState != 'STOP':
            time.sleep(1)

            if self.coreState != 'RUN':
                continue

            if self.socket_api.last_data_recv_time != update_time:
                update_time = self.socket_api.last_data_recv_time
            else:
                if (update_time + (15*retryCounter)) < time.time():
                    retryCounter += 1
                    try:
                        print(self.rest_api.test_ping())
                    except Exception as e:
                        logging.warning('[BotCore] Connection issue: {0}.'.format(e))
                        continue

                    logging.info('[BotCore] Connection issue resolved.')
                    if not(self.socket_api.socketRunning):
                        logging.info('[BotCore] Attempting socket restart.')
                        self.socket_api.start()


    def get_trader_data(self):
        '''  '''
        rData       = {'traders':[], 'topData':None}
        tradeTotal  = 0
        outcomes    = 0
        market_types = ['short', 'long']

        for trader_ in self.trader_objects:
            trader_data = trader_.get_trader_data()

            rData['traders'].append(trader_data)

            for market_type in market_types:
                outcomes += trader_data['traderStats']['overall'][market_type]

                tradeTotal += trader_data['traderStats']['#Trades'][market_type]

        rData['topData'] = {'oTrades':tradeTotal, 'oTotal':outcomes}
        return(rData)


    def get_trader_indicators(self):
        indicator_data_set = {}
        for _trader in self.trader_objects:
            indicator_data_set.update({_trader.print_pair:_trader.indicators})
        return(indicator_data_set)


def start(settings, order_log_path):
    '''
    Intilize the bot core object and also the flask object
    '''
    global BOT_CORE, host_ip, host_port

    if BOT_CORE == None:
        BOT_CORE = BotCore(
            settings['run_type'],
            settings['market_type'],
            settings['public_key'],
            settings['private_key'],
            settings['trading_currency'],
            settings['trading_markets'],
            settings['trader_interval'],
            settings['max_candles'],
            settings['max_depth'],
            order_log_path)
        BOT_CORE.start()

    logging.info('[BotCore] Starting traders in {0} mode, market type is {1}.'.format(settings['run_type'], settings['market_type']))
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    host_ip = settings['host_ip']
    host_port = settings['host_port']

    SOCKET_IO.run(APP, 
        host=settings['host_ip'], 
        port=settings['host_port'], 
        debug=True, 
        use_reloader=False)