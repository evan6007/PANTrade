import pandas as pd
from binance.client import Client
import time
from datetime import datetime, timedelta
import traceback
import requests
import math
from binance.exceptions import BinanceAPIException
from decimal import Decimal, ROUND_DOWN

#source myenv/bin/activate
#deactivate
#tmux attach -t 0


#line
line_url = 'https://notify-api.line.me/api/notify'
line_token = '0RxE9s8aOfLBoPOnGwiA3MQxEQBt2rZcpxaRRgvZmPh'
headers = {'Authorization': 'Bearer ' + line_token} # 設定權杖

# Initialize Binance API
api_key = "Wo34893AHGp4kCEkRYrzCDjNz17wyU4Qb4kDJMOZ8T7GwvjqPqqJiTNXuPsP9GJ4"
api_secret = "1k4yEPjzc23bByV3PQsFslzDBdUjyMeoqgvdY9Rd9ZI0v2klFxTBdvLxNRJ2VqRi"
client = Client(api_key, api_secret)


# 設定交易參數
asset = "LTC"
entry_premium = 0.0  # 當溢價 = 0% 時進場
exit_premium = -0.003  # 當溢價 = -0.3% 時平倉
spot_fee = 0.001  # 現貨手續費 0.1%

# 發送 LINE 訊息
def send_line_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {'message': f"[{timestamp}]\n{message}"}

    requests.post(line_url, headers=headers, data=payload)

# 取得最新價格（增加重試機制）
def fetch_prices():
    retries = 0
    while retries < 5:
        try:
            spot_price = float(client.get_symbol_ticker(symbol=f"{asset}USDT")["price"])
            future_price = float(client.futures_symbol_ticker(symbol=f"{asset}USDT")["price"])
            return spot_price, future_price
        except BinanceAPIException as e:
            print(f"❌ API 請求錯誤: {e}")
        except Exception as e:
            print(f"❌ 取得價格時發生錯誤: {e}")
        
        retries += 1
        time.sleep(5)

    send_line_message("❌ 無法取得最新價格，請手動檢查！")
    return None, None

# 取得現貨 & 期貨 USDT 餘額
def fetch_balances():
    try:
        account_info = client.get_account()
        usdt_balance = float(next(item for item in account_info['balances'] if item['asset'] == 'USDT')['free'])

        futures_account_info = client.futures_account_balance()
        futures_usdt_balance = float(next(item for item in futures_account_info if item['asset'] == 'USDT')['balance'])

        return usdt_balance, futures_usdt_balance
    except BinanceAPIException as e:
        print(f"❌ 餘額查詢失敗: {e}")
        send_line_message("⚠️ Binance API 連線錯誤，無法查詢餘額")
    except Exception as e:
        print(f"❌ 取得餘額時發生錯誤: {e}")
        send_line_message(f"⚠️ 取得餘額失敗: {e}")
    
    return None, None

# 計算交易數量
def calculate_quantity(balance, price):
    allocation = balance * 0.9  # 90% 的 USDT 餘額
    quantity = allocation / price * (1 - spot_fee)  # 扣除手續費
    return round(quantity, 6)  # Binance 支持最多 6 位小數

