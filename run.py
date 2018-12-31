#! /usr/bin/env python3

import sys
import os
import json
import time

try: 
	import calls
except ModuleNotFoundError:
	sys.exit("Make sure you have \"Calls\" in site-packages or the same directory.")

try: import TradeIndicators
except ModuleNotFoundError:
	sys.exit("Make sure you have \"TradeIndicators\" in site-packages or the same directory.")

try: import Trading_Bot
except ModuleNotFoundError:
	sys.exit("Make sure you have \"Trading_Bot\" in the same directory.")

ver = 6.5

## This creates file paths.
extra_directory = ("{0}/extra/".format(os.getcwd()))
settings_file_path = ("{0}settings.json".format(extra_directory))

## This creates the setting file if it was not found.
def initial_setup():

	if not os.path.isdir(extra_directory):
		os.mkdir(extra_directory)

	settingFileDate = '{"Currency_Allowed" : 0.002,\n"Market" : "BTC-LTC",\n"Time_Interval" : "5m",\n"Keys": {"Public" : "None",\n\t"Secret" : "None"}\n}'

	logFile = open(settings_file_path, 'w')
	logFile.write(settingFileDate)
	logFile.close()


def setup():
	## This sets up the traders and also formats the markets.
	global traderBot

	if not os.path.isfile(settings_file_path):
		sys.exit("There was an error reading settings file, try ./run init")

	## This section is for reading data from the settings file and storing it.
	settings_file = open(settings_file_path, 'r')
	settings_file_data = json.loads(settings_file.read())
	settings_file.close()

	## Start for settings file variable.
	Time_Interval = settings_file_data['Time_Interval']
	Market = settings_file_data['Market'].upper()
	Currency_Allowed = settings_file_data["Currency_Allowed"]
	PKEY = settings_file_data['Keys']['Public']
	SKEY = settings_file_data['Keys']['Secret']
	## End of Custome Setting Variables ##

	print("Binance Trader, Version: {0}, Time int: {1}, Market: {2}".format(ver, Time_Interval, Market))

	traderBot = Trading_Bot.trader(PKEY, SKEY, Market, float(Currency_Allowed), Time_Interval)


def run_bots():
	## This is the main calling section for the traders.
	forceUpdate = True
	maxCycle = 10
	cycle = maxCycle-1

	while True:

		traderBot.update(forceUpdate)

		if not(forceUpdate):
			traderBot.main()

		forceUpdate=False

		time.sleep(3.4)
		if cycle == maxCycle:
			print("]-------------------------------------------------[")
			print_data(traderBot.get_bot_info())
			print("]-------------------------------------------------[\n\n")
			cycle = 0
		else:
			cycle += 1


def print_data(data):
	MACD 	= data["Ind"]["MACD"]
	precis 	= data["MR"]["TICK_SIZE"]

	print("Market: {1} | overall: {2:.{0}f} | #Trades {3} | left: {4:.6f}".format(precis, data["market"], data["TS"]["overall"], data["TS"]["#Trades"], data["currencyLeft"]))
	
	if data["status"] == "STANDBY_ERROR":
		print("[STATUS] Data Error, trying to fix... | lastUpdate: {0}".format(data["time"]))
		
	else:
		marketTrade = "Sell: {0}".format(data["CTI"]["tradeTypes"]["S"]) if str(data["CTI"]["tradeTypes"]["B"]) == "None" else "Buy: {0}".format(data["CTI"]["tradeTypes"]["B"])
		marketOrder = "Order Status: {0}".format(data["CTI"]["orderStatus"]["S"] if str(data["CTI"]["tradeTypes"]["B"]) == "None" else data["CTI"]["orderStatus"]["B"])

		if data["status"] == "RUNNING":
			print("[STATUS] {0} | {1} | lastUpdate: {2}".format(marketTrade, marketOrder, data["time"]))

		print("[PRICES] buyPrice: {1:.{0}f} | sellPrice: {2:.{0}f}".format(precis, data["CTI"]["buyPrice"], data["CTI"]["sellPrice"]))
		print("[CONDITIONS] fast: {0:.8f} | slow: {1:.8f}".format(MACD[0]["fast"], MACD[0]["slow"]))


if __name__ == "__main__":

	if len(sys.argv) == 1: 
		setup()
		run_bots()
	elif sys.argv[1] == "init":
		initial_setup()
		print("Initilization Successfull")
	else:
		print("incorrect argument")
	



