"""
bybit_api.py — Общие функции для получения данных с Bybit API.

Использование:
    from src.bybit_api import fetch_option_chain, fetch_spot_price
"""

import requests

BYBIT_API = "https://api.bybit.com/v5/market/tickers"


def fetch_option_chain(base_coin: str) -> list:
    """Загружает полный опционный чейн для base_coin (например, SOL)."""
    params = {"category": "option", "baseCoin": base_coin}
    r = requests.get(BYBIT_API, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()

    if not data.get("result") or not isinstance(data["result"].get("list"), list):
        raise RuntimeError("Unexpected API response structure")

    return data["result"]["list"]


def fetch_spot_price(base_coin: str) -> float:
    """Загружает текущую цену спота для {base_coin}USDT."""
    try:
        params = {"category": "spot"}
        r = requests.get(BYBIT_API, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        symbol = f"{base_coin}USDT"
        for ticker in data.get("result", {}).get("list", []):
            if ticker.get("symbol") == symbol:
                return float(ticker.get("lastPrice", 0))
    except Exception:
        pass
    return 0.0
