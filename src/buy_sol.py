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

from src.db import get_position, add_buy_history, upsert_position


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

    # 2. Обновить позицию (усреднить avg_price)
    existing = get_position("SOL")

    if existing:
        old_qty = float(existing["qty"])
        old_avg = float(existing["avg_price"])
        new_qty = old_qty + args.qty
        new_avg = round((old_qty * old_avg + args.qty * args.price) / new_qty, 4)
        new_total_cost = round(new_qty * new_avg, 2)

        from src.db import get_connection
        conn = get_connection()
        conn.execute(
            "UPDATE positions SET qty=?, avg_price=?, total_cost=? WHERE symbol=?",
            (new_qty, new_avg, new_total_cost, "SOL")
        )
        conn.commit()
        conn.close()

        print(f"  Позиция обновлена: {old_qty} → {new_qty} SOL")
        print(f"  Avg price: ${old_avg} → ${new_avg}")
    else:
        upsert_position(
            symbol="SOL",
            qty=args.qty,
            avg_price=round(args.price, 4),
            total_cost=total,
            updated=date.today().isoformat(),
        )
        print(f"  Новая позиция: {args.qty} SOL @ ${args.price}")

    print("✅ Готово.")


if __name__ == "__main__":
    main()
