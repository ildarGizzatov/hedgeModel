"""status_step.py — Показать статус БД и файлов."""

from datetime import date
from pathlib import Path

from src import db


PROJECT_DIR = Path(__file__).resolve().parent.parent


def main():
    print("СТАТУС ОБНОВЛЕНИЙ")
    print("=" * 40)

    # ========================================================
    # PostgreSQL
    # ========================================================

    print("\n  PostgreSQL:")

    try:
        stats = db.table_stats()

        for table, count in stats.items():
            print(f"    БД.{table:30s} {count:6d} записей")

    except Exception as e:
        print(f"    ❌ Ошибка подключения к PostgreSQL: {e}")

    # ========================================================
    # CSV — только для информации
    # ========================================================

    csv_files = {
        "open_positions.csv": "data/open_positions.csv",
        "options_registry.csv": "data/options_registry.csv",
    }

    print("\n  CSV (бэкап):")

    for name, rel_path in csv_files.items():
        p = PROJECT_DIR / rel_path

        if p.exists():
            mtime = date.fromtimestamp(p.stat().st_mtime)
            print(
                f"    {name:30s} "
                f"{mtime}  ({p.stat().st_size} bytes)"
            )
        else:
            print(f"    {name:30s} ❌ не найден")


if __name__ == "__main__":
    main()
