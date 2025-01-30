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

def check_value(Spot_client):#讀取數據
    #參數
    m15=15*60*1000 #5分鐘轉換成毫秒
    #m1=1*60*1000 #5分鐘轉換成毫秒

    #抓資料
    start = time.time()*1000-m15*300
    end = time.time()*1000
    new_start=int(start)
    new_end=int(end)
    df=pd.DataFrame(Spot_client.klines(symbol, "15m",limit=1000,startTime=str(new_start),endTime=str(new_end)))

    df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume','close_time', 'qav', 'num_trades','taker_base_vol', 'taker_quote_vol', 'ignore']
    df=df[['datetime', 'open', 'high', 'low', 'close']].astype(float)
    #df.index = [datetime.datetime.fromtimestamp(x/1000.0) for x in df.datetime]
    df=df.astype(float)

    df['rsi']=ta.rsi(df['close'],length=14)
    df['5MA'] = df['close'].rolling(window=5).mean()
    df['10MA'] = df['close'].rolling(window=10).mean()

    now_time = datetime.datetime.fromtimestamp(df['datetime'].iloc[-1]/1000.0)

    now_low=round(df['low'].iloc[-1], 2)
    now_high=round(df['high'].iloc[-1], 2)

    now_open=round(df['open'].iloc[-1], 2)
    now_close=round(df['close'].iloc[-1], 2)
    now_rsi=round(df['rsi'].iloc[-1], 2)
    now_5MA = round(df['5MA'].iloc[-1], 2)
    now_10MA = round(df['10MA'].iloc[-1], 2)

    second_last_5MA = round(df['5MA'].iloc[-2], 2)
    second_last_10MA = round(df['10MA'].iloc[-2], 2)
    second_last_rsi=round(df['rsi'].iloc[-2], 2)

    # third_last_5MA = round(df['5MA'].iloc[-3], 2)
    # third_last_10MA = round(df['10MA'].iloc[-3], 2)
    # third_last_rsi=round(df['rsi'].iloc[-3], 2)

    high30 = round(df.iloc[-30:]['high'].max(), 2)
    low30 = round(df.iloc[-30:]['low'].min(), 2)

    return now_time ,now_low,now_high, now_open,now_close,now_rsi,  now_5MA,now_10MA,     second_last_5MA,second_last_10MA,second_last_rsi  ,high30 ,low30


def check_quantity(bin_client,now_close,U_quantity_percent):

    #查看最小下單單位
    info = bin_client.futures_exchange_info()
    symbols = info['symbols']
    for s in symbols:
        if s['symbol'] == symbol:
            min_qty = s['filters'][2]['minQty']
            print(f"最小下單: {min_qty}")


    balance = bin_client.futures_account_balance()
    for asset in balance:
        if asset['asset'] == 'USDT':
            USDTasset = asset['balance']
            print("U 本位 USDT 餘額:", asset['balance'])

    quantity=round(1/float(now_close)*100*float(USDTasset)*U_quantity_percent,4)
    print("數量:",quantity)

    return quantity

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
#------------------------------------------主程式-----------------------------------------------

url = 'https://notify-api.line.me/api/notify'
token = '0RxE9s8aOfLBoPOnGwiA3MQxEQBt2rZcpxaRRgvZmPh'
headers = {
    'Authorization': 'Bearer ' + token    # 設定權杖
}

found_rsi_below_30,notified_for_rsi30,notified_for_ma_cross30,notified_for_entry30_long,notified_for_entry30_short = False,False,False,False,False
Short_time,Long_time,cross_time,entry_time = " "," "," "," "

