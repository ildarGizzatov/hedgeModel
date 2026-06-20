"""
chain_parser.py — Парсинг данных опционов из Bybit API.

Единая точка парсинга: Bybit ticker dict → parsed dict.

Использование:
    from src.chain_parser import parse_option
    parsed = parse_option(ticker)
"""

from datetime import datetime


def parse_option(ticker: dict) -> dict | None:
    """
    Парсит один Bybit ticker в структуру опциона.

    Args:
        ticker: dict из Bybit API (delta, markPrice, markIv...)

    Returns:
        dict с полями: symbol, expiry_str, strike, type,
        delta, gamma, theta, vega, mark_price, iv, underlying_price
        или None если не опцион.
    """
    symbol = ticker.get("symbol", "")
    if "-P-" not in symbol and "-C-" not in symbol:
        return None

    try:
        parts = symbol.split("-")
        date_str = parts[1]
        expiry = datetime.strptime(date_str, "%d%b%y")
        expiry_str = expiry.strftime("%Y-%m-%d")
        strike = float(parts[2])
        opt_type = "PUT" if "-P-" in symbol else "CALL"

        return {
            "symbol": symbol,
            "expiry_str": expiry_str,
            "strike": strike,
            "type": opt_type,
            "delta": float(ticker.get("delta") or 0),
            "gamma": float(ticker.get("gamma") or 0),
            "theta": float(ticker.get("theta") or 0),
            "vega": float(ticker.get("vega") or 0),
            "mark_price": float(ticker.get("markPrice") or 0),
            "last_price": float(ticker.get("lastPrice") or 0),
            "iv": float(ticker.get("markIv") or 0),
            "underlying_price": float(ticker.get("underlyingPrice") or 0),
        }
    except Exception:
        return None


def calc_dte(expiry_str: str) -> int:
    """Дней до экспирации."""
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    delta = expiry - datetime.now().date()
    return max(delta.days, 0)


def calc_intrinsic(strike: float, option_type: str, spot: float) -> float:
    """Внутренняя стоимость опциона."""
    if option_type == "PUT":
        return max(strike - spot, 0)
    return max(spot - strike, 0)
