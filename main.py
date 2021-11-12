# imports
import time
import os
from dotenv import load_dotenv
from pathlib import Path
import logging

from api_trader import ApiTrader
from tdameritrade import TDAmeritrade
from gmail import Gmail
from mongo import MongoDB

from assets.pushsafer import PushNotification
from assets.exception_handler import exception_handler
from assets.helper_functions import selectSleep
from assets.timeformatter import Formatter
from assets.multifilehandler import MultiFileHandler

THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))

assets = os.path.join(THIS_FOLDER, 'assets')

path = Path(THIS_FOLDER)

load_dotenv(dotenv_path=f"{path.parent}/config.env")

RUN_LIVE_TRADER = True if os.getenv('RUN_LIVE_TRADER') == "True" else False


class Main:

    def connectAll(self):
        """ METHOD INITIALIZES LOGGER, MONGO, GMAIL, PAPERTRADER.
        """

        # INSTANTIATE LOGGER
        file_handler = MultiFileHandler(filename='logs/error.log', mode='a')

        formatter = Formatter('%(asctime)s [%(levelname)s] %(message)s')

        file_handler.setFormatter(formatter)

        ch = logging.StreamHandler()

        ch.setLevel(level="INFO")

        ch.setFormatter(formatter)

        self.logger = logging.getLogger(__name__)

        self.logger.setLevel(level="INFO")

        self.logger.addHandler(file_handler)

        self.logger.addHandler(ch)

        # CONNECT TO MONGO
        self.mongo = MongoDB(self.logger)

        mongo_connected = self.mongo.connect()

        # CONNECT TO GMAIL API
        self.gmail = Gmail(self.logger)

        gmail_connected = self.gmail.connect()

        if mongo_connected and gmail_connected:

            self.traders = {}

            self.accounts = []

            self.not_connected = []

            self.logger.info(
                f"LIVE TRADER IS {'ACTIVE' if RUN_LIVE_TRADER else 'INACTIVE'}", extra={'log': False})

            self.logger.info(
                f"PAPER TRADER IS {'INACTIVE' if RUN_LIVE_TRADER else 'ACTIVE'}\n", extra={'log': False})

            return True

        return False

    @exception_handler
    def setupTraders(self):
        """ METHOD GETS ALL USERS ACCOUNTS FROM MONGO AND CREATES LIVE TRADER INSTANCES FOR THOSE ACCOUNTS.
            IF ACCOUNT INSTANCE ALREADY IN SELF.TRADERS DICT, THEN ACCOUNT INSTANCE WILL NOT BE CREATED AGAIN.
        """
       # GET ALL USERS ACCOUNTS
        users = self.mongo.users.find({})

        for user in users:

            try:

                for account_id in user["Accounts"].keys():

                    if account_id not in self.traders and account_id not in self.not_connected:

                        push_notification = PushNotification(
                            user["deviceID"], self.logger)

                        tdameritrade = TDAmeritrade(
                            self.mongo, user, account_id, self.logger, push_notification)

                        connected = tdameritrade.initialConnect()

                        if connected:

                            obj = ApiTrader(user, self.mongo, push_notification, self.logger, int(
                                account_id), tdameritrade, RUN_LIVE_TRADER)

                            self.traders[account_id] = obj

                            time.sleep(0.1)

                        else:

                            self.not_connected.append(account_id)

                    self.accounts.append(account_id)

            except Exception as e:

                logging.error(e)

    @exception_handler
    def run(self):
        """ METHOD RUNS THE TWO METHODS ABOVE AND THEN RUNS LIVE TRADER METHOD RUNTRADER FOR EACH INSTANCE.
        """

        self.setupTraders()

        trade_data = self.gmail.getEmails()

        for api_trader in self.traders.values():

            api_trader.runTrader(trade_data)


if __name__ == "__main__":
    """ START OF SCRIPT.
        INITIALIZES MAIN CLASS AND STARTS RUN METHOD ON WHILE LOOP WITH A DYNAMIC SLEEP TIME.
    """

    main = Main()

    connected = main.connectAll()

    if connected:
        
        while True:

            main.run()

            time.sleep(selectSleep())
