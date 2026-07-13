"""prices_step.py — Обновить только цены (spot price из API)."""

from src.chain_fetcher import fetch_and_filter_chain


def main():
    print("[1/1] PRICES — получение spot price...")
    _, spot_price = fetch_and_filter_chain("SOL")
    print(f"  SOL: ${spot_price:.2f}")
