import json
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BUY_SYMBOLS_FILE = "./symbols_buy_check.json"
SELL_SYMBOLS_FILE = "./symbols_sell_check.json"
SYMBOLS_TEST_FILE = "./symbols_test.json"
IS_TEST_RUN = False
SEND_TELEGRAM_MESSAGE = True
PROCESS_SELL_SIGNALS = True


def load_symbols() -> list[str]:
    """Load stock symbols from JSON file"""
    try:
        path = SYMBOLS_TEST_FILE if IS_TEST_RUN else BUY_SYMBOLS_FILE

        with open(path, "r") as f:
            data = json.load(f)
            symbols_str = data.get("symbols", "")
            # Split by comma and clean up whitespace/symbols
            symbols = set([s.strip() for s in symbols_str.split(",") if s.strip()])
            return list(sorted(symbols))
    except Exception as e:
        print(f"Error loading symbols: {e}")
        return []


async def send_telegram_message(message: str) -> bool | None:
    """Send message to Telegram channel using bot API"""
    try:
        if not SEND_TELEGRAM_MESSAGE:
            print("SEND_TELEGRAM_MESSAGE is False - Skipping Telegram message...")
            return None

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"Telegram message sent successfully: {result.get('ok')}")
                    return True
                else:
                    error_text = await response.text()
                    print(
                        f"Failed to send Telegram message. Status: {response.status}, Error: {error_text}"
                    )
                    return False
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False


def load_portfolio_symbols() -> list[str]:
    """Load portfolio symbols from JSON file"""
    try:
        path = SYMBOLS_TEST_FILE if IS_TEST_RUN else SELL_SYMBOLS_FILE

        with open(path, "r") as f:
            data = json.load(f)
            symbols_str = data.get("symbols", "")
            symbols = set([s.strip() for s in symbols_str.split(",") if s.strip()])
            return list(sorted(symbols))
    except Exception as e:
        print(f"Error loading portfolio symbols: {e}")
        return []
