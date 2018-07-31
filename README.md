# Simple-Binance-Trader

Simple bollinger band trading bot for binance.


This Repository Contains:

- start.py : This is used to start the bot.
- gexchange : This is a type of global exchange api.
- algs.py : This contails some of the trades I use.
- Traiding_Bot.py : This is the main script for the bot.


SETTINGS:

- "Currency_Allowed" = THe amount of btc allowed to share between every market.
- "Markets" = The market(s) you want to trade.
- "Time_Interval" = The Time interval for candles.
- "Loss Threshold" = the amount in % before the bot sell for loss.
- "Keys" = both of the keys for the API.


Setup:

1.Make sure you put algs, gexchange and Trading_Bot into the same folder as start.py

2.Make the main script (start.py) executable (chmod u+x)

3. run start.py and it will create a settings file, populate the file.

4.Make sure you add/change the settings to fit your needs.(If you want to do real trades and not simulations you need your keys)

5.Run the script in a terminal (start.py) once you're happy with the settings.

6.Use the terminal keep track of activity.


CONTACT: If you would like to contact me please use jlennie1996@gmail.com