while 1:
    #確認 數值&倉位狀態
    
    now_time,\
    now_low,now_high,now_open,now_close,\
    now_rsi,now_5MA,now_10MA,\
    second_last_5MA,second_last_10MA,second_last_rsi,\
    high30 ,low30\
    =check_value(Spot_client) #確認技術指標數據

    Long_have_position , Short_have_position = check_position(bin_client)

    # 檢查前一根RSI是否低於30
    if second_last_rsi <= 30 and not notified_for_rsi30:
        found_rsi_below_30 = True
        data = requests.post(url, headers=headers, data={'message':f'RSI低於30: {second_last_rsi}'})
        notified_for_rsi30 = True  # 設定為已通知

    # 如果先前已發現RSI低於30，則檢查5MA和10MA是否交叉
    if found_rsi_below_30 and not notified_for_ma_cross30 and  (cross_time != now_time):
        if (second_last_5MA <= second_last_10MA) and (now_5MA > now_10MA):
            cross_time = now_time
            data = requests.post(url, headers=headers, data={'message':f'5MA向上交叉10MA開始震盪\n\
                                                                時間:{cross_time}'})
            Cross_5MA_10MA = second_last_5MA + (second_last_10MA - second_last_5MA) / ((second_last_10MA - second_last_5MA) + (now_5MA - now_10MA)) * (now_5MA - second_last_5MA)

            notified_for_ma_cross30 = True

    # 如果交叉，進入震盪區判斷做多or放空
    if notified_for_ma_cross30 and ((not notified_for_entry30_long) & (not notified_for_entry30_short)) and  (entry_time != now_time):

        upper_x2_bond = (Cross_5MA_10MA-low30)*2.0+Cross_5MA_10MA
        upper_bond = (Cross_5MA_10MA-low30)+Cross_5MA_10MA
        lower_bond = low30
        lower_x2_bond = Cross_5MA_10MA-(Cross_5MA_10MA-low30)*2.0

        if now_high >= upper_bond:
            entry_time = now_time
            Long_Profit_Loss_Percentage = ((upper_x2_bond - upper_bond) / upper_bond) * 100
            data = requests.post(url, headers=headers, data={'message':f'突破上限做多\n\
                                                                時間:{entry_time},\n\
                                                                價格:{now_close},\n\
                                                                做多停損點:{Cross_5MA_10MA},\n\
                                                                做多停利點:{upper_x2_bond}\n\
                                                                盈虧比+/- {Long_Profit_Loss_Percentage} %'})

            long_quantity=round(check_quantity(bin_client, now_close, 0.1), 3)
            #下單
            bin_client.futures_create_order(symbol=symbol,positionSide='LONG',side = 'BUY',type='MARKET',quantity=long_quantity,leverage=100) #precision=3
            #止盈
            bin_client.futures_create_order(symbol=symbol,positionSide='LONG',side='SELL',type ='TAKE_PROFIT_MARKET',quantity = long_quantity,
                                            stopPrice=round(float(upper_x2_bond),2),workingType='MARK_PRICE')#precision=3
            #止損
            bin_client.futures_create_order(symbol=symbol,positionSide='LONG',side='SELL',type ='STOP_MARKET',quantity = long_quantity,
                                            stopPrice=round(float(Cross_5MA_10MA),2),workingType='MARK_PRICE')#precision=3

            notified_for_entry30_long = True  # 設定為已通知
            print("做多")

        elif now_low <= lower_bond:
            entry_time = now_time
            Short_Profit_Loss_Percentage = ((upper_x2_bond - upper_bond) / upper_bond) * 100
            data = requests.post(url, headers=headers, data={'message':f'突破下限放空\n\
                                                                時間:{entry_time},\n\
                                                                價格:{now_close},\n\
                                                                放空停損點:{Cross_5MA_10MA},\n\
                                                                放空停利點:{lower_x2_bond}\n\
                                                                盈虧比+/- {Short_Profit_Loss_Percentage} %'})
            short_quantity=round(check_quantity(bin_client, now_close, 0.1), 3)
            #下單
            bin_client.futures_create_order(symbol=symbol,positionSide='SHORT',side = 'SELL',type='MARKET',quantity=short_quantity,leverage=100) #precision=3
            #止盈
            bin_client.futures_create_order(symbol=symbol,positionSide='SHORT',side='BUY',type ='TAKE_PROFIT_MARKET',quantity = short_quantity,
                                            stopPrice=round(float(lower_x2_bond),2),workingType='MARK_PRICE')#precision=3
            #止損
            bin_client.futures_create_order(symbol=symbol,positionSide='SHORT',side='BUY',type ='STOP_MARKET',quantity = short_quantity,
                                            stopPrice=round(float(Cross_5MA_10MA),2),workingType='MARK_PRICE')#precision=3
            notified_for_entry30_short = True  # 設定為已通知
            print("放空")


    if notified_for_entry30_long == True :
        if (now_high >=upper_x2_bond) | (now_close <= Cross_5MA_10MA):
            found_rsi_below_30,notified_for_rsi30,notified_for_ma_cross30,notified_for_entry30_long,notified_for_entry30_short = False,False,False,False,False
            if (now_high >=upper_x2_bond):
                data = requests.post(url, headers=headers, data={'message':f'目前價格:{now_close},達到做多停損點:{Cross_5MA_10MA}'})
            elif (now_close <= Cross_5MA_10MA):
                data = requests.post(url, headers=headers, data={'message':f'目前價格:{now_close},達到做多停利點:{upper_x2_bond}'})
            # 遍歷所有未執行訂單，尋找放空的止損/止盈訂單並取消它們
            while True:
                Long_have_position , Short_have_position = check_position(bin_client)
                if Long_have_position == False:
                    open_orders = bin_client.futures_get_open_orders(symbol=symbol)
                    for order in open_orders:
                        if order['positionSide'] == 'LONG' and (order['type'] == 'STOP_MARKET' or order['type'] == 'TAKE_PROFIT_MARKET'):
                            result = bin_client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                    break
                time.sleep(1)
    elif notified_for_entry30_short == True :
        if (now_high >=Cross_5MA_10MA) | (now_close <= lower_x2_bond):
            found_rsi_below_30,notified_for_rsi30,notified_for_ma_cross30,notified_for_entry30_long,notified_for_entry30_short = False,False,False,False,False
            if (now_high >=Cross_5MA_10MA):
                data = requests.post(url, headers=headers, data={'message':f'目前價格:{now_close},達到放空停損點:{Cross_5MA_10MA}'})
            elif (now_close <= lower_x2_bond):
                data = requests.post(url, headers=headers, data={'message':f'目前價格:{now_close},達到放空停利點:{lower_x2_bond}'})
            # 遍歷所有未執行訂單，尋找放空的止損/止盈訂單並取消它們
            while True:
                Long_have_position , Short_have_position = check_position(bin_client)
                if Short_have_position == False:
                    open_orders = bin_client.futures_get_open_orders(symbol=symbol)
                    for order in open_orders:
                        if order['positionSide'] == 'SHORT' and (order['type'] == 'STOP_MARKET' or order['type'] == 'TAKE_PROFIT_MARKET'):
                            result = bin_client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                    break
                time.sleep(1)
    
    time.sleep(5)

    nowtimestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) 
    print(f"時間: {nowtimestamp}")
    print(found_rsi_below_30,notified_for_rsi30,notified_for_ma_cross30,notified_for_entry30_long,notified_for_entry30_short)
    print(Long_have_position , Short_have_position)
    print(f"| now_open:       {now_open:>10.2f} | now_close:        {now_close:>10.2f} | high30:{high30:>17.2f} | low30:{low30:>17.2f} |")
    print(f"| second_last_5MA:{second_last_5MA:>10.2f} | second_last_10MA: {second_last_10MA:>10.2f} | second_last_rsi: {second_last_rsi:>7.2f} |")
    print(f"| now_5MA: {now_5MA:>17.2f} | now_10MA:  {now_10MA:>17.2f} | Now_rsi:      {now_rsi:>10.2f} |")

    time.sleep(50)


