"""prices_step.py — Обновить только цены (spot + позиции в БД)."""

from src.chain_fetcher import fetch_and_filter_chain
from src.db import update_position_prices


def main():
    print("[1/1] PRICES — обновление цен...")
    _, spot_price = fetch_and_filter_chain("SOL")
    update_position_prices("SOL", spot_price)
    print(f"  ✅ Позиция SOL обновлена: ${spot_price:.2f}")
