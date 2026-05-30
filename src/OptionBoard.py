import requests
import pandas as pd
from datetime import datetime, timezone
import os

BYBIT_API = "https://api.bybit.com/v5/market/tickers"

# Мы всегда будем запускать скрипт из корня проекта (hedgeModel/).
# Поэтому путь к файлу должен быть относительно корня.
EXCEL_OUT = "sol_options_chain.xlsx" 

BASE_COIN = "SOL"
SHEET_NAME = "OptionBoard"


def fetch_option_chain(base_coin):
    params = {
        "category": "option",
        "baseCoin": base_coin
    }
    r = requests.get(BYBIT_API, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    if not data.get("result") or not isinstance(data["result"].get("list"), list):
        raise RuntimeError("Unexpected API response structure")

    return data["result"]["list"]


def fetch_spot_price(base_coin):
    r = requests.get(BYBIT_API, params={"category": "spot"}, timeout=30)
    r.raise_for_status()
    data = r.json()

    if not data.get("result") or not isinstance(data["result"].get("list"), list):
        raise RuntimeError("Unexpected API response structure for spot price")

    symbol = f"{base_coin}USDT"
    spot_price = None
    for ticker in data["result"]["list"]:
        if ticker.get("symbol") == symbol:
            spot_price = float(ticker.get("lastPrice") or 0)
            break

    if spot_price is None:
        raise RuntimeError(f"Spot price for {symbol} not found")

    return spot_price


def parse_option_data(option_list, spot_price):
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
    df = pd.DataFrame(rows)
    if not df.empty:
        df["type_order"] = df["type"].map({"PUT": 0, "CALL": 1})
        df = df.sort_values(by=["dte", "type_order", "strike"])
        df = df.drop(columns=["type_order"])

    # Ищем полный путь к файлу относительно корня проекта
    # Мы предполагаем, что запуск идет из корня hedgeModel/
    target_path = os.path.abspath(filename)

    if os.path.exists(target_path):
        with pd.ExcelWriter(target_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=SHEET_NAME, index=False)
    else:
        # Если файла нет (например, при первом запуске в новой папке), создаем его
        with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=SHEET_NAME, index=False)

    print(f"Option board saved to sheet '{SHEET_NAME}' in {os.path.abspath(filename)}")


if __name__ == "__main__":
    try:
        chain = fetch_option_chain(BASE_COIN)
        spot_price = fetch_spot_price(BASE_COIN)
        parsed = parse_option_data(chain, spot_price)

        if not parsed:
            print("No options found after filtering")
        else:
            save_to_excel(parsed, EXCEL_OUT)

    except Exception as e:
        print("Error:", e)
