# Simple Binance Trader

# Disclaimer
I am not responsible for the trades you make with the script, this script has not been exstensivly tested on live trades.

NOTE: The current strtergy is also very weak and will mostlikley return only losses therefore I recomend you create your work or use some which would work. However the trader currently also does not support simulated trades and only support live trading, simulated trades should be added in the future so you may need to wait until then to use this to test stratergies.

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
- "publicKey" = Public API key.
- "privateKey" = Private API key.
- "runType" = Which mode to run teh trader (TEST/REAL) currently only real trades are configured, no simulation mode has been added yet
- "mainInterval" = The Time interval for candles.
- "traderCurrency" = The amount of btc allowed to share between every market.
- "markets" = The market(s) you want to trade (currently only BTC markets are supported).
- "host_ip" = Host IP can be set for the webserver to access the trader.
- "host_port" = Host port can be set for the webserver to access the trader.

## Usage
I recommend setting this all up within a virtual python enviornment:
First get the base modules:
 - To quickly install all the required modules use 'pip3 install -r requirements'.

Secondly get the required techinal indicators module adn binance api.
 - https://github.com/EasyAI/binance_api, This is the binance API that the trader uses.
 - https://github.com/EasyAI/Python-Charting-Indicators, This contains the logic to calculate technical indicators.

Move them into the site-packages folder.
Finally navigate to the trader directory.

To set up the bot and for any further detail please refer to the google doc link below:
https://docs.google.com/document/d/1VUx_1O5kQQxk0HfqqA8WyQpk6EbbnXcezAdqXkOMklo/edit?usp=sharing

### Contact
Please if you find any bugs or issues contact me so I can improve.
EMAIL: jlennie1996@gmail.com
