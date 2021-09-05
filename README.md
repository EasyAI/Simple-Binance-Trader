# Simple Binance Trader

# Disclaimer
I am not responsible for the trades you make with the script, this script has not been exstensivly tested on live trades.

## Please check the following:
- Make sure your account uses BNB for the trade fees and that you have plenty of BNB for the trader to use for trades as if not there will be issues with the trader.
- Please clear any cache files when updating the trader as there may be issues if not.
- Please if any updates are also available for binance_api or the technical indicators update those also.


NOTE: The current strtergy is also very weak and will mostlikley return only losses therefore I recomend you create your work or use some which would work. However the trader currently also does not support simulated trades and only support live trading, simulated trades should be added in the future so you may need to wait until then to use this to test stratergies.

NOTE: Trader now supports MARGIN trades allowing the placement of short and long positions. If SPOT trading put your conditions within the "long_entry/long_exit" sections within the trader_configuration.py file.


## Description
This is a simple binance trader that uses the REST api and sockets to allow automation or manipulation of account detail/data. The script which in the default configuration uses a basic MACD trading setup to trade. The script however is very customisable and you'll be able to configure it as you with via the help of the document in the usage section.

### Repository Contains:
- run.py : This is used to start/setup the bot.
- trader_configuration.py : Here is where you write your conditions using python logic.
- patterns.py : Can be used to trade based on specific patterns.
- Core
  - botCore.py : Is used to manage the socket and trader as well as pull data to be displayed.
  - trader.py : The main trader inchage or updating and watching orders.
  - static : Folder for static files for the website (js/css).
  - templates : Folder for HTML page templates.
  
### Setting File:
- PUBLIC_KEY -  Your public binanace api key
- PRIVATE_KEY - Your private binanace api key
- IS_TEST - Allow trader to be run in test mode (True/False)
- MARKET_TYPE - Market type to be traded (SPOT/MARGIN)
- UPDATE_BNB_BALANCE - Automatically update the BNB balance when low (for trading fees, only applicable to real trading)
- TRADER_INTERVAL - Interval used for the trader (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d).
- TRADING_CURRENCY - The currency max the trader will use (in the quote key) also note this scales up with the number of markets i.e. 2 pairs each market will have 0.0015 as their trading currency pair.
- TRADING_MARKETS - The markets that are being traded and seperate with ',' (BTC-ETH,BTC-NEO)
- HOST_IP - The host IP for the web UI (if left blank default is 127.0.0.1)
- HOST_PORT - The host port for the web UI (if left blank default is 5000)
- MAX_CANDLES - Max candles the trader will use (if left brank default is 500)
- MAX_DEPTH - Max market depth the trader will use (if left brank default is 50)

## Usage
I recommend setting this all up within a virtual python enviornment:
First get the base modules:
 - To quickly install all the required modules use 'pip3 install -r requirements'.

Secondly get the required techinal indicators module adn binance api.
 - https://github.com/EasyAI/binance_api, This is the binance API that the trader uses.
 - https://github.com/EasyAI/Python-Charting-Indicators, This contains the logic to calculate technical indicators. (only the file technical_indicators.py is needed)

Move them into the site-packages folder. NOTE: If you get an error saying that either the technical_indicators or binance_api is not found you can move them in to the same directory as the run.py file for the trader.

Finally navigate to the trader directory.

To set up the bot and for any further detail please refer to the google doc link below:
https://docs.google.com/document/d/1VUx_1O5kQQxk0HfqqA8WyQpk6EbbnXcezAdqXkOMklo/edit?usp=sharing

### Contact
Please if you find any bugs or issues contact me so I can improve.
EMAIL: jlennie1996@gmail.com
