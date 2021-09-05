#! /usr/bin/env python3
import os
import sys
import time
import json
import os.path
import hashlib
import logging
import threading
from decimal import Decimal
from flask_socketio import SocketIO
from flask import Flask, render_template, url_for, request

from binance_api import api_master_rest_caller
from binance_api import api_master_socket_caller

from . import trader


MULTI_DEPTH_INDICATORS = ['ema', 'sma', 'rma', 'order']

# Initilize globals.

## Setup flask app/socket
APP         = Flask(__name__)
SOCKET_IO   = SocketIO(APP)

## Initilize base core object.
core_object = None

started_updater = False

## Initilize IP/port pair globals.
host_ip     = ''
host_port   = ''

## Set traders cache file name.
CAHCE_FILES = 'traders.json'


@APP.context_processor
def override_url_for():
    return(dict(url_for=dated_url_for))


def dated_url_for(endpoint, **values):
    # Override to prevent cached assets being used.
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
    # Base control panel configuration.
    global started_updater 

    ## Web updater used for live updating.
    if not(started_updater):
        started_updater = True
        web_updater_thread = threading.Thread(target=web_updater)
        web_updater_thread.start()

    ## Set socket ip/port.
    start_up_data = {
        'host':{'IP': host_ip, 'Port': host_port},
        'market_symbols': core_object.trading_markets
    }

    return(render_template('main_page.html', data=start_up_data))


@APP.route('/rest-api/v1/trader_update', methods=['POST'])
def update_trader():
    # Base API for managing trader interaction.
    data = request.get_json()

    ## Check if specified bot exists.
    current_trader = api_error_check(data)

    if current_trader == None:
        ## No trader therefore return false.
        return(json.dumps({'call':False, 'message':'INVALID_TRADER'}))
    elif data['action'] == 'start':
        ## Updating trader status to running.
        if current_trader.state_data['runtime_state'] == 'FORCE_PAUSE':
            current_trader.state_data['runtime_state'] = 'RUN'
    elif data['action'] == 'pause':
        ## Updating trader status to paused.
        if current_trader.state_data['runtime_state'] == 'RUN':
            current_trader.state_data['runtime_state'] = 'FORCE_PAUSE'
    else:
        ## If action was not found return false
        return(json.dumps({'call':False, 'message':'INVALID_ACTION'}))

    return(json.dumps({'call':True}))


@APP.route('/rest-api/v1/get_trader_charting', methods=['GET'])
def get_trader_charting():
    # Endpoint to pass trader indicator data.
    market = request.args.get('market')
    limit = int(request.args.get('limit'))
    data = {'market':market}

    ## Check if specified bot exists.
    current_trader = api_error_check(data)

    if current_trader == None:
        ## No trader therefore return false.
        return(json.dumps({'call':False, 'message':'INVALID_TRADER'}))

    candle_data = core_object.get_trader_candles(current_trader.print_pair)[:limit]
    indicator_data = core_object.get_trader_indicators(current_trader.print_pair)
    short_indicator_data = shorten_indicators(indicator_data, candle_data[-1][0])

    return(json.dumps({'call':True, 'data':{'market':market, 'indicators':short_indicator_data, 'candles':candle_data}}))


@APP.route('/rest-api/v1/get_trader_indicators', methods=['GET'])
def get_trader_indicators():
    # Endpoint to pass trader indicator data.
    market = request.args.get('market')
    limit = int(request.args.get('limit'))
    data = {'market':market}

    ## Check if specified bot exists.
    current_trader = api_error_check(data)

    if current_trader == None:
        ## No trader therefore return false.
        return(json.dumps({'call':False, 'message':'INVALID_TRADER'}))

    indicator_data = core_object.get_trader_indicators(current_trader.print_pair)

    return(json.dumps({'call':True, 'data':{'market':market, 'indicators':indicator_data}}))


@APP.route('/rest-api/v1/get_trader_candles', methods=['GET'])
def get_trader_candles():
    # Endpoint to pass trader candles.
    market = request.args.get('market')
    limit = int(request.args.get('limit'))
    data = {'market':market}

    ## Check if specified bot exists.
    current_trader = api_error_check(data)

    if current_trader == None:
        ## No trader therefore return false.
        return(json.dumps({'call':False, 'message':'INVALID_TRADER'}))

    candle_data = core_object.get_trader_candles(current_trader.print_pair)[:limit]

    return(json.dumps({'call':True, 'data':{'market':market, 'candles':candle_data}}))


