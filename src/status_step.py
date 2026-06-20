"""status_step.py — Показать статус БД и файлов."""

from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def main():
    print("СТАТУС ОБНОВЛЕНИЙ")
    print("=" * 40)

    # БД
    db_path = PROJECT_DIR / "hedge_model.db"
    if db_path.exists():
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        tables = ["positions", "options", "option_chain_snapshot",
                  "option_greeks_history", "closed_positions", "buy_history", "recommendations"]
        for table in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"  БД.{table:30s} {count:6d} записей")
            except:
                pass
        conn.close()

    # CSV (только для информации)
    csv_files = {
        "open_positions.csv": "data/open_positions.csv",
        "options_registry.csv": "data/options_registry.csv",
    }

    print("\n  CSV (бэкап):")
    for name, rel_path in csv_files.items():
        p = PROJECT_DIR / rel_path
        if p.exists():
            mtime = date.fromtimestamp(p.stat().st_mtime)
            print(f"    {name:30s} {mtime}  ({p.stat().st_size} bytes)")
        else:
            print(f"    {name:30s} ❌ не найден")
