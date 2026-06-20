#!/usr/bin/env python3
"""
pipeline.py — Orchestrator HedgeModel.

Команды:
    pipeline.py fetch    — загрузить чейн с Bybit → БД
    pipeline.py select   — подобрать Anchor (Core + Tail)
    pipeline.py monitor  — сводка портфеля + рекомендации
    pipeline.py prices   — обновить только цены (spot + позиции)
    pipeline.py run      — полный цикл (fetch → select → monitor)
    pipeline.py status   — статус БД и файлов
"""
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import argparse


def main():
    parser = argparse.ArgumentParser(description="HedgeModel Pipeline")
    parser.add_argument("command", nargs="?", default="status",
                        help="fetch | select | monitor | run | status | prices",
                        choices=["fetch", "select", "monitor", "run", "status", "prices"])
    args = parser.parse_args()

    # Импорт здесь — ленивый, только нужные модули
    if args.command == "fetch":
        from src.fetch_step import main
    elif args.command == "select":
        from anchor_picker import main
    elif args.command == "monitor":
        from monitor_options import main
    elif args.command == "prices":
        from src.prices_step import main
    elif args.command == "run":
        from src.run_step import main
    elif args.command == "status":
        from src.status_step import main
    else:
        return

    main()


if __name__ == "__main__":
    main()
