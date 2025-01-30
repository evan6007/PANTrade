import pandas as pd
from binance.client import Client
import time
from datetime import datetime, timedelta
import traceback
import requests
import threading
import math

# Initialize Binance API
api_key = "Wo34893AHGp4kCEkRYrzCDjNz17wyU4Qb4kDJMOZ8T7GwvjqPqqJiTNXuPsP9GJ4"
api_secret = "1k4yEPjzc23bByV3PQsFslzDBdUjyMeoqgvdY9Rd9ZI0v2klFxTBdvLxNRJ2VqRi"
client = Client(api_key, api_secret)

# Define the thresholds for opening and closing positions
open_threshold = 0.3  # Open position when premium exceeds 0.3%
close_threshold = 0.00  # Close position when premium is below 0.05%
spot_fee_rate = 0.2  # Fee rate per side (e.g., 0.1%)
future_fee_rate = 0.07  # Fee rate per side (e.g., 0.07%)

# Initialize variables
positions = []
current_position = None

#line
url = 'https://notify-api.line.me/api/notify'
token = '0RxE9s8aOfLBoPOnGwiA3MQxEQBt2rZcpxaRRgvZmPh'
headers = {'Authorization': 'Bearer ' + token} # 設定權杖

symbols = ["DOGE", "XRP", "ADA", "LTC", "ETH", "BNB"] #, "BTC", "SOL"
#只搜尋一次交易精度
# lot_size_dict = {s['symbol']: float(next(f for f in s['filters'] if f['filterType'] == 'LOT_SIZE')['stepSize']) for s in exchange_info['symbols']}

# 📌 只取前一根收盤價的價格獲取函數
# def fetch_prices():
#     spot_prices = {}
#     future_prices = {}
#     try:
#         # Fetch spot prices
#         for symbol in symbols:
#             klines = client.get_klines(symbol=f"{symbol}USDT", interval="1m", limit=2)
#             spot_prices[symbol] = float(klines[-2][4])  # Last close price from previous minute

#         # Fetch futures prices
#         for symbol in symbols:
#             klines = client.futures_klines(symbol=f"{symbol}USDT", interval="1m", limit=2)
#             future_prices[symbol] = float(klines[-2][4])  # Last close price from previous minute
#     except Exception as e:
#         print(f"Error fetching prices: {e}")
#         traceback.print_exc()
#     return spot_prices, future_prices

# 📌 優化後的價格獲取函數
def fetch_prices():
    try:
        spot_prices = {s: float(client.get_symbol_ticker(symbol=f"{s}USDT")["price"]) for s in symbols}
        future_prices = {s: float(client.futures_symbol_ticker(symbol=f"{s}USDT")["price"]) for s in symbols}
        return spot_prices, future_prices
    except Exception as e:
        send_line_message("錯誤", None, error_msg=f"價格獲取失敗: {str(e)}")
        return None, None

# Function to calculate the quantity based on available balance
def calculate_quantity(balance, price, percentage):
    # Use a percentage of the balance to calculate quantity
    allocation = balance * percentage
    quantity = allocation / price
    return round(quantity, 6)  # Binance supports up to 6 decimal places for quantity

# Ensure we are reading data exactly at the correct timestamp
def wait_for_next_minute():
    now = datetime.now()
    next_minute = (now + timedelta(minutes=1)).replace(second=2, microsecond=0) #延遲整點兩秒後抓
    sleep_time = (next_minute - now).total_seconds()
    time.sleep(0.1)

def adjust_quantity(symbol, quantity):
    # 獲取交易對的規範信息
    exchange_info = client.get_exchange_info()
    for market in exchange_info['symbols']:
        if market['symbol'] == symbol:
            # 查找 LOT_SIZE 過濾器
            lot_size = next(
                (f for f in market['filters'] if f['filterType'] == 'LOT_SIZE'), 
                None
            )
            if lot_size is None:
                raise ValueError(f"未找到 {symbol} 的 LOT_SIZE 規範")

            # 獲取最小數量和精度
            min_qty = float(lot_size['minQty'])  # 最小下單量
            step_size = float(lot_size['stepSize'])  # 精度限制

            # 確保數量大於最小數量，並符合精度要求
            if quantity < min_qty:
                raise ValueError(f"數量 {quantity} 小於最小交易量 {min_qty}")
            adjusted_quantity = round(quantity - (quantity % step_size), 8)
            return adjusted_quantity

    # 如果未找到該交易對，拋出異常
    raise ValueError(f"無法獲取交易對 {symbol} 的規範信息")

# 📌 交易數量調整 (只在啟動時查詢一次 `exchange_info`)
# def adjust_quantity(symbol, quantity):
#     step_size = lot_size_dict.get(symbol, 0.01)  # 預設步進值
#     return round(quantity - (quantity % step_size), 8)

def send_line_message(message_type, asset, premium=None, quantity=None, spot_price=None, future_price=None, error_msg=None):
    if message_type == "開倉":
        message = f"📢 **開倉通知** 📢\n"
        message += f"🔹 幣種: {asset}\n"
        message += f"🔹 溢價: {premium:.3f}%\n"
        message += f"🔹 數量: {quantity}\n"
        message += f"🔹 現貨價格: {spot_price}\n"
        message += f"🔹 期貨價格: {future_price}\n"
    elif message_type == "平倉":
        message = f"✅ **平倉通知** ✅\n"
        message += f"🔹 幣種: {asset}\n"
        message += f"🔹 溢價: {premium:.3f}%\n"
        message += f"🔹 數量: {quantity}\n"
        message += f"🔹 現貨價格: {spot_price}\n"
        message += f"🔹 期貨價格: {future_price}\n"
    elif message_type == "錯誤":
        message = f"⚠️ **錯誤通知** ⚠️\n"
        message += f"🔹 錯誤內容: {error_msg}\n"
    else:
        return
    # 使用 Threading 非同步發送，確保不影響交易
    threading.Thread(target=requests.post, args=(url,), kwargs={'headers': headers, 'data': {'message': message}}).start()

