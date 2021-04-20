#! /usr/bin/env python3

'''
Botcore

'''
import os
import os.path
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

APP         = Flask(__name__)
SOCKET_IO   = SocketIO(APP)

##
core_object    = None
host_ip     = ''
host_port   = ''

CAHCE_FILES = 'traders.json'


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

    return(render_template('main_page.html', data=start_up_data))


@APP.route('/rest-api/v1/add_trader', methods=['POST'])
def add_trader():
    print(request.get_json())
    return(json.dumps({'call':True}))


@APP.route('/rest-api/v1/trader_update', methods=['POST'])
def update_trader():
    post_data = request.get_json()
    current_trader = None
    for trader in core_object.trader_objects:
        if trader.print_pair == post_data['market']:
            current_trader = trader
            break

    if current_trader == None:
        return(json.dumps({'call':False}))

    elif post_data['action'] == 'remove':
        trader.stop()
    elif post_data['action'] == 'start':
        if trader.state_data['runtime_state'] == 'FORCE_PAUSE':
            trader.state_data['runtime_state'] = 'RUN'

    elif post_data['action'] == 'pause':
        if trader.state_data['runtime_state'] == 'RUN':
            trader.state_data['runtime_state'] = 'FORCE_PAUSE'

    else:
        return(json.dumps({'call':False}))

    return(json.dumps({'call':True}))


@APP.route('/rest-api/v1/get_trader_indicators', methods=['GET'])
def get_trader_indicators():
    print(request.get_json())
    return(json.dumps({'call':True, 'data':core_object.get_trader_indicators()}))


@APP.route('/rest-api/v1/get_trader_candles', methods=['GET'])
def get_trader_candles():
    print(request.get_json())
    return(json.dumps({'call':True, 'data':core_object.get_trader_candles()}))



@APP.route('/rest-api/v1/test', methods=['GET'])
def test_rest_call():
    return(json.dumps({'call':True,'data':'Hello World'}))


def web_updater():
    lastHash = None

    while True:
        if core_object.coreState == 'RUN':
            traderData = core_object.get_trader_data()
            currHash = hashlib.md5(str(traderData).encode())

            if lastHash != currHash:
                lastHash = currHash
                SOCKET_IO.emit('current_traders_data', {'data':traderData})

        time.sleep(2)


