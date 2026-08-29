import ccxt
import pandas as pd
import time
import requests
import threading

# Telegram Credentials
TELEGRAM_TOKEN = "8899462957:AAGULs4zyHqM1UbwDjml5_BT0i5pBRJrgXk"
TELEGRAM_CHAT_ID = "6532128071"

exchange = ccxt.binance()

# Paper Trading Settings
balance_usdt = 1000.0  
btc_held = 0.0         
buy_price = 0.0        

# Risk Limits
STOP_LOSS_PCT = 0.02
TAKE_PROFIT_PCT = 0.04

last_offset = 0

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def calculate_rsi(data, window=14):
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def fetch_data(symbol='BTC/USDT', timeframe='1h', limit=300):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['MA50'] = df['close'].rolling(window=50).mean()
    df['MA200'] = df['close'].rolling(window=200).mean()
    df['RSI'] = calculate_rsi(df, window=14)
    return df

def analyze_and_trade():
    global balance_usdt, btc_held, buy_price
    
    df = fetch_data()
    
    last_close = df['close'].iloc[-1]
    ma50 = df['MA50'].iloc[-1]
    ma200 = df['MA200'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    
    prev_ma50 = df['MA50'].iloc[-2]
    prev_ma200 = df['MA200'].iloc[-2]

    print("--------------------------------------------------")
    print(f"Current Price: ${last_close:.2f} | RSI: {rsi:.2f}")
    print(f"MA50: ${ma50:.2f} | MA200: ${ma200:.2f}")
    print(f"💰 Balance: ${balance_usdt:.2f} USDT | BTC: {btc_held:.4f}")

    if btc_held > 0:
        price_change = (last_close - buy_price) / buy_price
        
        if price_change <= -STOP_LOSS_PCT:
            balance_usdt = btc_held * last_close
            msg = f"🛑 *STOP-LOSS TRIGGERED!*\nSold BTC at ${last_close:.2f}\nBalance: ${balance_usdt:.2f} USDT"
            print(msg)
            send_telegram_message(msg)
            btc_held = 0.0
            buy_price = 0.0
            return

        elif price_change >= TAKE_PROFIT_PCT:
            balance_usdt = btc_held * last_close
            msg = f"🎯 *TAKE-PROFIT TRIGGERED!*\nSold BTC at ${last_close:.2f}\nBalance: ${balance_usdt:.2f} USDT"
            print(msg)
            send_telegram_message(msg)
            btc_held = 0.0
            buy_price = 0.0
            return

    if prev_ma50 < prev_ma200 and ma50 > ma200:
        if rsi < 70:
            print("🚀 SIGNAL: BUY (Golden Cross + RSI OK)")
            if balance_usdt > 0:
                btc_held = balance_usdt / last_close
                buy_price = last_close
                balance_usdt = 0.0
                msg = f"🚀 *BUY SIGNAL DETECTED!*\nBought {btc_held:.4f} BTC at ${last_close:.2f}\nRSI: {rsi:.2f}"
                print(msg)
                send_telegram_message(msg)
        else:
            print("⚠️ Golden Cross detected BUT Market is Overbought (RSI > 70). Skipping Buy.")
            
    elif prev_ma50 > prev_ma200 and ma50 < ma200:
        print("🔻 SIGNAL: SELL (Death Cross detected!)")
        if btc_held > 0:
            balance_usdt = btc_held * last_close
            msg = f"🔻 *SELL SIGNAL DETECTED!*\nSold BTC for ${balance_usdt:.2f} USDT"
            print(msg)
            send_telegram_message(msg)
            btc_held = 0.0
            buy_price = 0.0
    else:
        print("⏳ SIGNAL: HOLD (No crossover)")

# Safe Telegram Command Listener (Handles non-text messages without crash)
def check_telegram_commands():
    global last_offset
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_offset + 1}&timeout=5"
    try:
        response = requests.get(url).json()
        if "result" in response:
            for update in response["result"]:
                last_offset = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]
                    if text == "/status":
                        df = fetch_data()
                        last_close = df['close'].iloc[-1]
                        rsi = df['RSI'].iloc[-1]
                        ma50 = df['MA50'].iloc[-1]
                        ma200 = df['MA200'].iloc[-1]
                        
                        status_msg = (
                            f"📊 *BOT LIVE STATUS*\n\n"
                            f"💵 *BTC Price:* ${last_close:.2f}\n"
                            f"📈 *RSI (14):* {rsi:.2f}\n"
                            f"📉 *MA50:* ${ma50:.2f}\n"
                            f"📉 *MA200:* ${ma200:.2f}\n\n"
                            f"💰 *USDT Balance:* ${balance_usdt:.2f}\n"
                            f"🪙 *BTC Balance:* {btc_held:.4f}\n"
                            f"🎯 *Buy Price:* ${buy_price:.2f}"
                        )
                        send_telegram_message(status_msg)
    except Exception as e:
        print(f"Error handling Telegram command: {e}")

def run_bot():
    start_msg = "🤖 *Trading Bot Online & Listening for Commands!* Send /status"
    print(start_msg)
    send_telegram_message(start_msg)
    
    while True:
        try:
            analyze_and_trade()
        except Exception as e:
            print(f"Error in trading loop: {e}")
        time.sleep(10)

def run_telegram_listener():
    while True:
        check_telegram_commands()
        time.sleep(2)

# Run trading loop and Telegram listener simultaneously
t1 = threading.Thread(target=run_bot)
t2 = threading.Thread(target=run_telegram_listener)

t1.start()
t2.start()