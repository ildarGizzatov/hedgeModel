"""
OptionBoard.py — Загрузка опционного чейна с Bybit → Excel.

Использование:
    python src/OptionBoard.py
"""

import pandas as pd
from datetime import datetime, timezone
import os
import sys
from pathlib import Path

# Add project to path
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from src.bybit_api import fetch_option_chain, fetch_spot_price

# Путь к файлу относительно корня проекта.
EXCEL_OUT = "excel/sol_options_chain.xlsx"

BASE_COIN = "SOL"
SHEET_NAME = "OptionBoard"


def parse_option_data(option_list, spot_price):
    """Парсит данные Bybit в структуру для Excel."""
    rows = []
    now_utc = datetime.now(timezone.utc)

    for opt in option_list:
        symbol = opt.get("symbol", "")
        if "-P-" not in symbol and "-C-" not in symbol:
            continue

        try:
            parts = symbol.split("-")
            date_str = parts[1]
            expiry = datetime.strptime(date_str, "%d%b%y").replace(tzinfo=timezone.utc)
            dte = max((expiry - now_utc).days, 0)
        except:
            continue

        if dte <= 3:
            continue

        delta = float(opt.get("delta") or 0)
        theta = float(opt.get("theta") or 0)
        gamma = float(opt.get("gamma") or 0)
        vega = float(opt.get("vega") or 0)
        mark_price = float(opt.get("markPrice") or 0)
        iv = float(opt.get("markIv") or 0)
        open_interest = opt.get("openInterest")

        if "-P-" in symbol:
            if delta >= -0.01 or delta < -0.70:
                continue
            opt_type = "PUT"
        elif "-C-" in symbol:
            if delta <= 0.01 or delta > 0.70:
                continue
            opt_type = "CALL"
        else:
            continue

        hedge_cost_per_day = mark_price / dte if dte != 0 else 0
        T = dte / 365

        rows.append({
            "symbol": symbol,
            "strike": float(parts[2]),
            "delta": delta,
            "gamma": gamma,
            "vega": vega,
            "theta": theta,
            "mark_price": mark_price,
            "iv": iv,
            "dte": dte,
            "T": T,
            "type": opt_type,
            "spot_price": spot_price,
            "hedge_cost_per_day": hedge_cost_per_day,
            "open_interest": open_interest
        })

    return rows


def save_to_excel(rows, filename):
    """Записывает данные в Excel."""
    df = pd.DataFrame(rows)
    if not df.empty:
       df["type_order"] = df["type"].map({"PUT": 0, "CALL": 1})
       df = df.sort_values(by=["dte", "type_order", "strike"])
       df = df.drop(columns=["type_order"])

    target_path = os.path.abspath(filename)

    if os.path.exists(target_path):
        with pd.ExcelWriter(target_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=SHEET_NAME, index=False)
    else:
        with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=SHEET_NAME, index=False)

    print(f"Option board saved to '{SHEET_NAME}' in {target_path}")


def main():
    """Точка входа для запуска скрипта."""
    try:
        chain = fetch_option_chain(BASE_COIN)
        spot_price = fetch_spot_price(BASE_COIN)
        parsed = parse_option_data(chain, spot_price)

        if not parsed:
            print("No options found after filtering")
        else:
            save_to_excel(parsed, EXCEL_OUT)
            print(f"✅ Spot SOL: ${spot_price:.2f}")

    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    main()
