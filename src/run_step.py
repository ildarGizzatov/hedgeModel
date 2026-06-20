"""run_step.py — Полный цикл: fetch → select → monitor."""

from datetime import datetime


def main():
    print("=" * 60)
    print("PIPELINE: FULL CYCLE")
    print("=" * 60)
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    from src.fetch_step import main as fetch
    from anchor_picker import main as select
    from monitor_options import main as monitor

    fetch()
    select()
    monitor()

    print("=" * 60)
    print("✅ PIPELINE COMPLETE")
    print("=" * 60)
