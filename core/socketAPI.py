#! /usr/bin/env python3

import time
import json
import logging
import websocket
import threading


## sets up the socket BASE for binances socket API.
SOCKET_BASE = 'wss://stream.binance.com:9443'


class BinanceSOCK:

    def __init__(self, query):
        '''
        Setup the connection and setup data containers and management variables for the socket.
        '''
        streams = []
        self.forceClose = False
        self.socketRunning = False

        self.socketBuffer = {'depth':{'bids':[], 'asks':[]}, 'candle':{}}

        if query[-1] == '/':
            query = query[:-1]

        self.destURL = '{0}/stream?streams={1}'.format(SOCKET_BASE, query)


    def start(self):
        '''
        This is used to start the socket.
        '''
        if not(self.socketRunning):
            logging.info('SOCKET: Setting up socket connection.')
            self.create_socket()
            logging.info('SOCKET: Setup socket.')

            ## -------------------------------------------------------------- ##
            # This block is used to test connectivity to the socket.
            conn_timeout = 5
            while not self.ws.sock or not self.ws.sock.connected and conn_timeout:
                time.sleep(1)
                conn_timeout -= 1

                if not conn_timeout:
                    # If the timeout limit is reached then the websocket is force closed.
                    self.ws.close()
                    raise websocket.WebSocketTimeoutException('Couldn\'t connect to WS! Exiting.')
            ## -------------------------------------------------------------- ##

            self.socketRunning = True
            logging.info('SOCKET: Sucessfully created socket connection.')

        logging.info('SOCKET: Sucessfully started socket.')


    def get_buffer(self):
        '''
        This is called for retrival of the current data stored in the buffer object.
        '''
        return(self.socketBuffer)


    def create_socket(self):
        '''
        This is used to initilise connection and set it up to the exchange.
        '''
        self.ws = websocket.WebSocketApp(self.destURL,
            on_open = self._on_Open,
            on_message = self._on_Message,
            on_error = self._on_Error,
            on_close = self._on_Close)

        wsthread = threading.Thread(target=lambda: self.ws.run_forever())
        wsthread.start()


    def _on_Open(self):
        '''
        This is called to manually open the websocket connection.
        '''
        logging.info('SOCKET: Websocket Opened.')


    def _on_Message(self, message):
        '''
        This is used to handle any messages recived via the websocket.
        '''
        data = json.loads(message)

        if data['stream'][data['stream'].index('@')+1:-2] == 'depth':
            self.socketBuffer['depth']['bids'] = data['data']['bids']
            self.socketBuffer['depth']['asks'] = data['data']['asks']
        else:
            cData = data['data']['k']
            candle = {
                'time':int(cData['t']), 
                'open':float(cData['o']),
                'high':float(cData['h']),
                'low':float(cData['l']),
                'close':float(cData['c']),
                'volume':float(cData['v'])}

            self.socketBuffer['candle'] = candle


    def _on_Error(self, error):
        '''
        This is called when the socket recives an connection based error.
        '''
        logging.warning('SOCKET: {0}'.format(error))
        if self.socketRunning:
            time.sleep(10)


    def _on_Close(self):
        '''
        This is called for manually closing the websocket.
        '''
        self.socketRunning = False
        logging.info('SOCKET: Socket closed.')