# Simulate the trading strategy in real-time
while True:

    try:
        # Wait until the start of the next minute
        wait_for_next_minute()

        # Fetch account balance (example for USDT)
        account_info = client.get_account()
        usdt_balance = float(next(item for item in account_info['balances'] if item['asset'] == 'USDT')['free'])
        # Fetch futures account balance
        futures_account_info = client.futures_account_balance()
        futures_usdt_balance = float(next(item for item in futures_account_info if item['asset'] == 'USDT')['balance'])
        

        spot_prices, future_prices = fetch_prices()
        # Fetch current spot and futures prices
        if spot_prices is None or future_prices is None:
            continue  # 如果抓取失敗，跳過本次循環

        # Combine data for all assets
        combined_data = []
        for symbol in symbols:
            asset_data = {
                'asset': symbol,
                'spot_price': spot_prices[symbol],
                'future_price': future_prices[symbol],
            }
            asset_data['premium'] = (asset_data['future_price'] - asset_data['spot_price']) / asset_data['spot_price'] * 100
            combined_data.append(asset_data)

        print("usdt_balance=",usdt_balance)
        print("futures_usdt_balance=", futures_usdt_balance)
        
        for row in combined_data:
            premium = row['premium']
            spot_price = row['spot_price']
            future_price = row['future_price']
            asset = row['asset']

            print("asset=",asset,"premium=",premium,"spot_price=",spot_price,"future_price=",future_price)


            if current_position is None:
                # Open position if premium exceeds open_threshold
                if abs(premium) > open_threshold:
                    send_line_message("開倉", asset, premium, 0, spot_price, future_price)
                if premium > open_threshold:  #------------原本abs(premium)--------------------
                    quantity = calculate_quantity(usdt_balance, spot_price, 0.9)  # Use 90% of available balance
                    print("調整前quantity=",quantity)
                    quantity = adjust_quantity(f"{asset}USDT", quantity)  # 調整幣對應的小數精度
                    print("調整後quantity=",quantity)
                    fee_percentage = 0.001  # 手續費比例（0.1%）
                    asset_price = float(client.get_symbol_ticker(symbol=f"{asset}USDT")['price'])  # 獲取當前 XRP 價格
                    usdt_to_spend = quantity / (1 - fee_percentage) * asset_price # 計算所需支付的 USDT 金額
                    print("調整後usdt_to_spend=",usdt_to_spend)
                    # Place orders on Binance (No leverage)
                    if premium > 0:
                        # Spot long, Futures short
                        send_line_message("開倉", asset, premium, quantity, spot_price, future_price)
                        client.order_market_buy(symbol=f"{asset}USDT", quoteOrderQty=round(usdt_to_spend, 2))
                        # client.futures_create_order(symbol=f"{asset}USDT", side="SELL", type="MARKET", quantity=quantity)
                        client.futures_create_order(symbol=f"{asset}USDT",
                                                    side="SELL",
                                                    type="MARKET",
                                                    quantity=quantity,
                                                    positionSide="SHORT"  # 指定為做空
                                                )
                    #     # Spot short, Futures long
                    #     client.order_market_sell(symbol=f"{asset}USDT", quoteOrderQty=quantity)
                    #     client.futures_create_order(symbol=f"{asset}USDT", side="BUY", type="MARKET", quantity=quantity)

                    current_position = {
                        'asset': asset,
                        'entry_premium': premium,
                        'entry_spot_price': spot_price,
                        'entry_future_price': future_price,
                        'direction': 'positive' if premium > 0 else 'negative',
                        'quantity': quantity,
                    }

            elif current_position['asset'] == asset:
                # Close position if premium is below close_threshold
                if (current_position['direction'] == 'positive' and premium < close_threshold) or \
                (current_position['direction'] == 'negative' and premium > -close_threshold):
                    quantity = current_position['quantity']
                    send_line_message("平倉", asset, premium, quantity, spot_price, future_price)

                    # Place close orders on Binance
                    if current_position['direction'] == 'positive':
                        # Close Spot long, Futures short
                        client.order_market_sell(symbol=f"{asset}USDT", quantity=quantity)
                        # client.futures_create_order(symbol=f"{asset}USDT", side="BUY", type="MARKET", quantity=quantity)
                        # 平空倉 (做空平倉)
                        client.futures_create_order(
                            symbol=f"{asset}USDT",
                            side="BUY",
                            type="MARKET",
                            quantity=quantity,
                            positionSide="SHORT"  # 指定平空倉
                        )

                    else:
                        # Close Spot short, Futures long
                        client.order_market_buy(symbol=f"{asset}USDT", quantity=quantity)
                        client.futures_create_order(symbol=f"{asset}USDT", side="SELL", type="MARKET", quantity=quantity)

                    current_position = None
    except Exception as e:
        print("Error in main loop:", e)
        traceback.print_exc()
        send_line_message("錯誤", None, error_msg=f"交易錯誤: {str(e)}")
        time.sleep(5)  # 延遲後重試