# **調整價格以符合 Binance 交易規則**
def adjust_price(symbol, price):
    exchange_info = client.get_exchange_info()
    for market in exchange_info['symbols']:
        if market['symbol'] == symbol:
            price_filter = next((f for f in market['filters'] if f['filterType'] == 'PRICE_FILTER'), None)
            if price_filter:
                tick_size = Decimal(price_filter['tickSize'])
                adjusted_price = (Decimal(price) // tick_size) * tick_size  # 向下取整符合 tickSize
                return float(adjusted_price.quantize(tick_size, rounding=ROUND_DOWN))
    # 先發送 LINE 通知，再拋出錯誤
    error_message = f"⚠️ 無法獲取 {symbol} adjust_price"
    send_line_message(error_message)
    raise ValueError(error_message)

# 調整交易數量以符合 Binance 交易規則
def adjust_quantity(symbol, quantity):
    exchange_info = client.get_exchange_info()
    for market in exchange_info['symbols']:
        if market['symbol'] == symbol:
            lot_size = next((f for f in market['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            if lot_size:
                min_qty = Decimal(lot_size['minQty'])
                step_size = Decimal(lot_size['stepSize'])
                adjusted_quantity = (Decimal(quantity) // step_size) * step_size  # 向下取整符合 stepSize
                return float(max(adjusted_quantity, min_qty).quantize(step_size, rounding=ROUND_DOWN))

    # 先發送 LINE 通知，再拋出錯誤
    error_message = f"⚠️ 無法獲取 {symbol} adjust_quantity"
    send_line_message(error_message)
    raise ValueError(error_message)

# **等待訂單成交（無限重試 + API 連線錯誤處理）**
def wait_for_orders(spot_symbol, spot_order_id, futures_symbol, futures_order_id):
    while True:
        try:
            # 查詢訂單狀態
            spot_order_status = client.get_order(symbol=spot_symbol, orderId=spot_order_id)["status"]
            future_order_status = client.futures_get_order(symbol=futures_symbol, orderId=futures_order_id)["status"]

            print(f"📊 訂單狀態 - 現貨: {spot_order_status}, 合約: {future_order_status}")

            # 如果現貨 & 合約都成交，就返回
            if spot_order_status == "FILLED" and future_order_status == "FILLED":
                # 算成交均價
                spot_order_details = client.get_order(symbol=f"{asset}USDT", orderId=spot_order_id)
                spot_cummulative_quote_qty = float(spot_order_details['cummulativeQuoteQty'])
                spot_executed_qty = float(spot_order_details['executedQty'])
                spot_average_price = spot_cummulative_quote_qty / spot_executed_qty

                future_order_status = client.futures_get_order(symbol=f"{asset}USDT", orderId=future_order_id)
                future_average_price = float(future_order_status['avgPrice'])

                print("✅ 現貨與合約訂單已成交")
                return spot_average_price,future_average_price

        except BinanceAPIException as e:
            print(f"❌ API 連線錯誤，將重試: {e}")
            send_line_message("⚠️ Binance API 連線錯誤，請手動檢查訂單狀態！")
        except Exception as e:
            print(f"❌ 其他錯誤: {e}")
            send_line_message(f"⚠️ 發生未知錯誤: {e}")

        # 每次等待 2 秒再試
        time.sleep(2)


def calculate_exit_prices(asset,spot_price, future_price,premium,target_premium):
    """計算讓溢價從 -0.4% 回到 -0.3% 的新的現貨與合約價格"""
    # x = (1 + target_premium) / (1 - premium) - 1
    
    # spot_price_new = spot_price * (1 - x)  # 現貨下降
    # future_price_new = future_price * (1 + x)  # 合約上升
    mid = (future_price+spot_price)/2
    spot_price_new = mid * (1.0015)  # 現貨下降
    future_price_new = mid * (0.9985)  # 合約上升
    
    # 確保價格符合 Binance 交易規則
    spot_price_new = adjust_price(f"{asset}USDT", spot_price_new)
    future_price_new = adjust_price(f"{asset}USDT", future_price_new)


    return spot_price_new, future_price_new

# **主交易邏輯**
while True:
    # 取得最新價格
    spot_price, future_price = fetch_prices()
    premium = (future_price - spot_price) / spot_price  # 計算溢價
    print(f"📊 目前溢價: {premium:.2%}")



    # **當溢價 > 0.1% 時，建立套利倉位**
    if premium >= 0.0:
        print(f"✅ 溢價 {premium:.2%}，執行套利！")


        try:
            # **設定 LTC 合約槓桿 (1x)**
            client.futures_change_leverage(symbol="LTCUSDT", leverage=1)

            # 取得 USDT 餘額
            account_info = client.get_account()
            usdt_balance = float(next(item for item in account_info['balances'] if item['asset'] == 'USDT')['free'])

            # **計算開倉價格**
            # entry_price = (spot_price + future_price) / 2
            # entry_price = adjust_price(f"{asset}USDT", entry_price)  # 確保價格符合 Binance 規則
            #暫時用spot_price當entry
            entry_price = spot_price


            # 計算交易數量
            quantity = calculate_quantity(usdt_balance, entry_price)
            quantity = adjust_quantity(f"{asset}USDT", quantity)

            print(f"🔄 建立套利倉位，交易數量: {quantity}")
            # **發送 LINE 通知**                
            send_line_message(f"✅ 溢價 {premium:.2%}，建立套利倉位！\n"
                              f"🔄 建立套利倉位，交易數量: {quantity}\n"
                              f"LTC 現貨溢價價格: {spot_price}\n"
                              f"LTC 期貨溢價價格: {future_price}")

            # **下現貨買入單**
            order_spot = client.order_market_buy(
                symbol=f"{asset}USDT",
                quantity=quantity,
            )
            spot_order_id = order_spot["orderId"]

            # **下合約做空單**
            order_futures = client.futures_create_order(
                symbol=f"{asset}USDT",
                side="SELL",
                type="MARKET",
                quantity=quantity,
                positionSide="SHORT"
            )
            future_order_id = order_futures["orderId"]

            # **等待訂單成交**
            open_spot_average_price,open_future_average_price =wait_for_orders(f"{asset}USDT", spot_order_id, f"{asset}USDT", future_order_id)
            print("✅ 套利倉位建立完成，等待平倉機會...")

            # **發送 LINE 訊息**
            open_premium = (open_future_average_price - open_spot_average_price)/open_spot_average_price
            send_line_message(f"✅ 成功建立套利倉位，溢價 {open_premium:.2%}\n"
                            f"LTC 現貨成交價: {open_spot_average_price:.6f}\n"
                            f"LTC 期貨成交價: {open_future_average_price:.6f}\n"
                            f"交易數量: {quantity}")

            #開始找平倉機會
            while True:
                spot_price, future_price = fetch_prices()
                premium = (future_price - spot_price) / spot_price
                print(f"📊 監控溢價: {premium:.2%}")


                # **當溢價 = -0.3%~-0.4% 時，執行平倉**
                if -0.004 <= premium <= -0.003:
                    send_line_message(f"🎯 溢價 {premium:.2%}")

                # **當溢價 = -0.4% 時，執行平倉**
                if premium <= exit_premium:
                    print(f"🎯 溢價 {premium:.2%}，執行套利平倉！")

                    # **發送 LINE 通知**
                    send_line_message(f"🎯 溢價 {premium:.2%}，執行套利平倉\n"
                    f"LTC 現貨溢價價格: {spot_price}\n"
                    f"LTC 期貨溢價價格: {future_price}\n")

                    # **現貨賣出**
                    order_spot = client.order_market_sell(
                        symbol=f"{asset}USDT",
                        quantity=quantity,
                    )
                    spot_order_id = order_spot["orderId"]

                    # **期貨平倉**
                    # **期貨平倉（改為市價單）**
                    order_futures = client.futures_create_order(
                        symbol=f"{asset}USDT",
                        side="BUY",
                        type="MARKET",
                        quantity=quantity,
                        positionSide="SHORT"
                    )
                    future_order_id = order_futures["orderId"]

                    # **等待訂單成交**
                    close_spot_average_price,close_future_average_price =wait_for_orders(f"{asset}USDT", spot_order_id, f"{asset}USDT", future_order_id)


                    print("✅ 套利交易完成！")

                    # **發送 LINE 訊息**
                    send_line_message(f"✅ 套利完成！\n"
                                    f"LTC 現貨成交價: {close_spot_average_price:.6f}\n"
                                    f"LTC 期貨成交價: {close_future_average_price:.6f}\n"
                                    f"交易數量: {quantity}")


                    # **發送 LINE 通知**
                    usdt_balance, futures_usdt_balance = fetch_balances()
                    # 計算總 USDT 餘額
                    total_usdt_balance = usdt_balance + futures_usdt_balance
                    # 計算報酬率
                    initial_capital = 200  # 初始資本 200 USDT
                    profit_percentage = ((total_usdt_balance - initial_capital) / initial_capital) * 100
                    spot_profit = (close_spot_average_price - open_spot_average_price)/open_spot_average_price
                    future_profit = (open_future_average_price - close_future_average_price)/open_future_average_price
                    now_profit = (spot_profit+future_profit)*100
                    # 發送 LINE 訊息，新增「總計 USDT 餘額」
                    send_line_message(f"✅ 套利完成！\n"
                                    f"📈LTC 現貨賣出價: {close_spot_average_price}\n"
                                    f"📉LTC 期貨回補價: {close_future_average_price}\n"
                                    f"🔢交易數量: {quantity}\n"
                                    f"💰 現貨 USDT 餘額: {usdt_balance:.2f}\n"
                                    f"💰 合約 USDT 餘額: {futures_usdt_balance:.2f}\n"
                                    f"💰 **總計 USDT 餘額: {total_usdt_balance:.2f}**\n"
                                    f"📈 **本次報酬: {now_profit:.2f}%**\n"
                                    f"📊  **總報酬: {profit_percentage:.2f}%**")
                    break

                time.sleep(0.5)  # 每 2 秒檢查一次
        except BinanceAPIException as e:
            print(f"❌ 下單失敗: {e}")
            send_line_message(f"❌ 下單失敗: {e}")
        except Exception as e:
            print(f"❌ 未知錯誤: {e}")
            send_line_message(f"❌ 未知錯誤: {traceback.format_exc()}")
    time.sleep(0.5)  # 每 2 秒檢查一次