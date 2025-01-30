import pandas as pd
from binance.client import Client
import time
from datetime import datetime, timedelta
import traceback
import requests
import math


# Initialize Binance API
api_key = "Wo34893AHGp4kCEkRYrzCDjNz17wyU4Qb4kDJMOZ8T7GwvjqPqqJiTNXuPsP9GJ4"
api_secret = "1k4yEPjzc23bByV3PQsFslzDBdUjyMeoqgvdY9Rd9ZI0v2klFxTBdvLxNRJ2VqRi"
client = Client(api_key, api_secret)
symbols = ["DOGE", "XRP", "ADA", "LTC", "ETH", "BNB"] #, "BTC", "SOL"


def fetch_prices():

    spot_prices = {s: float(client.get_symbol_ticker(symbol=f"{s}USDT")["price"]) for s in symbols}
    future_prices = {s: float(client.futures_symbol_ticker(symbol=f"{s}USDT")["price"]) for s in symbols}
    return spot_prices, future_prices

# Function to calculate the quantity based on available balance
def calculate_quantity(balance, price, percentage):
    # Use a percentage of the balance to calculate quantity
    allocation = balance * percentage
    quantity = allocation / price * (1 - 0.001)
    return round(quantity, 6)  # Binance supports up to 6 decimal places for quantity


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


account_info = client.get_account()
usdt_balance = float(next(item for item in account_info['balances'] if item['asset'] == 'USDT')['free'])
spot_prices, future_prices = fetch_prices()
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

for row in combined_data:
    premium = row['premium']
    spot_price = row['spot_price']
    future_price = row['future_price']
    asset = row['asset']

    if asset == "XRP":
        quantity = calculate_quantity(usdt_balance, spot_price, 0.9)  # Use 90% of available balance
        print("調整前quantity=",quantity)
        quantity = adjust_quantity(f"{asset}USDT", quantity)  # 調整幣對應的小數精度
        print("調整後quantity=",quantity)
        
        # Place orders on Binance (No leverage)
        order_spot = client.order_limit_buy(
            symbol=f"{asset}USDT",
            quantity=quantity,
            price=spot_price,
            timeInForce="GTC"  # Good-Till-Cancel
        )
        order_futures = client.futures_create_order(
                            symbol=f"{asset}USDT",
                            side="SELL",
                            type="LIMIT",
                            quantity=quantity,
                            price=future_price,
                            timeInForce="GTC",
                            positionSide="SHORT"
                        )
# **2️⃣ 等待成交**
time.sleep(1)
while True:
    spot_order_status = client.get_order(symbol="XRPUSDT", orderId=order_spot["orderId"])["status"]
    future_order_status = client.futures_get_order(symbol="XRPUSDT", orderId=order_futures["orderId"])["status"]

    if spot_order_status == "FILLED" and future_order_status == "FILLED":
        print("✅ 現貨與合約訂單已成交，可以進行平倉")
        break  # 只有成交後才繼續平倉

    print(f"📊 訂單狀態 - 現貨: {spot_order_status}, 合約: {future_order_status}")
    time.sleep(2)


spot_prices, future_prices = fetch_prices()
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

for row in combined_data:
    premium = row['premium']
    spot_price = row['spot_price']
    future_price = row['future_price']
    asset = row['asset']

    if asset == "XRP":

        # Close Spot long, Futures short
        order_spot = client.order_limit_sell(
                symbol=f"{asset}USDT",
                quantity=quantity,
                price=spot_price,
                timeInForce="GTC"
            )
        # client.futures_create_order(symbol=f"{asset}USDT", side="BUY", type="MARKET", quantity=quantity)
        # 平空倉 (做空平倉)
        order_futures = client.futures_create_order(
            symbol=f"{asset}USDT",
            side="BUY",
            type="LIMIT",
            quantity=quantity,
            price=future_price,
            timeInForce="GTC",
            positionSide="SHORT"
        )
        print("平倉")

while True:
    spot_order_status = client.get_order(symbol="XRPUSDT", orderId=order_spot["orderId"])["status"]
    future_order_status = client.futures_get_order(symbol="XRPUSDT", orderId=order_futures["orderId"])["status"]

    print(f"📊 訂單狀態 - 現貨: {spot_order_status}, 合約: {future_order_status}")
    if spot_order_status == "FILLED" and future_order_status == "FILLED":
        print("✅ 現貨與合約訂單已成交")
        break  # 只有成交後才繼續平倉

    time.sleep(2)