class BotCore():

    def __init__(self, settings, logs_dir, cache_dir):
        ''' 
        
        '''
        logging.info('[BotCore] Initilizing the BotCore object.')

        self.rest_api           = rest_master.Binance_REST(settings['public_key'], settings['private_key'])
        self.socket_api         = socket_master.Binance_SOCK()

        self.logs_dir           = logs_dir
        self.cache_dir          = cache_dir

        self.run_type           = settings['run_type']
        self.market_type        = settings['market_type']

        self.update_bnb_balance = settings['update_bnb_balance']

        self.max_candles        = settings['max_candles']
        self.max_depth          = settings['max_depth']

        pair_one = settings['trading_markets'][0]

        self.quote_asset        = pair_one[:pair_one.index('-')]
        self.base_currency      = settings['trading_currency']
        self.candle_Interval    = settings['trader_interval']

        self.trader_objects     = []
        self.trading_markets    = settings['trading_markets']

        self.coreState          = None


    def start(self):
        ''' '''
        logging.info('[BotCore] Starting the BotCore object.')
        self.coreState = 'SETUP'

        ## check markets
        found_markets = []
        not_supported = []

        for market in self.rest_api.get_exchangeInfo()['symbols']:
            fmtMarket = '{0}-{1}'.format(market['quoteAsset'], market['baseAsset'])

            # If the current market is not in the trading markets list then skip.
            if not fmtMarket in self.trading_markets:
                continue

            found_markets.append(fmtMarket)

            if (self.market_type == 'MARGIN' and market['isMarginTradingAllowed'] == False) or (self.market_type == 'SPOT' and market['isSpotTradingAllowed'] == False):
                not_supported.append(fmtMarket)
                continue

            # This is used to setup min quantity.
            if float(market['filters'][2]['minQty']) < 1.0:
                minQuantBase = (Decimal(market['filters'][2]['minQty'])).as_tuple()
                lS = abs(int(len(minQuantBase.digits)+minQuantBase.exponent))+1
            else: lS = 0

            # This is used to set up the price precision for the market.
            tickSizeBase = (Decimal(market['filters'][0]['tickSize'])).as_tuple()
            tS = abs(int(len(tickSizeBase.digits)+tickSizeBase.exponent))+1

            # This is used to get the markets minimal notation.
            mN = float(market['filters'][3]['minNotional'])

            # Put all rules into a json object to pass to the trader.
            market_rules = {'LOT_SIZE':lS, 'TICK_SIZE':tS, 'MINIMUM_NOTATION':mN}

            # Initilize trader objecta dn also set-up its inital required data.
            traderObject = trader.BaseTrader(market['quoteAsset'], market['baseAsset'], self.rest_api, socket_api=self.socket_api)
            traderObject.setup_initial_values(self.market_type, self.run_type, market_rules)
            self.trader_objects.append(traderObject)

        
        ## Show markets that dont exist on the binance exchange.
        if len(self.trading_markets) != len(found_markets):
            no_market_text = ''
            for market in [market for market in self.trading_markets if market not in found_markets]:
                no_market_text+=str(market)+', '
            logging.warning('Following pairs dont exist: {}'.format(no_market_text[:-2]))

        ## Show markets that dont support the market type.
        if len(not_supported) > 0:
            not_support_text = ''
            for market in not_supported:
                not_support_text += ' '+str(market)
            logging.warning('[BotCore] Following market pairs are not supported for {}: {}'.format(self.market_type, not_support_text))

        valid_tading_markets = [market for market in found_markets if market not in not_supported]

        ## setup the binance socket.
        for market in valid_tading_markets:
            self.socket_api.set_candle_stream(symbol=market, interval=self.candle_Interval)
            self.socket_api.set_manual_depth_stream(symbol=market, update_speed='1000ms')

        if self.run_type == 'REAL':
            self.socket_api.set_userDataStream(self.rest_api, self.market_type)

        self.socket_api.BASE_CANDLE_LIMIT = self.max_candles
        self.socket_api.BASE_DEPTH_LIMIT = self.max_depth

        self.socket_api.build_query()
        self.socket_api.set_live_and_historic_combo(self.rest_api)

        self.socket_api.start()

        # Load the wallets.
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
        else:
            current_tokens = {self.quote_asset:[float(self.base_currency), 0.0]}

        # Load cached data
        cached_traders_data = None
        if os.path.exists(self.cache_dir+CAHCE_FILES[0]):
            with open(self.cache_dir+CAHCE_FILES[0], 'r') as f:
                cached_traders_data = json.load(f)['data']

        ## Setup the trader objects and start them.
        logging.info('[BotCore] Starting the trader objects.')
        for trader_ in self.trader_objects:
            currSymbol = "{0}{1}".format(trader_.base_asset, trader_.quote_asset)

            # Update trader with cached data (to resume trades/keep records of trades.)
            if cached_traders_data != '' and cached_traders_data:
                for cached_trader in cached_traders_data:
                    m_split = cached_trader['market'].split('-')
                    if (m_split[1]+m_split[0]) == currSymbol:
                        trader_.configuration           = cached_trader['configuration']
                        trader_.custom_conditional_data = cached_trader['custom_conditions']
                        trader_.market_activity         = cached_trader['market_activity']
                        trader_.trade_recorder          = cached_trader['trade_recorder']
                        trader_.state_data              = cached_trader['state_data']

            wallet_pair = {}

            if trader_.quote_asset in current_tokens:
                wallet_pair.update({trader_.quote_asset:current_tokens[trader_.quote_asset]})

            if trader_.base_asset in current_tokens:
                wallet_pair.update({trader_.base_asset:current_tokens[trader_.base_asset]})

            trader_.start(self.base_currency, wallet_pair)

        logging.debug('[BotCore] Starting trader manager')
        TM_thread = threading.Thread(target=self._trader_manager)
        TM_thread.start()

        if self.update_bnb_balance:
            logging.debug('[BotCore] Starting BNB manager')
            BNB_thread = threading.Thread(target=self._bnb_manager)
            BNB_thread.start()

        logging.debug('[BotCore] Starting connection manager thread.')
        CM_thread = threading.Thread(target=self._connection_manager)
        CM_thread.start()

        logging.debug('[BotCore] Starting file manager thread.')
        FM_thread = threading.Thread(target=self._file_manager)
        FM_thread.start()

        logging.info('[BotCore] BotCore successfully started.')
        self.coreState = 'RUN'


    def _trader_manager(self):
        ''' '''
        while self.coreState != 'STOP':
            pass


    def _bnb_manager(self):
        ''' This will manage BNB balance and update if there is low BNB in account. '''
        last_wallet_update_time = 0

        while self.coreState != 'STOP':
            socket_buffer_global = self.socket_api.socketBuffer

            # If outbound postion is seen then wallet has updated.
            if 'outboundAccountPosition' in socket_buffer_global:
                if last_wallet_update_time != socket_buffer_global['outboundAccountPosition']['E']:
                    last_wallet_update_time = socket_buffer_global['outboundAccountPosition']['E']

                    for wallet in socket_buffer_global['outboundAccountPosition']['B']:
                        if wallet['a'] == 'BNB':
                            if float(wallet['f']) < 0.01:
                                bnb_order = self.rest_api.place_order(self.market_type, symbol='BNBBTC', side='BUY', type='MARKET', quantity=0.1)
                                print(wallet)
                                print(bnb_order)
            time.sleep(2)


    def _file_manager(self):
        ''' This section is responsible for activly updating the traders cache files. '''
        while self.coreState != 'STOP':
            time.sleep(15)

            traders_data = self.get_trader_data()
            if os.path.exists(self.cache_dir):
                file_path = '{0}{1}'.format(self.cache_dir,CAHCE_FILES)
                with open(file_path, 'w') as f:
                    json.dump({'lastUpdateTime':time.time() ,'data':traders_data}, f)


    def _connection_manager(self):
        ''' This section is responsible for re-testing connectiongs in the event of a disconnect. '''
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
        ''' This can be called to return data for each of the active traders. '''
        rData = []
        for trader_ in self.trader_objects:
            rData.append(trader_.get_trader_data())
        return(rData)


    def get_trader_indicators(self):
        ''' This can be called to return the indicators that are used by the traders (Will be used to display web UI activity.) '''
        indicator_data_set = {}
        for _trader in self.trader_objects:
            indicator_data_set.update({_trader.print_pair:_trader.indicators})
        return(indicator_data_set)


    def get_trader_candles(self):
        ''' This can be called to return the candle data for the traders (Will be used to display web UI activity.) '''
        candle_data_set = {}
        for _trader in self.trader_objects:
            sock_symbol = str(_trader.base_asset)+str(_trader.quote_asset)
            candle_data_set.update({_trader.print_pair:self.socket_api.get_live_candles(sock_symbol)})
        return(candle_data_set)


def start(settings, logs_dir, cache_dir):
    global core_object, host_ip, host_port

    if core_object == None:
        core_object = BotCore(settings, logs_dir, cache_dir)
        core_object.start()

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