"""fetch_step.py — Шаг 1: загрузка чейна с Bybit → БД."""

from src.chain_fetcher import fetch_and_filter_chain
from src.db import record_chain_snapshot


def main():
    print("[1/1] FETCH — загрузка чейна SOL...")
    rows, spot_price = fetch_and_filter_chain("SOL")

    if not rows:
        print("  ⚠️ Нет опционов после фильтрации")
        return

    count = record_chain_snapshot("SOL", spot_price, rows)
    print(f"  ✅ Записано в БД: {count} опционов")
    print(f"  SOL: ${spot_price:.2f}")
