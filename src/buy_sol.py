#!/usr/bin/env python3
"""
buy_sol.py — Покупка SOL с записью в БД.

Запуск:
    python src/buy_sol.py --qty 10 --price 72.5
    python src/buy_sol.py --qty 10 --price 72.5 --notes "покупка 20 июня"
"""

import argparse
import sys
from pathlib import Path
from datetime import date

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from src.db import add_buy_history


def main():
    parser = argparse.ArgumentParser(description="Купить SOL")
    parser.add_argument("--qty", type=float, required=True, help="Количество SOL")
    parser.add_argument("--price", type=float, required=True, help="Цена за единицу")
    parser.add_argument("--notes", type=str, default="", help="Комментарий")
    args = parser.parse_args()

    if args.qty <= 0 or args.price <= 0:
        print("❌ qty и price должны быть > 0")
        sys.exit(1)

    total = round(args.qty * args.price, 2)

    # 1. Записать покупку в buy_history
    add_buy_history(
        buy_date=date.today().isoformat(),
        qty=args.qty,
        price=args.price,
        total=total,
        symbol="SOL",
        notes=args.notes,
    )
    print(f"✅ Покупка записана: {args.qty} SOL @ ${args.price} = ${total}")
    print("✅ Готово.")


if __name__ == "__main__":
    main()
