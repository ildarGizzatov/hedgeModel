#!/usr/bin/env python3
"""
buy_option.py — Покупка Put-опциона с записью в БД.

Заменяет CSV-запись: options_registry.csv → options (БД),
                    options_tracking.csv → option_greeks_history (БД)

Использование:
  python src/buy_option.py --strike 70 --expiry 2026-07-25 --qty 1 --layer active
  python src/buy_option.py --symbol "SOL-25JUL25-70-P-USDT"  # явный символ
  python src/buy_option.py --auto  # автоподбор по config.toml
"""

import os
import sys
import math
import json
from datetime import datetime, date
from pathlib import Path

# Add project to path
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import tomllib

# ============================================================
# DB IMPORT
# ============================================================
from src.db import get_portfolio_position, add_option, record_greeks, get_connection

# ============================================================
# CONFIG
# ============================================================
CONFIG_PATH = PROJECT_DIR / "config.toml"

# ============================================================
# BYBIT API
# ============================================================
import http.client
from urllib.parse import urlencode

BYBIT_HOST = "api.bybit.com"


def fetch_spot_price(symbol: str = "SOLUSDT") -> float:
    """Получить текущую цену спота."""
    try:
        conn = http.client.HTTPSConnection(BYBIT_HOST, timeout=15)
        conn.request("GET", f"/v5/market/tickers?category=spot&symbol={symbol}")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        if data["retCode"] == 0:
            return float(data["result"]["list"][0]["lastPrice"])
        print(f"  ❌ Bybit spot error: {data.get('retMsg')}")
        return 0
    except Exception as e:
        print(f"  ❌ Spot fetch failed: {e}")
        return 0


def fetch_option_chain(coin: str = "SOL") -> list:
    """Получить полный option chain с Bybit (через tickers API)."""
    import requests
    url = "https://api.bybit.com/v5/market/tickers"
    try:
        params = {"category": "option", "baseCoin": coin}
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()

        chain = []
        for item in data.get("result", {}).get("list", []):
            # Только PUT опционы — по символу
            if not item.get("symbol", "").endswith("-P-USDT"):
                continue
            try:
                # Strike и expiry извлекаются из символа (SOL-DDMONYY-STRIKE-P-USDT)
                sym = item.get("symbol", "")
                parts = sym.split("-")
                strike = float(parts[2])
                # Парсим дату из символа (10JUL26 → 2026-07-10)
                date_part = parts[1]
                expiry_dt = datetime.strptime(date_part, "%d%b%y")
                expiry_str = expiry_dt.strftime("%Y-%m-%d")
                dte = (expiry_dt - datetime.now()).days
                delta = float(item.get("delta", 0))
                gamma = float(item.get("gamma", 0))
                theta = float(item.get("theta", 0))
                vega = float(item.get("vega", 0))
                iv = float(item.get("markIv", 0))
                mark_price = float(item.get("markPrice", 0))
                last_price = float(item.get("lastPrice", 0))
                price = last_price if last_price > 0 else mark_price

                chain.append({
                    "symbol": item["symbol"],
                    "type": "PUT",
                    "strike": strike,
                    "expiry": expiry_str,
                    "dte": dte,
                    "delta": delta,
                    "gamma": gamma,
                    "theta": theta,
                    "vega": vega,
                    "iv": iv,
                    "mark_price": price,
                })
            except (ValueError, KeyError):
                continue
        return chain
    except Exception as e:
        print(f"  ❌ Chain fetch failed: {e}")
        return []


def find_option(chain: list, symbol: str = None, strike: float = None, expiry: str = None) -> dict:
    """Найти опцион по символу или параметрам."""
    for o in chain:
        if symbol and o["symbol"] == symbol:
            return o
        if strike and o["strike"] == strike:
            if expiry is None or o["expiry"] == expiry:
                return o
    return None


def calc_intrinsic(strike: float, option_type: str, spot: float) -> float:
    """Внутренняя стоимость."""
    if option_type == "PUT":
        return max(strike - spot, 0)
    return max(spot - strike, 0)


# ============================================================
# CONFIG LOADING
# ============================================================
def load_config() -> dict:
    """Загрузить config.toml."""
    if not CONFIG_PATH.exists():
        print(f"  ❌ Config not found: {CONFIG_PATH}")
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def load_portfolio_avg_price() -> float:
    """Загрузить avg_price из БД (позиция SOL)."""
    pos = get_portfolio_position("SOL")
    if pos:
        return float(pos["avg_price"])
    return None


