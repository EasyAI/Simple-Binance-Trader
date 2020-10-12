# Simple Binance Trader

# Disclaimer
I am not responsible for the trades you make with the script, this script has not been exstensivly tested on live trades.

NOTE: The current strtergy is also very weak and will mostlikley return only losses therefore I recomend you create your work or use some which would work. However the trader currently also does not support simulated trades and only support live trading, simulated trades should be added in the future so you may need to wait until then to use this to test stratergies.

NOTE: Testing has been re-enabled I also recomend updating the binance_api again.

NOTE: Trader now supports MARGIN trades allowing the placement of short and long positions. If SPOT trading put your conditions within the "long_entry/long_exit" sections within the trader_configuration.py file.


## Description
This is a simple binance trader that uses the REST api and sockets to allow automation or manipulation of account detail/data. The script which in the default configuration uses a basic MACD trading setup to trade. The script however is very customisable and you'll be able to configure it as you with via the help of the document in the usage section.

### Repository Contains:
- run.py : This is used to start/setup the bot.
- trader_configuration.py : Here is where you write your conditions using python logic.
- settings.txt : This contains indicators that can be used by the bot.
- Core
  - botCore.py : Is used to manage the socket and trader as well as pull data to be displayed.
  - handler.py : handles file reading/saving for cached data.
  - trader.py : The main trader inchage or updating and watching orders.
  - static : Folder for static files for the website (js/css).
  - templates : Folder for HTML page templates.
  
### Setting File:
- PUBLIC_KEY -  Your public binanace api key
- PRIVATE_KEY - Your private binanace api key
- IS_TEST - If the trader should only simulate orders or actually place them (if running real api keys are required)
- MARKET_TYPE - Market type to be traded (SPOT/MARGIN)
- TRADER_INTERVAL - The interval that is being traded at 3m, 5m, 1h, 1d, etc.
- TRADING_CURRENCY - The amount of curreny each trader can use for its trades (in BTC)
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
