import requests
import pandas as pd

BYBIT_API = "https://api.bybit.com/v5/market/tickers"

EXCEL_FILE = "sol_options_chain.xlsx"
SHEET_NAME = "ListOption"
BASE_COIN = "SOL"


# -----------------------------
# Получаем цены по опционам
# -----------------------------
def fetch_market_data(symbols):
    params = {
        "category": "option",
        "baseCoin": BASE_COIN
    }

    r = requests.get(BYBIT_API, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    result = data.get("result", {}).get("list", [])

    market_map = {}

    for item in result:
        sym = item.get("symbol")

        if sym in symbols:
            market_map[sym] = {
                "last_price": float(item.get("lastPrice") or 0),
                "bid_price": float(item.get("bid1Price") or 0),
                "ask_price": float(item.get("ask1Price") or 0),
                "mark_price_live": float(item.get("markPrice") or 0),
            }

    return market_map


# -----------------------------
# Основная логика
# -----------------------------
def update_market_data():
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)

    if "symbol" not in df.columns:
        raise RuntimeError("Нет колонки symbol")

    symbols = df["symbol"].dropna().tolist()

    market_map = fetch_market_data(symbols)

    # маппинг колонок
    df["last_price"] = df["symbol"].map(lambda x: market_map.get(x, {}).get("last_price"))
    df["bid_price"] = df["symbol"].map(lambda x: market_map.get(x, {}).get("bid_price"))
    df["ask_price"] = df["symbol"].map(lambda x: market_map.get(x, {}).get("ask_price"))
    df["mark_price_live"] = df["symbol"].map(lambda x: market_map.get(x, {}).get("mark_price_live"))

    # покажем что не нашлось
    missing = df[df["last_price"].isna()]
    if not missing.empty:
        print("Не найдено:")
        print(missing["symbol"].tolist())

    # запись обратно
    with pd.ExcelWriter(
        EXCEL_FILE,
        engine="openpyxl",
        mode="a",
        if_sheet_exists="replace"
    ) as writer:
        df.to_excel(writer, sheet_name=SHEET_NAME, index=False)

    print("Обновлено:", SHEET_NAME)


# -----------------------------
# Запуск
# -----------------------------
if __name__ == "__main__":
    try:
        update_market_data()
    except Exception as e:
        print("Error:", e)