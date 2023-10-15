import pandas_ta as ta
import pandas as pd
import warnings
import numpy as np
#from pylab import *
import math
import time
from binance_spot.binance.spot import Spot 
import pandas as pd
import datetime
import requests


warnings.simplefilter(action='ignore',category=FutureWarning)
pd.set_option("display.max_rows",1000)

from binance.client import Client

api_key = 'Wo34893AHGp4kCEkRYrzCDjNz17wyU4Qb4kDJMOZ8T7GwvjqPqqJiTNXuPsP9GJ4' #請自己寫api
api_secret = '1k4yEPjzc23bByV3PQsFslzDBdUjyMeoqgvdY9Rd9ZI0v2klFxTBdvLxNRJ2VqRi'#請自己寫api

bin_client = Client(api_key, api_secret)

Spot_client = Spot()


symbol='ETHUSDT'


def check_position(bin_client): #查看倉位
    get_position=bin_client.futures_account()['positions']
    for i in get_position:
        if i['symbol']==symbol and i['positionSide']=='LONG':
            if float(i['positionAmt']) == 0:
                Long_have_position=False
            else:
                Long_have_position=True
        if i['symbol']==symbol and i['positionSide']=='SHORT':
            if float(i['positionAmt']) == 0:
                Short_have_position=False
            else:
                Short_have_position=True

    return Long_have_position , Short_have_position

while 1:
    Long_have_position , Short_have_position = check_position(bin_client)
    print(Long_have_position , Short_have_position)
    time.sleep(5)
