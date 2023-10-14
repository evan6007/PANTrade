import pandas_ta as ta
import pandas as pd
import warnings
import numpy as np
from pylab import *
import math
import time
from binance_spot.binance.spot import Spot 
import pandas as pd
import datetime
import requests


warnings.simplefilter(action='ignore',category=FutureWarning)
pd.set_option("display.max_rows",1000)

from binance.client import Client

api_key = '' #請自己寫api
api_secret = ''#請自己寫api

bin_client = Client(api_key, api_secret)

Spot_client = Spot()

def check_value(Spot_client):#讀取數據
    #參數
    m15=15*60*1000 #5分鐘轉換成毫秒

    #抓資料
    start = time.time()*1000-m15*300
    end = time.time()*1000
    new_start=int(start)
    new_end=int(end)
    df=pd.DataFrame(Spot_client.klines("BTCUSDT", "15m",limit=1000,startTime=str(new_start),endTime=str(new_end)))

    df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume','close_time', 'qav', 'num_trades','taker_base_vol', 'taker_quote_vol', 'ignore']
    df=df[['datetime', 'open', 'high', 'low', 'close']].astype(float)
    df.index = [datetime.datetime.fromtimestamp(x/1000.0) for x in df.datetime]
    df=df.astype(float)

    df['rsi']=ta.rsi(df['close'],length=14)
    df['5MA'] = df['close'].rolling(window=5).mean()
    df['10MA'] = df['close'].rolling(window=10).mean()


    now_open=df['open'].iloc[-1]
    now_close=df['close'].iloc[-1]
    now_rsi=df['rsi'].iloc[-1]
    now_5MA = df['5MA'].iloc[-1]
    now_10MA = df['10MA'].iloc[-1]

    second_last_5MA = df['5MA'].iloc[-2]
    second_last_10MA = df['10MA'].iloc[-2]
    second_last_rsi=df['rsi'].iloc[-2]

    third_last_5MA = df['5MA'].iloc[-3]
    third_last_10MA = df['10MA'].iloc[-3]
    third_last_rsi=df['rsi'].iloc[-3]

    high30 = df.iloc[-30:]['high'].max()
    low30 = df.iloc[-30:]['low'].min()
    
    return now_open,now_close,now_rsi,     second_last_5MA,second_last_10MA,second_last_rsi,      third_last_5MA,third_last_10MA,third_last_rsi  ,high30 ,low30

url = 'https://notify-api.line.me/api/notify'
token = 'Zk7at0w4dwEUirpo67Gd4SascWyV9vBzSbZbTwML2Qy'
headers = {
    'Authorization': 'Bearer ' + token    # 設定權杖
}


found_rsi_below_30 = False  
notified_for_rsi = False
notified_for_ma_cross = False

while 1:
    #確認 數值&倉位狀態
    
    now_open,now_close,now_rsi,\
    second_last_5MA,second_last_10MA,second_last_rsi,\
    third_last_5MA,third_last_10MA,third_last_rsi\
    ,high30 ,low30\
    =check_value(Spot_client) #確認技術指標數據

    
    # 檢查當前RSI是否低於30
    if second_last_rsi <= 30 and not notified_for_rsi:
        found_rsi_below_30 = True
        data = requests.post(url, headers=headers, data={'message':'found_rsi_below_30'})
        notified_for_rsi = True  # 設定為已通知

    # 如果先前已發現RSI低於30，則檢查5MA和10MA是否交叉
    #print(found_rsi_below_30 , third_last_5MA ,third_last_10MA ,  second_last_5MA , second_last_10MA)
    if found_rsi_below_30 and not notified_for_ma_cross:
        if (third_last_5MA < third_last_10MA) and (second_last_5MA > second_last_10MA):

            Cross_5MA_10MA = third_last_5MA + (third_last_10MA - third_last_5MA) / ((third_last_10MA - third_last_5MA) + (second_last_5MA - second_last_10MA)) * (second_last_5MA - third_last_5MA)
            Profit_Target_Price = Cross_5MA_10MA - low30 + Cross_5MA_10MA
            data = requests.post(url, headers=headers, data={'message':'5MA向上交叉10MA準備做多'})
            data = requests.post(url, headers=headers, data={'message':f'開盤價:{now_open},停損:{low30},停利:{Profit_Target_Price}'})
            notified_for_ma_cross = True  # 設定為已通知

    if notified_for_ma_cross == True:
        if (now_close >=Profit_Target_Price) | (now_close <= low30):
            found_rsi_below_30 = False  
            notified_for_rsi = False
            notified_for_ma_cross = False

    print(now_open,now_close,now_rsi,second_last_5MA,second_last_10MA,second_last_rsi,third_last_5MA,third_last_10MA,third_last_rsi,high30 ,low30)

    time.sleep(10)