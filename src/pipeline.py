#!/usr/bin/env python3
"""
Orchestrator проекта HedgeModel.

Подключает все модули в единый пайплайн:
    pipeline.py status   — статус обновлений
    pipeline.py fetch    — загрузить опционный чейн с Bybit
    pipeline.py select   — подобрать Anchor (Core + Tail)
    pipeline.py monitor  — сводка портфеля + рекомендации
    pipeline.py run      — полный цикл (fetch → select → monitor)

Использует существующие модули без дублирования логики.
"""
import sys
import os
import argparse
from datetime import datetime, date
from pathlib import Path

# Корень проекта
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
sys.path.insert(0, str(PROJECT_DIR))


# ============================================================
# СТЕПЫ
# ============================================================

def step_fetch():
    """Шаг 1: Загрузить опционный чейн SOL с Bybit в Excel."""
    from OptionBoard import (
        fetch_option_chain, fetch_spot_price,
        parse_option_data, save_to_excel, update_positions_csv
    )

    print("[1/3] FETCH — загрузка опционного чейна SOL...")

    try:
        chain = fetch_option_chain("SOL")
        spot = fetch_spot_price("SOL")
        parsed = parse_option_data(chain, spot)

        if not parsed:
            print("  ⚠️  Нет опционов после фильтрации")
            return False

        save_to_excel(parsed, "excel/sol_options_chain.xlsx")
        update_positions_csv("excel/sol_options_chain.xlsx")

        print(f"  ✅ {len(parsed)} опционов → excel/sol_options_chain.xlsx")
        print(f"     Spot: ${spot:.2f}")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


def step_select():
    """Шаг 2: Подобрать Anchor Layer (Core + Tail)."""
    from anchor_picker import main as anchor_main

    print("[2/3] SELECT — подбор Anchor Layer...")

    try:
        anchor_main()
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


def step_monitor():
    """Шаг 3: Мониторинг портфеля + рекомендации."""
    from monitor_options import main as monitor_main

    print("[3/3] MONITOR — анализ позиций...")

    try:
        monitor_main()
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


def step_update_prices():
    """Шаг: Обновить только текущие цены (spot + позиции)."""
    import csv
    from OptionBoard import fetch_spot_price
    print("[1/1] PRICES — обновление цен...")
    try:
        spot = fetch_spot_price("SOL")
        # Читаем позиции
        pos_path = DATA_DIR / "open_positions.csv"
        rows = []
        if pos_path.exists():
            with open(pos_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        
        updated = 0
        for r in rows:
            if r.get("symbol", "").upper().startswith("SOL"):
                qty = float(r.get("qty", 0))
                r["current_price"] = str(spot)
                r["total_value"] = str(round(qty * spot, 2))
                avg = float(r.get("avg_price", 0))
                cost = float(r.get("total_cost", 0))
                r["pnl"] = str(round((spot - avg) * qty, 2))
                updated += 1
        
        if rows:
            with open(pos_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        
        print(f"  ✅ Spot обновлён: ${spot:.2f}")
        print(f"  ✅ Позиций обновлено: {updated}")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


def step_run():
    """Полный цикл: fetch → select → monitor."""
    print("=" * 60)
    print("PIPELINE: FULL CYCLE")
    print("=" * 60)
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    results = {}
    results["fetch"] = step_fetch()
    if not results["fetch"]:
        print("\n⚠️  Fetch не удался, select пропуск...")
        results["select"] = None
    else:
        results["select"] = step_select()

    results["monitor"] = step_monitor()

    # Итог
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТ")
    print("=" * 60)
    for step_name, ok in results.items():
        status = "✅ OK" if ok else ("❌ FAIL" if ok is False else "⏭ SKIP")
        print(f"  {step_name:12s} {status}")
    print("=" * 60)


def step_status():
    """Показать статус обновлений."""
    print("СТАТУС ОБНОВЛЕНИЙ")
    print("=" * 40)

    checks = {
        "Excel (OptionBoard)": "excel/sol_options_chain.xlsx",
        "open_positions.csv": "data/open_positions.csv",
        "options_registry.csv": "data/options_registry.csv",
        "options_tracking.csv": "data/options_tracking.csv",
        "buy_history.csv": "data/buy_history.csv",
    }

    for name, rel_path in checks.items():
        p = Path(PROJECT_DIR) / rel_path
        if p.exists():
            mtime = date.fromtimestamp(p.stat().st_mtime)
            print(f"  {name:30s} {mtime}  ({p.stat().st_size} bytes)")
        else:
            print(f"  {name:30s} ❌ не найден")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="HedgeModel Pipeline")
    parser.add_argument("command", nargs="?", default="status",
                        help="fetch | select | monitor | run | status | prices",
                        choices=["fetch", "select", "monitor", "run", "status", "prices"])
    args = parser.parse_args()

    commands = {
        "fetch": step_fetch,
        "select": step_select,
        "monitor": step_monitor,
        "run": step_run,
        "status": step_status,
        "prices": step_update_prices,
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
