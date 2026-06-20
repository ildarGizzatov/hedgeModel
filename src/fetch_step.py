"""fetch_step.py — Шаг 1: загрузка чейна с Bybit → БД."""

from src.chain_fetcher import fetch_and_filter_chain
from src.db import record_chain_snapshot, update_position_prices


def main():
    print("[1/3] FETCH — загрузка чейна SOL...")
    rows, spot_price = fetch_and_filter_chain("SOL")

    if not rows:
        print("  ⚠️ Нет опционов после фильтрации")
        return

    count = record_chain_snapshot("SOL", spot_price, rows)
    print(f"  ✅ Записано в БД: {count} опционов")

    update_position_prices("SOL", spot_price)
    print(f"  ✅ SOL позиция обновлена: ${spot_price:.2f}")
