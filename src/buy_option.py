#!/usr/bin/env python3
"""
T007 — Покупка опциона.

Загружает option chain с Bybit, выбирает опцион по параметрам,
записывает в options_registry.csv и options_tracking.csv с Greeks.

Использование:
  python src/buy_option.py --strike 70 --expiry 2026-07-25 --qty 1 --layer active
  python src/buy_option.py --symbol "SOL-25JUL25-70-P-USDT"  # явный символ
  python src/buy_option.py --auto  # автоподбор по config.toml
"""

import os
import sys
import csv
import math
import json
from datetime import datetime, date
from pathlib import Path

# Add project to path
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import toml

# ============================================================
# CONFIG
# ============================================================
CONFIG_PATH = PROJECT_DIR / "config.toml"
REGISTRY_PATH = PROJECT_DIR / "data" / "options_registry.csv"
TRACKING_PATH = PROJECT_DIR / "data" / "options_tracking.csv"
PORTFOLIO_PATH = PROJECT_DIR / "data" / "open_positions.csv"

REGISTRY_FIELDS = [
    "id", "symbol", "type", "strike", "expiry", "qty",
    "entry_date", "entry_price", "total_cost",
    "iv_entry", "iv_atm_entry", "delta_entry", "gamma_entry",
    "theta_entry", "vega_entry", "layer", "status", "notes"
]

TRACKING_FIELDS = [
    "symbol", "current_price", "pnl", "delta", "gamma", "theta",
    "vega", "dte", "iv", "iv_atm", "intrinsic_value", "layer", "updated"
]


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
    """Получить полный option chain с Bybit."""
    try:
        conn = http.client.HTTPSConnection(BYBIT_HOST, timeout=15)
        conn.request("GET", f"/v5/options/usdc/query?category=option&symbol={coin}USDC&limit=200")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        if data["retCode"] != 0:
            print(f"  ❌ Bybit chain error: {data.get('retMsg')}")
            return []

        chain = []
        for item in data["result"]["list"]:
            # Только PUT опционы
            if item.get("optionsType", {}).get("optionType") != "P":
                continue
            try:
                strike = float(item["strike"])
                expiry = item["settleTime"]  # ms since epoch
                expiry_dt = datetime.fromtimestamp(expiry / 1000)
                expiry_str = expiry_dt.strftime("%Y-%m-%d")
                dte = (expiry_dt - datetime.now()).days
                delta = float(item.get("delta", 0))
                gamma = float(item.get("gamma", 0))
                theta = float(item.get("theta", 0))
                vega = float(item.get("vega", 0))
                iv = float(item.get("impliedVolatility", 0))
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
            except (ValueError, KeyError) as e:
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
    with open(CONFIG_PATH) as f:
        return toml.load(f)


def load_portfolio() -> list:
    """Загрузить open_positions.csv."""
    if not PORTFOLIO_PATH.exists():
        return []
    with open(PORTFOLIO_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ============================================================
# FILE WRITING
# ============================================================
def next_registry_id() -> int:
    """Следующий ID в registry."""
    if not REGISTRY_PATH.exists():
        return 1
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ids = [int(r.get("id", 0)) for r in reader]
        return max(ids) + 1 if ids else 1


def write_registry(row: dict):
    """Записать в options_registry.csv."""
    exists = REGISTRY_PATH.exists()
    with open(REGISTRY_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        if exists:
            # Дописываем к существующим
            with open(REGISTRY_PATH, "r", encoding="utf-8") as rf:
                for r in csv.DictReader(rf):
                    writer.writerow(r)
        writer.writerow(row)


def write_tracking(row: dict):
    """Записать в options_tracking.csv."""
    exists = TRACKING_PATH.exists()
    with open(TRACKING_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKING_FIELDS)
        writer.writeheader()
        if exists:
            with open(TRACKING_PATH, "r", encoding="utf-8") as rf:
                for r in csv.DictReader(rf):
                    writer.writerow(r)
        writer.writerow(row)


# ============================================================
# BUY LOGIC
# ============================================================
def buy_option(args: dict) -> bool:
    """Купить опцион."""
    print("=" * 60)
    print("📊 ПОКУПКА ОПЦИОНА")
    print("=" * 60)

    # 1. Загрузка данных
    print("\n[1/5] Загрузка данных...")
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
    print("\n[2/5] Поиск опциона...")
    symbol = args.get("symbol")
    strike = args.get("strike")
    expiry = args.get("expiry")

    opt = find_option(chain, symbol=symbol, strike=strike, expiry=expiry)
    if not opt:
        print("  ⚠️ Опцион не найден, показываем доступные:")
        print(f"  {'Символ':<40} {'Strike':>7} {'DTE':>5} {'IV':>6} {'Price':>7}")
        print("  " + "-" * 67)
        for o in sorted(chain, key=lambda x: x["dte"]):
            if o["dte"] > 0:
                print(f"  {o['symbol']:<40} ${o['strike']:>6.0f} {o['dte']:>5d} {o['iv']:>6.2%} ${o['mark_price']:>6.2f}")
        return False
    print(f"  ✅ {opt['symbol']}")
    print(f"     Strike: ${opt['strike']} | DTE: {opt['dte']} | IV: {opt['iv']:.2%} | Price: ${opt['mark_price']:.2f}")

    # 3. Загрузка config
    print("\n[3/5] Конфигурация...")
    config = load_config()
    portfolio = load_portfolio()

    avg_price = spot
    for p in portfolio:
        if p["symbol"].upper() == "SOL":
            avg_price = float(p.get("avg_price", spot))
            break

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

    # 4. Запись в registry
    print("\n[4/5] Запись в registry...")
    new_id = next_registry_id()
    entry_date = date.today().strftime("%Y-%m-%d")
    expiry_dt = datetime.strptime(opt["expiry"], "%Y-%m-%d")
    expiry_ms = int(expiry_dt.timestamp() * 1000)

    reg_row = {
        "id": str(new_id),
        "symbol": opt["symbol"],
        "type": "PUT",
        "strike": str(opt["strike"]),
        "expiry": opt["expiry"],
        "qty": str(qty),
        "entry_date": entry_date,
        "entry_price": f"{entry_price:.4f}",
        "total_cost": f"{total_cost:.2f}",
        "iv_entry": f"{opt['iv']:.4f}",
        "iv_atm_entry": f"{opt['iv']:.4f}",  # Placeholder, updated by monitor
        "delta_entry": f"{opt['delta']:.4f}",
        "gamma_entry": f"{opt['gamma']:.4f}",
        "theta_entry": f"{opt['theta']:.4f}",
        "vega_entry": f"{opt['vega']:.4f}",
        "layer": layer,
        "status": "open",
        "notes": f"Auto-buy {entry_date}",
    }
    write_registry(reg_row)
    print(f"  ✅ Registry: ID={new_id}")

    # 5. Запись в tracking
    print("\n[5/5] Запись в tracking...")
    tracking_row = {
        "symbol": opt["symbol"],
        "current_price": f"{entry_price:.4f}",
        "pnl": "0.00",
        "delta": f"{opt['delta']:.4f}",
        "gamma": f"{opt['gamma']:.4f}",
        "theta": f"{opt['theta']:.4f}",
        "vega": f"{opt['vega']:.4f}",
        "dte": str(opt["dte"]),
        "iv": f"{opt['iv']:.4f}",
        "iv_atm": f"{opt['iv']:.4f}",
        "intrinsic_value": f"{intrinsic:.4f}",
        "layer": layer,
        "updated": entry_date,
    }
    write_tracking(tracking_row)
    print(f"  ✅ Tracking updated")

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
