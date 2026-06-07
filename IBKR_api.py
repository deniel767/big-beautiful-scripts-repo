from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ib_insync import *
import threading
import time
import requests
import pandas as pd
from functools import wraps
import xml.etree.ElementTree as ET
import random
import os
from dotenv import load_dotenv

# load local .env file
load_dotenv()

HOST_IP = os.getenv('LOCAL_IP', '127.0.0.1')

# retry parameters
MAX_RETRIES = 3
RETRY_DELAY = 1
SAFETY_DELAY = 3

class TimeoutException(Exception):
    pass

# basic decorator for timing out functions
def timeout(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = [TimeoutException(f"Function '{func.__name__}' timed out after {seconds} seconds.")]
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    result[0] = e
            thread = threading.Thread(target=target)
            thread.start()
            thread.join(seconds)
            if thread.is_alive():
                raise TimeoutException(f"Function '{func.__name__}' timed out after {seconds} seconds.")
            elif isinstance(result[0], Exception):
                raise result[0]
            return result[0]
        return wrapper
    return decorator

#
# the following are basic functions required for rudimentary interaction with the IBKR API
#

class MyWrapper(EWrapper):
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        # Suppress "farm connection is OK" messages
        ignored_errors = (
            502,
            2014,
            2106,
            2158,
            10314,
            2104,
            2174,
            2176
        )
        if errorCode in ignored_errors:
            return
        print(f"Error {reqId} {errorCode} {errorString}")

class MyClient(EClient):
    def __init__(self, wrapper):
        super().__init__(wrapper)

class IBapi(MyWrapper, MyClient):
    def __init__(self):
        MyClient.__init__(self, self)
        self.historical_data = []
        self.data_end = threading.Event()

    def historicalData(self, reqId, bar):
        self.historical_data.append({
            "date": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume
        })

    def historicalDataEnd(self, reqId, start, end):
        self.data_end.set()  # signal that data collection is complete
        self.disconnect()

    def disconnect_gracefully(self):
        """Safely disconnect."""
        if self.isConnected():
            print("🔌 Disconnecting gracefully...")
            self.disconnect()
            self.connected_flag = False
            time.sleep(1)

def run_loop(app):
    app.run()

#
# actual functions for doing stuff
#

# main function for fetching historical stock data
def get_stock_data(symbol='', end_date='', duration='1 M', barSize='1 day', **kwargs):

    """
    Date format is: "%Y%m%d %H:%M:%S"
    i.e: 20250713 08:04:39

    Valid secTypes: STK, OPT, FUT, CONTFUT, IND, CASH, BAG, WAR, BOND, CMDTY, NEWS, FUND

    Eschanges:
     - SMART for stocks
     - CBOE for SPX
     - NASDAQ for COMP

    https://interactivebrokers.github.io/tws-api/historical_bars.html

    """

    predefined_symbols = {
        'AAPL': {'symbol': 'AAPL', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'},
        'TSLA': {'symbol': 'TSLA', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'},
        'AMZN': {'symbol': 'AMZN', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'},
        'GOOGL': {'symbol': 'GOOGL', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'},
        'MSFT': {'symbol': 'MSFT', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'},
        'NFLX': {'symbol': 'NFLX', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'},
        'NVDA': {'symbol': 'NVDA', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'},
        'META': {'symbol': 'META', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'},
        'ORCL': {'symbol': 'ORCL', 'secType': 'STK', 'exchange': 'SMART', 'currency': 'USD'}
    }

    # create app instance and connect
    app = IBapi()
    client_id = random.randint(1, 9999)
    app.nextValidId(client_id)
    app.connect(HOST_IP, 7496, clientId=client_id)

    # start API thread
    api_thread = threading.Thread(target=run_loop, args=[app], daemon=True)
    api_thread.start()

    # wait until connected
    # or max retries reached
    retry_count = 0
    while not app.isConnected() and retry_count < MAX_RETRIES:
        print(f'trying to connect {retry_count+1} try')
        retry_count += 1
        time.sleep(RETRY_DELAY)

    if retry_count == MAX_RETRIES:
        print(f'[ERROR] get_stock_data called for ticker={symbol}, end_date={end_date}, duration={duration}, barSize={barSize} FAILED TO CONNECT after {MAX_RETRIES} attempts')
        app.disconnect_gracefully()
        return pd.DataFrame()

    # after connection is established we wait a bit just in case
    time.sleep(SAFETY_DELAY)

    # define contract
    # contract is like a base template IBKR uses to identify assets
    contract = Contract()

    if symbol in predefined_symbols.keys():
        for key in predefined_symbols[symbol].keys():
            contract.__setattr__(key, predefined_symbols[symbol][key])
    elif all(k in kwargs for k in ['conId', 'exchange']):
        print(f'[INFO] Using conId')
        contract.conId = kwargs.get('conId')
        contract.exchange = kwargs.get('exchange')
    else:
        print(f'[INFO] Using default values for symbol {symbol}')
        contract.symbol = symbol
        contract.secType = kwargs.get('secType', 'STK')
        contract.exchange = kwargs.get('exchange', 'SMART')
        contract.currency = kwargs.get('currency', 'USD')
    df = pd.DataFrame()
    for _ in range(MAX_RETRIES):
        # clear old data and event
        app.historical_data.clear()
        app.data_end.clear()

        whatToShow = kwargs.get(
            'whatToShow',
            predefined_symbols.get(symbol, {}).get('whatToShow', 'TRADES')
        )

        # generate random reqId for each request to avoid conflicts
        reqId = random.randint(1,999)
        # request historical data
        # the actual API call if you will
        app.reqHistoricalData(
            reqId=reqId,
            contract=contract,
            endDateTime=end_date,
            durationStr=duration,
            barSizeSetting=barSize,
            whatToShow=whatToShow,
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[]
        )

        # wait for data since API needs some time to respond
        if app.data_end.wait(timeout=SAFETY_DELAY):
            df = pd.DataFrame(app.historical_data)
            if not df.empty:
                # no retry, we get data
                break
        else:
            # else sleep a little and retry
            time.sleep(RETRY_DELAY)

    if not df.empty:
        print(f'[INFO] get_stock_data called with contract={contract}, end_date={end_date}, duration={duration}, barSize={barSize} SUCCESSFULLY RETURNED {len(df)} points of data')
        app.cancelHistoricalData(reqId)
        app.disconnect_gracefully()
        return df
    else:
        print(f'[WARNING] get_stock_data called with contract={contract}, end_date={end_date}, duration={duration}, barSize={barSize} FAILED TO RETURN DATA')
        app.cancelHistoricalData(reqId)
        app.disconnect_gracefully()
        return pd.DataFrame()

# helper function for decoding what the API labels each instrument as
def symbol_search(symbol, secType, currency='USD'):

    client_id = random.randint(1, 9999)
    ib = IB()
    ib.connect(HOST_IP, 7496, clientId=client_id, readonly=True)

    matches = ib.reqMatchingSymbols(symbol)
    matches = [m for m in matches if m.contract.currency == currency]
    if secType:
        matches = [m for m in matches if m.contract.secType == secType]

    for m in matches:
        print(m.contract)

# contact ID is a good standalone identifier
# this function looks up a given conId
def fetch_contract_details_from_conid(conid: int, keys = []):

    ib = IB()
    client_id = random.randint(1, 9999)
    ib.connect(HOST_IP, 7496, clientId=client_id, readonly=True)

    c = Contract()
    c.conId = conid
    c.exchange = ""  # let IBKR resolve

    details = ib.reqContractDetails(c)

    if not details:
        print(f"No contract details found for conId {conid}")
        return

    if not keys:
        # Fallback: Print the entire object if no specific keys were requested
        print(details[0])
    else:
        # Explicit loop: Fetch only the requested attributes
        for key in keys:
            try:
                print(f"{key}: {getattr(details[0], key)}")
            except AttributeError:
                print(f"Attribute '{key}' not found on ContractDetails object!")

# function to request preconfigured Flex report from IBKR site
def fetch_ibkr_executions(token: str, query_id: str) -> pd.DataFrame:
    # request report generation
    url = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest?t={token}&q={query_id}&v=3"
    print(f'Trying to request: {url}')
    r = requests.get(url)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    try:
        reference_code = root.find('ReferenceCode').text
    except AttributeError:
        print('ReferenceCode not found in response XML, aborting now!')
        return pd.DataFrame()

    # request actual report
    url2 = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement?t={token}&q={reference_code}&v=3"
    r2 = requests.get(url2)
    r2.raise_for_status()

    root2 = ET.fromstring(r2.text)
    trades = []

    # parse the useful parts of the report
    for trade in root2.findall(".//Trade"):
        trades.append(trade.attrib)

    df = pd.DataFrame(trades)
    return df

if __name__ == "__main__":
    #fetch_contract_details_from_conid(557528367, ['contract'])
    #symbol_search(symbol='Dollar', secType='IND')

    get_stock_data('AAPL', '20251201 23:00:00', '1 M', '1 min')
    #df = get_stock_data(conId=49315275, exchange='NYBOT', whatToShow='MIDPOINT', end_date='20251128 23:00:00', duration='1 D', barSize='1 min')
    #df = get_stock_data(symbol='XAUUSD', end_date='20251128 23:00:00', duration='1 D', barSize='1 min')
    #print(df)