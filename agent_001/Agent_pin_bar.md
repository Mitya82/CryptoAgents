def check_pinbar_buy_signal(previous_candle, trend_direction='uptrend'):
    """
    Проверяет, является ли предыдущая свеча сигнальной для покупки по правилу 'пин-бар в тренде'.
    
    Args:
        previous_candle (list): Данные предыдущей свечи [timestamp, open, high, low, close, volume].
        trend_direction (str): Направление тренда ('uptrend', 'downtrend', 'sideways').
        
    Returns:
        bool: True если сигнал на покупку, иначе False.
    """
    # 1. Распаковываем данные свечи
    open_price = previous_candle[1]
    high_price = previous_candle[2]
    low_price = previous_candle[3]
    close_price = previous_candle[4]
    
    # 2. Проверяем общий контекст: мы в растущем тренде?
    if trend_direction != 'uptrend':
        return False  # Сигнал актуален только для аптренда
    
    # 3. Проверяем, что свеча МЕДВЕЖЬЯ (красная): закрытие ниже открытия
    is_bearish = close_price < open_price
    if not is_bearish:
        return False
    
    # 4. Вычисляем тело свечи и тени
    body_size = abs(close_price - open_price)
    lower_shadow = min(open_price, close_price) - low_price  # Нижняя тень
    upper_shadow = high_price - max(open_price, close_price) # Верхняя тень (нам не нужна тут)
    
    # 5. Главное условие: нижняя тень >= половине тела свечи
    if lower_shadow >= (body_size / 2):
        # 6. (ОПЦИОНАЛЬНО) Можно добавить фильтр: тело свечи не должно быть слишком большим
        # if body_size < (high_price - low_price) * 0.7:  # Тело меньше 70% от общего диапазона
        print(f"[СИГНАЛ] Найден пин-бар для покупки. Тело: {body_size:.5f}, Нижняя тень: {lower_shadow:.5f}")
        return True
    
    return False

# --- Пример использования в основном цикле агента ---
# Предположим, 'candles' - это массив последних свечей, а 'current_trend' мы определили ранее
if check_pinbar_buy_signal(candles[-2], trend_direction=current_trend):  # Проверяем ПРЕДЫДУЩУЮ свечу
    print(">>> ВЫСТАВЛЯЕМ ОРДЕР НА ПОКУПКУ!")
    # Здесь будет вызов функции exchange.create_order(...)