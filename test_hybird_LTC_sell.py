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
#往上滑ctrl+b + [ 
#ubuntu@ip-172-31-14-207:~$ git config --global user.email evan6007@gmail.com
#ubuntu@ip-172-31-14-207:~$ git config --global user.name evan6007

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
exit_premium = -0.004  # 當溢價 = -0.3% 時平倉
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
        spot_usdt = next(item for item in client.get_account()['balances'] if item['asset'] == 'USDT')['free']
        futures_usdt = next(item for item in client.futures_account_balance() if item['asset'] == 'USDT')['balance']
        return float(spot_usdt), float(futures_usdt)
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

def adjust_price(symbol, price):
    tick_size = symbol_filters[symbol]['tickSize']
    return float((Decimal(price) // tick_size) * tick_size)

def adjust_quantity(symbol, quantity):
    step_size = symbol_filters[symbol]['stepSize']
    min_qty = symbol_filters[symbol]['minQty']
    quantity = (Decimal(quantity) // step_size) * step_size
    return float(max(quantity, min_qty))



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
    spot_price_new = mid * (1.00325)  # 現貨下降 原始28 還沒更新
    future_price_new = mid * (1.00025)  # 合約上升  98
    
    # 確保價格符合 Binance 交易規則
    spot_price_new = adjust_price(f"{asset}USDT", spot_price_new)
    future_price_new = adjust_price(f"{asset}USDT", future_price_new)


    return spot_price_new, future_price_new


def calculate_entry_prices(asset,spot_price, future_price,premium,target_premium):
    """計算讓溢價從 -0.4% 回到 -0.3% 的新的現貨與合約價格"""
    # x = (1 + target_premium) / (1 - premium) - 1
    
    # spot_price_new = spot_price * (1 - x)  # 現貨下降
    # future_price_new = future_price * (1 + x)  # 合約上升
    mid = (future_price+spot_price)/2
    spot_price_new = mid*0.9990
    future_price_new = mid*0.9990
    
    # 確保價格符合 Binance 交易規則
    spot_price_new = adjust_price(f"{asset}USDT", spot_price_new)
    future_price_new = adjust_price(f"{asset}USDT", future_price_new)


    return spot_price_new, future_price_new


exchange_info = client.get_exchange_info()
symbol_info = {item['symbol']: item for item in exchange_info['symbols']}
symbol_filters = {}
for symbol, info in symbol_info.items():
    price_filter = next(f for f in info['filters'] if f['filterType'] == 'PRICE_FILTER')
    lot_size_filter = next(f for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
    symbol_filters[symbol] = {
        'tickSize': Decimal(price_filter['tickSize']),
        'stepSize': Decimal(lot_size_filter['stepSize']),
        'minQty': Decimal(lot_size_filter['minQty'])
    }




# **主交易邏輯**
while True:
    # 取得最新價格
    spot_price, future_price = fetch_prices()
    premium = (future_price - spot_price) / spot_price  # 計算溢價
    print(f"📊 準備建倉 溢價: {premium:.2%}")



    # **當溢價 > 0.1% 時，建立套利倉位**
    if 0.0005 <= premium <= 0.0012:
        print(f"✅ 溢價 {premium:.2%}，執行套利！")


        try:
            # **設定 LTC 合約槓桿 (1x)**
            client.futures_change_leverage(symbol="LTCUSDT", leverage=1)

            # 取得 USDT 餘額
            account_info = client.get_account()
            usdt_balance = float(next(item for item in account_info['balances'] if item['asset'] == 'USDT')['free'])

            # 計算新的現貨與合約平倉價格
            spot_price_new, future_price_new = calculate_entry_prices(asset,spot_price, future_price,premium,0) #用-0.3%價格去平倉

            # 計算交易數量
            quantity = calculate_quantity(usdt_balance, spot_price_new)
            quantity = adjust_quantity(f"{asset}USDT", quantity)

            # **下合約做空單**
            order_futures = client.futures_create_order(
                symbol=f"{asset}USDT",
                side="SELL",
                type="LIMIT",
                quantity=quantity,
                price=future_price_new,
                timeInForce="GTC",
                positionSide="SHORT"
            )
            future_order_id = order_futures["orderId"]

            # **下現貨買入單**
            order_spot = client.order_limit_buy(
                symbol=f"{asset}USDT",
                quantity=quantity,
                price=spot_price_new,
                timeInForce="GTC"
            )
            spot_order_id = order_spot["orderId"]



            print(f"🔄 建立套利倉位，交易數量: {quantity}")
            # **發送 LINE 通知**                
            send_line_message(f"✅ 溢價 {premium:.2%}，建立套利倉位！\n"
                              f"🔄 建立套利倉位，交易數量: {quantity}\n"
                              f"LTC 現貨溢價價格: {spot_price}\n"
                              f"LTC 期貨溢價價格: {future_price}"
                              f"LTC 現貨限單: {spot_price_new}\n"
                              f"LTC 期貨限單: {future_price_new}\n")


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
                print(f"📊 準備平倉 監控溢價: {premium:.2%}")


                # **當溢價 = -0.42%~-0.32% 時，執行平倉**
                if -0.0042 <= premium <= -0.0034:


                    # 計算新的現貨與合約平倉價格
                    spot_price_new, future_price_new = calculate_exit_prices(asset,spot_price, future_price,premium,-0.003) #用-0.3%價格去平倉
                    
                    # **期貨平倉**
                    order_futures = client.futures_create_order(
                        symbol=f"{asset}USDT",
                        side="BUY",
                        type="LIMIT",
                        quantity=quantity,
                        price=future_price_new,
                        timeInForce="GTC",
                        positionSide="SHORT"
                    )
                    future_order_id = order_futures["orderId"]

                    # **現貨賣出**
                    order_spot = client.order_limit_sell(
                        symbol=f"{asset}USDT",
                        quantity=quantity,
                        price=spot_price_new,
                        timeInForce="GTC"
                    )
                    spot_order_id = order_spot["orderId"]


                    # **發送 LINE 通知**
                    send_line_message(f"🎯 溢價 {premium:.2%}，執行套利平倉\n"
                    f"LTC 原始現貨限單: {spot_price}\n"
                    f"LTC 原始期貨限單: {future_price}\n"
                    f"LTC 現貨限單: {spot_price_new}\n"
                    f"LTC 期貨限單: {future_price_new}\n")


                    # **等待訂單成交**
                    close_spot_average_price,close_future_average_price =wait_for_orders(f"{asset}USDT", spot_order_id, f"{asset}USDT", future_order_id)


                    print("✅ 套利交易完成！")

                    # 查詢現貨BNB餘額
                    account_info = client.get_account()
                    spot_bnb = float(next(item for item in account_info['balances'] if item['asset'] == 'BNB')['free'])
                    # 查詢合約BNB餘額
                    futures_info = client.futures_account_balance()
                    futures_bnb = float(next(item for item in futures_info if item['asset'] == 'BNB')['balance'])
                    # 查詢目前BNB/USDT價格
                    bnb_usdt_price = float(client.get_symbol_ticker(symbol="BNBUSDT")["price"])
                    # 換算成USDT
                    spot_bnb_usdt = spot_bnb * bnb_usdt_price
                    futures_bnb_usdt = futures_bnb * bnb_usdt_price
                    total_bnb_usdt = spot_bnb_usdt+futures_bnb_usdt
                    print(f"現貨BNB餘額：{spot_bnb_usdt:.2f} USDT")
                    print(f"合約BNB餘額：{futures_bnb_usdt:.2f} USDT")
                    print(f"總共BNB餘額：{total_bnb_usdt:.2f} USDT")



                    # 計算總 USDT 餘額
                    usdt_balance, futures_usdt_balance = fetch_balances()

                    #總usdt
                    total_usdt_balance = usdt_balance + futures_usdt_balance + total_bnb_usdt 
                    # 計算報酬率
                    initial_capital = 211.75  # 初始資本 200 USDT
                    profit_percentage = ((total_usdt_balance - initial_capital) / initial_capital) * 100
                    spot_profit = (close_spot_average_price - open_spot_average_price)/open_spot_average_price
                    future_profit = (open_future_average_price - close_future_average_price)/open_future_average_price
                    now_profit = (spot_profit+future_profit)


                    # 發送 LINE 訊息，新增「總計 USDT 餘額」
                    send_line_message(f"✅ 套利完成！溢價 {now_profit:.2%}，套利完成！\n"
                                    f"📈LTC 現貨賣出價: {close_spot_average_price}\n"
                                    f"📉LTC 期貨回補價: {close_future_average_price}\n"
                                    f"🔢交易數量: {quantity}\n"
                                    f"💰 現貨 USDT 餘額: {usdt_balance:.2f}\n"
                                    f"💰 合約 USDT 餘額: {futures_usdt_balance:.2f}\n"
                                    f"💎 現貨 BNB 餘額: {spot_bnb_usdt:.2f} USDT\n"
                                    f"💎 合約 BNB 餘額: {futures_bnb_usdt:.2f} USDT\n"
                                    f"💎 BNB 總價值: {total_bnb_usdt:.2f} USDT\n"
                                    f"💰 **總計 USDT 餘額: {total_usdt_balance:.2f}**\n"
                                    f"📈 **本次報酬: {now_profit:.2%}**\n"
                                    f"📊  **總報酬: {profit_percentage:.2f}%**")
                    break

                # time.sleep(0.5)  # 每 2 秒檢查一次
        except BinanceAPIException as e:
            print(f"❌ 下單失敗: {e}")
            send_line_message(f"❌ 下單失敗: {e}")
        except Exception as e:
            print(f"❌ 未知錯誤: {e}")
            send_line_message(f"❌ 未知錯誤: {traceback.format_exc()}")
    # time.sleep(0.5)  # 每 2 秒檢查一次