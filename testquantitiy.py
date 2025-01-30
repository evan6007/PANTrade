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

# 設定轉帳金額
transfer_amount = 50  # 你想轉 100 USDT

# 1.轉移 USDT 從「現貨帳戶」到「Margin 帳戶」
client.transfer_spot_to_margin(asset='USDT', amount=transfer_amount)
print(f"✅ 成功轉移 {transfer_amount} USDT 到 Margin 帳戶")
time.sleep(1)

#2. 借幣
borrow_amount = 10  # 想要借入的 XRP 數量
client.create_margin_loan(asset='XRP', amount=borrow_amount)
print(f"已借入 {borrow_amount} XRP")

#3.執行賣出訂單 
current_price = float(client.get_symbol_ticker(symbol='XRPUSDT')['price'])# 取得當前價格
usdt_to_receive = borrow_amount * current_price #計算要賣出的 USDT 數量
print(f"放空 {borrow_amount} XRP，預計可獲得 {usdt_to_receive:.2f} USDT")
order = client.create_margin_order(
    symbol='XRPUSDT',
    side='SELL',
    type='MARKET',
    quantity=borrow_amount
)
print("現貨放空訂單已下單")

#4.買回
time.sleep(2)
# 取得當前價格
xrp_price = float(client.get_symbol_ticker(symbol='XRPUSDT')['price'])
# 設定 Binance 交易手續費率（現貨默認為 0.1%）
fee_rate = 0.001  # 0.1% = 0.001
# 計算要花費的 USDT 總量（確保扣除手續費後能買回足夠的 XRP）
buy_size = borrow_amount*(1+fee_rate)
usdt_to_spend = buy_size * xrp_price
usdt_to_spend = math.floor(usdt_to_spend * 100) / 100  # Binance 允許 2 位小數
order = client.create_margin_order(
    symbol='XRPUSDT',
    side='BUY',
    type='MARKET',
    quoteOrderQty=usdt_to_spend
)
print(f"成功買回{buy_size} XRP")

#margin還砍
time.sleep(2)
margin_account_info = client.get_margin_account()
# 取得 XRP 餘額
xrp_balance = 0
for asset_info in margin_account_info['userAssets']:
    if asset_info['asset'] == 'XRP':
        xrp_balance = float(asset_info['free'])  # 真正可用的 XRP
        break

print(f"🔍 真正可用的 XRP 數量: {xrp_balance}")
if xrp_balance > 0:
    client.repay_margin_loan(asset='XRP', amount=xrp_balance)
    print(f"✅ 成功歸還 {xrp_balance:.6f} XRP")
else:
    print("⚠️ 沒有足夠的 XRP 進行還款")

#把錢從margin轉回去現貨
time.sleep(2)
max_transferable_usdt = math.floor(float(client.get_max_margin_transfer(asset='USDT')['amount'])*100)/100# 取得 USDT 的可用餘額
print(max_transferable_usdt)
client.transfer_margin_to_spot(asset='USDT', amount =max_transferable_usdt) # **Margin → 現貨**
print(f"✅ 成功轉回 {max_transferable_usdt} USDT 到現貨帳戶")
