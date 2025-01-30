

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


def calculate_quantity(balance, price, percentage):
    # Use a percentage of the balance to calculate quantity
    allocation = balance * percentage
    quantity = allocation / price
    return round(quantity, 6)  # Binance supports up to 6 decimal places for quantity
