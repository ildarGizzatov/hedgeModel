"""
chain_fetcher.py — Fetch + парсинг + фильтрация чейна.

Единая функция для загрузки опционного чейна из Bybit.
Возвращает список отфильтрованных опционов для БД.

Использование:
    from src.chain_fetcher import fetch_and_filter_chain
    rows = fetch_and_filter_chain("SOL")
"""

from src.bybit_api import fetch_option_chain, fetch_spot_price
from src.chain_parser import parse_option, calc_dte


def fetch_and_filter_chain(base_coin: str = "SOL") -> tuple[list[dict], float]:
    """
    Загружает чейн, фильтрует, возвращает данные для БД.

    Фильтры:
      - DTE > 3
      - PUT: delta ∈ [-0.70, -0.01]
      - CALL: delta ∈ [0.01, 0.70]

    Returns:
        (rows, spot_price) — список dicts + цена спота
    """
    chain = fetch_option_chain(base_coin)
    spot_price = fetch_spot_price(base_coin)
    print(f"   Загружено тикеров: {len(chain)}")
    print(f"   Spot {base_coin}: ${spot_price:.2f}")

    rows = []
    for opt in chain:
        parsed = parse_option(opt)
        if not parsed:
            continue
        dte = calc_dte(parsed["expiry_str"])
        if dte <= 3:
            continue
        delta = parsed["delta"]
        if parsed["type"] == "PUT":
            if delta >= -0.01 or delta < -0.70:
                continue
        else:
            if delta <= 0.01 or delta > 0.70:
                continue
        rows.append({
            "symbol": parsed["symbol"],
            "strike": parsed["strike"],
            "expiry": parsed["expiry_str"],
            "delta": delta,
            "gamma": parsed["gamma"],
            "vega": parsed["vega"],
            "theta": parsed["theta"],
            "mark_price": parsed["mark_price"],
            "iv": parsed["iv"],
            "dte": dte,
            "type": parsed["type"],
            "open_interest": opt.get("openInterest"),
        })

    return rows, spot_price