# ============================================================
# BUY LOGIC
# ============================================================
def buy_option(args: dict) -> bool:
    """Купить опцион."""
    print("=" * 60)
    print("📊 ПОКУПКА ОПЦИОНА")
    print("=" * 60)

    # 1. Загрузка данных
    print("\n[1/4] Загрузка данных...")
    spot = fetch_spot_price("SOLUSDT")
    if spot <= 0:
        print("  ❌ Не удалось получить цену спота")
        return False
    print(f"  SOL: ${spot:.2f}")

    chain = fetch_option_chain("SOL")
    if not chain:
        print("  ❌ Не удалось получить option chain")
        return False
    print(f"  PUT-опционов: {len(chain)}")

    # 2. Поиск опциона
    print("\n[2/4] Поиск опциона...")
    symbol = args.get("symbol")
    strike = args.get("strike")
    expiry = args.get("expiry")

    opt = find_option(chain, symbol=symbol, strike=strike, expiry=expiry)
    if opt:
        print(f"  ✅ {opt['symbol']}")
        print(f"     Strike: ${opt['strike']} | DTE: {opt['dte']} | IV: {opt['iv']:.2%} | Price: ${opt['mark_price']:.2f}")
    else:
        print("  ⚠️ Опцион не найден, показываем доступные:")
        print(f"  {'Символ':<40} {'Strike':>7} {'DTE':>5} {'IV':>6} {'Price':>7}")
        print("  " + "-" * 67)
        for o in sorted(chain, key=lambda x: x["dte"]):
            if o["dte"] > 0:
                print(f"  {o['symbol']:<40} ${o['strike']:>6.0f} {o['dte']:>5d} {o['iv']:>6.2%} ${o['mark_price']:>6.2f}")
        return False

    # 3. Загрузка config
    print("\n[3/4] Конфигурация...")
    config = load_config()
    layer = args.get("layer", "active")
    qty = args.get("qty", 1)
    entry_price = opt["mark_price"]
    total_cost = entry_price * qty
    intrinsic = calc_intrinsic(opt["strike"], "PUT", spot)

    print(f"  Layer: {layer}")
    print(f"  Qty: {qty}")
    print(f"  Entry Price: ${entry_price:.4f}")
    print(f"  Total Cost: ${total_cost:.2f}")
    print(f"  Intrinsic: ${intrinsic:.4f}")

    # 4. Запись в БД
    print("\n[4/4] Запись в БД...")

    # 4a. Записать в options (реестр)
    new_id = add_option(
        symbol=opt["symbol"],
        opt_type="PUT",
        strike=opt["strike"],
        expiry=opt["expiry"],
        qty=qty,
        layer=layer,
        entry_date=date.today().isoformat(),
        entry_price=entry_price,
        iv_entry=opt["iv"],
        iv_atm_entry=opt["iv"],
        delta_entry=opt["delta"],
        gamma_entry=opt["gamma"],
        theta_entry=opt["theta"],
        vega_entry=opt["vega"],
        notes=f"Auto-buy {date.today().isoformat()}",
    )
    print(f"  ✅ options: ID={new_id}")

    # 4b. Записать в option_greeks_history (первый снимок)
    record_greeks(
        option_id=new_id,
        option_symbol=opt["symbol"],
        current_price=entry_price,
        delta=opt["delta"],
        gamma=opt["gamma"],
        theta=opt["theta"],
        vega=opt["vega"],
        iv=opt["iv"],
        iv_atm=opt["iv"],
        dte=opt["dte"],
        intrinsic_value=intrinsic,
        unrealized_pnl=0.0,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    print(f"  ✅ greeks_history: snapshot #1")

    # Итог
    print("\n" + "=" * 60)
    print("✅ ПОКУПКА ЗАВЕРШЕНА")
    print("=" * 60)
    print(f"  Опцион: {opt['symbol']}")
    print(f"  Strike: ${opt['strike']} | DTE: {opt['dte']}")
    print(f"  Qty: {qty} | Cost: ${total_cost:.2f}")
    print(f"  Greeks: Δ={opt['delta']:.4f} Γ={opt['gamma']:.4f} Θ={opt['theta']:.4f} V={opt['vega']:.4f}")
    print("=" * 60)

    return True


# ============================================================
# CLI
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Buy option")
    parser.add_argument("--symbol", help="Full symbol (e.g. SOL-25JUL25-70-P-USDT)")
    parser.add_argument("--strike", type=float, help="Strike price")
    parser.add_argument("--expiry", help="Expiry date (YYYY-MM-DD)")
    parser.add_argument("--qty", type=int, default=1, help="Quantity")
    parser.add_argument("--layer", default="active", choices=["anchor", "adaptation", "active"])
    parser.add_argument("--auto", action="store_true", help="Auto-select best option from chain")

    args = parser.parse_args()

    if args.auto:
        # Auto mode: select cheapest OTM PUT with DTE > 30
        spot = fetch_spot_price("SOLUSDT")
        chain = fetch_option_chain("SOL")
        if not chain:
            print("❌ No chain available")
            sys.exit(1)

        puts = [o for o in chain if o["dte"] > 30 and o["mark_price"] > 0]
        if not puts:
            print("❌ No suitable options")
            sys.exit(1)

        # Best value: highest ratio of (intrinsic / price) for downside protection
        best = max(puts, key=lambda o: o["mark_price"])  # Cheapest with good DTE
        args.symbol = best["symbol"]

    ok = buy_option(vars(args))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