@APP.route('/rest-api/v1/test', methods=['GET'])
def test_rest_call():
    # API endpoint test
    return(json.dumps({'call':True, 'message':'HELLO WORLD!'}))


def shorten_indicators(indicators, end_time):
    base_indicators = {}

    for ind in indicators:
        if ind in MULTI_DEPTH_INDICATORS:
            base_indicators.update({ind:{}})
            for sub_ind in indicators[ind]:
                base_indicators[ind].update({sub_ind:[ [val[0] if ind != 'order' else val[0]*1000,val[1]] for val in indicators[ind][sub_ind] if (val[0] if ind != 'order' else val[0]*1000) > end_time ]})
        else:
            base_indicators.update({ind:[ [val[0],val[1]] for val in indicators[ind] if val[0] > end_time]})

    return(base_indicators)


def api_error_check(data):
    ## Check if specified bot exists.
    current_trader = None
    for trader in core_object.trader_objects:
        if trader.print_pair == data['market']:
            current_trader = trader
            break
    return(current_trader)


def web_updater():
    # Web updater use to update live via socket.
    lastHash = None

    while True:
        if core_object.coreState == 'RUN':
            ## Get trader data and hash it to find out if there have been any changes.
            traderData = core_object.get_trader_data()
            currHash = hashlib.md5(str(traderData).encode())

            if lastHash != currHash:
                ## Update any new changes via socket.
                lastHash = currHash
                total_bulk_data = []
                for trader in traderData:
                    bulk_data = {}
                    bulk_data.update({'market':trader['market']})
                    bulk_data.update({'trade_recorder':trader['trade_recorder']})
                    bulk_data.update({'wallet_pair':trader['wallet_pair']})

                    bulk_data.update(trader['custom_conditions'])
                    bulk_data.update(trader['market_activity'])
                    bulk_data.update(trader['market_prices'])
                    bulk_data.update(trader['state_data'])
                    total_bulk_data.append(bulk_data)

                SOCKET_IO.emit('current_traders_data', {'data':total_bulk_data})
                time.sleep(.8)


class BotCore():

    def __init__(self, settings, logs_dir, cache_dir):
        # Initilization for the bot core managment object.
        logging.info('[BotCore] Initilizing the BotCore object.')

        ## Setup binance REST and socket API.
        self.rest_api           = api_master_rest_caller.Binance_REST(settings['public_key'], settings['private_key'])
        self.socket_api         = api_master_socket_caller.Binance_SOCK()

        ## Setup the logs/cache dir locations.
        self.logs_dir           = logs_dir
        self.cache_dir          = cache_dir

        ## Setup run type, market type, and update bnb balance.
        self.run_type           = settings['run_type']
        self.market_type        = settings['market_type']
        self.update_bnb_balance = settings['update_bnb_balance']

        ## Setup max candle/depth setting.
        self.max_candles        = settings['max_candles']
        self.max_depth          = settings['max_depth']

        ## Get base quote pair (This prevents multiple different pairs from conflicting.)
        pair_one = settings['trading_markets'][0]

        self.quote_asset        = pair_one[:pair_one.index('-')]
        self.base_currency      = settings['trading_currency']
        self.candle_Interval    = settings['trader_interval']

        ## Initilize base trader settings.
        self.trader_objects     = []
        self.trading_markets    = settings['trading_markets']

        ## Initilize core state
        self.coreState          = 'READY'


    def start(self):
        # Start the core object.
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
        if os.path.exists(self.cache_dir+CAHCE_FILES):
            with open(self.cache_dir+CAHCE_FILES, 'r') as f:
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
        rData = [ _trader.get_trader_data() for _trader in self.trader_objects ]
        return(rData)


    def get_trader_indicators(self, market):
        ''' This can be called to return the indicators that are used by the traders (Will be used to display web UI activity.) '''
        for _trader in self.trader_objects:
            if _trader.print_pair == market:
                indicator_data = _trader.indicators
                indicator_data.update({'order':{'buy':[], 'sell':[]}})
                indicator_data['order']['buy'] = [ [order[0],order[1]] for order in _trader.trade_recorder if order[4] == 'BUY']
                indicator_data['order']['sell'] = [ [order[0],order[1]] for order in _trader.trade_recorder if order[4] == 'SELL']
                return(indicator_data)


    def get_trader_candles(self, market):
        ''' This can be called to return the candle data for the traders (Will be used to display web UI activity.) '''
        for _trader in self.trader_objects:
            if _trader.print_pair == market:
                sock_symbol = str(_trader.base_asset)+str(_trader.quote_asset)
                return(self.socket_api.get_live_candles(sock_symbol))


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
