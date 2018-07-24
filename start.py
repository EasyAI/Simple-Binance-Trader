#! /usr/bin/python3

import sys
import os
import json
import time

try: import CryptoAlgs
except ModuleNotFoundError:
	sys.exit("Make sure you have \"CryptoAgls\" in site-packages or the same directory.")

try: import Trading_Bot as TB
except ModuleNotFoundError:
	sys.exit("Make sure you have \"Trading_Bot\" in the same directory.")

## This creates file paths.
SETTINGS_FILE_PATH = (os.getcwd()+"/settings.json")

## This creates the setting file if it was not found.
def make_settings_file():
	settingFileDate = '{"Currency_Allowed" : 0.002,\n"Markets" : ["BTC-LTC"],\n"Time_Interval" : "5m",\n"Loss_Threshold":5,\n"Keys": {"Public" : "None",\n\t"Secret" : "None"}\n}'

	logFile = open(SETTINGS_FILE_PATH, 'w')
	logFile.write(settingFileDate)
	logFile.close()

## This checks if the settings file exists.
if not os.path.isfile(SETTINGS_FILE_PATH):
	make_settings_file()

## This section is for reading data from the settings file and storing it.
settings_file = open(SETTINGS_FILE_PATH, 'r')
settings_file_data = json.loads(settings_file.read())
settings_file.close()

CURRENCY_ALLOWED = settings_file_data["Currency_Allowed"]
MARKET_TO_TRADE = settings_file_data["Markets"]
TIME_INTERVAL = settings_file_data["Time_Interval"]
LOSS_THRESHOLD = settings_file_data["Loss_Threshold"]
PKEY = settings_file_data["Keys"]["Public"]
SKEY = settings_file_data["Keys"]["Secret"]
## End of Custome Setting Variables ##

botCollection = {}


def setup():

	## THis gets the currency that the bots are allowed to trade and devices it between all the bots.
	currency = float("{0:.8f}".format(CURRENCY_ALLOWED/len(MARKET_TO_TRADE)))

	## This calles the initilisation of the bots.
	print("-<| Active Trades |>-")
	for market in MARKET_TO_TRADE:
		botCollection[market] = TB.trader(PKEY, SKEY, market, currency, TIME_INTERVAL, LOSS_THRESHOLD)


def run_bots():

	forceUpdate = True
	maxCycle = 10
	cycle = 9

	## This is the main loop for running the bot.
	while True:
		
		## This is used call updates for the bots.
		for index,bot in enumerate(botCollection):
			botCollection[bot].update(forceUpdate=forceUpdate)

		## This is where the trading is done by the bots.
		for index,bot in enumerate(botCollection):
			botCollection[bot].find_trade()

		## This displays data onto the terminal.
		if cycle >= maxCycle:
			cycle = 0
			for index,bot in enumerate(botCollection):
				botCollection[bot].print_out_statistics()
			print("------------------------------------------------------------")
		else: cycle += 1

		time.sleep(1.5)
		forceUpdate=False


if __name__ == "__main__":

	setup()
	run_bots()



