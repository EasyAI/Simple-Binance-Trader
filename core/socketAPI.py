#! /usr/bin/env python3

'''
socketAPI

'''
import time
import json
import hashlib
import logging
import websocket
import threading


## sets up the socket BASE for binances socket API.
SOCKET_BASE = 'wss://stream.binance.com:9443'


class BinanceSOCK:

    def __init__(self):
        '''
        Setup the connection and setup data containers and management variables for the socket.
        '''
        self.socketRunning = False

        self.socketBuffer = {}

        self.ws = None
        

    def start(self, markets, query):
        '''
        This is used to start the socket.
        '''

        if self.ws != None and self.socketRunning:
            self.stop()

        ## -------------------------------------------------------------- ##
        ## Here the socket buffer is setup to store the data for each symbol.
        logging.debug('SOCKET: Setting up buffer.')
        socketBuffer = {}
        for market in markets:
            socketBuffer.update({market:{'depth':{'bids':[], 'asks':[]}, 'candle':{}}})
        self.socketBuffer = socketBuffer

        ## -------------------------------------------------------------- ##
        ## Here the sockets URL is set so it can be connected to.
        logging.debug('SOCKET: Setting up socket stream URL.')
        if query[-1] == '/':
            query = query[:-1]
        self.destURL = '{0}/stream?streams={1}'.format(SOCKET_BASE, query)

        ## -------------------------------------------------------------- ##
        ## Here the 'create_socket' function is called to attempt a connection to the socket.
        logging.debug('SOCKET: Setting up socket connection.')
        self.create_socket()

        ## -------------------------------------------------------------- ##
        # This block is used to test connectivity to the socket.
        conn_timeout = 5
        while not self.ws.sock or not self.ws.sock.connected and conn_timeout:
            time.sleep(5)
            conn_timeout -= 1

            if not conn_timeout:
                ## If the timeout limit is reached then the websocket is force closed.
                self.ws.close()
                raise websocket.WebSocketTimeoutException('Couldn\'t connect to WS! Exiting.')

        self.socketRunning = True
        logging.info('SOCKET: Sucessfully established the socket.')


    def stop(self):
        self.ws.close()

        while self.socketRunning:
            time.sleep(0.2)


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
        logging.debug('SOCKET: Websocket Opened.')


    def _on_Message(self, message):
        '''
        This is used to handle any messages recived via the websocket.
        '''
        data = json.loads(message)

        try:
            atIndex = data['stream'].index('@')
        except Exception as e:
            logging.warning('SOCKET: @ index find: {0}'.format(e))

        try:
            market = data['stream'][:atIndex]
        except Exception as e:
            logging.warning('SOCKET: market slicing: {0}'.format(e))

        if market in self.socketBuffer:
            if data['stream'][atIndex+1:atIndex+6] == 'depth':
                if data['data']['bids'] != []:
                    self.socketBuffer[market]['depth']['bids'] = data['data']['bids']
                    self.socketBuffer[market]['depth']['asks'] = data['data']['asks']
            else:
                cData = data['data']['k']
                candle = {
                    'time':int(cData['t']), 
                    'open':float(cData['o']),
                    'high':float(cData['h']),
                    'low':float(cData['l']),
                    'close':float(cData['c']),
                    'volume':float(cData['v'])}

                self.socketBuffer[market]['candle'] = candle


    def _on_Error(self, error):
        '''
        This is called when the socket recives an connection based error.
        '''
        logging.warning('SOCKET: {0}'.format(error))


    def _on_Close(self):
        '''
        This is called for manually closing the websocket.
        '''
        self.socketRunning = False
        logging.info('SOCKET: Socket closed.')