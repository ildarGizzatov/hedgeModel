"""
db.py — обёртка над SQLite для HedgeModel.

Инициализация БД из schema.sql.
CRUD-операции для всех таблиц.
Query-хелперы для агрегаций (тренды, сводки).
"""

import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import Optional

# Путь к БД (корень проекта)
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "hedge_model.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


# ============================================================
# CONNECTION
# ============================================================

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Подключение к БД с безопасными настройками."""
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # доступ по имени столбца
    conn.execute("PRAGMA journal_mode=WAL")  # concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Инициализация БД: создание таблиц из schema.sql."""
    conn = get_connection(db_path)
    if SCHEMA_PATH.exists():
        conn.executescript(SCHEMA_PATH.read_text())
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        print(f"✅ БД инициализирована ({len(tables)} таблиц)")
    else:
        raise FileNotFoundError(f"Схема не найдена: {SCHEMA_PATH}")
    return conn


def execute_query(query: str, params: tuple = ()) -> list[dict]:
    """Выполнить SELECT и вернуть list[dict]."""
    conn = get_connection()
    try:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def execute_write(query: str, params: tuple = ()) -> int:
    """Выполнить INSERT/UPDATE/DELETE. Возвращает affected rows."""
    conn = get_connection()
    try:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ============================================================
# POSITIONS (open positions CSV replacement)
# ============================================================

def get_position(symbol: str = "SOL") -> Optional[dict]:
    """Получить текущую позицию."""
    rows = execute_query(
        "SELECT * FROM positions WHERE symbol=? ORDER BY updated DESC LIMIT 1",
        (symbol,)
    )
    return rows[0] if rows else None


def upsert_position(symbol: str, qty: float, avg_price: float,
                    total_cost: float, current_price: float = None,
                    total_value: float = None, pnl: float = None,
                    updated: Optional[str] = None) -> int:
    """Добавить или обновить позицию SOL."""
    updated = updated or date.today().isoformat()
    if total_value is None and current_price is not None:
        total_value = round(qty * current_price, 2)
    if pnl is None and current_price is not None:
        pnl = round((current_price - avg_price) * qty, 2)

    conn = get_connection()
    conn.execute(
        "INSERT INTO positions (symbol, qty, avg_price, total_cost, current_price, "
        "total_value, pnl, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (symbol, qty, avg_price, total_cost, current_price, total_value, pnl, updated)
    )
    conn.commit()
    conn.close()
    return 1


def update_position_prices(symbol: str, spot_price: float) -> None:
    """Обновить current_price, total_value, pnl для позиции SOL."""
    pos = get_position(symbol)
    if not pos:
        return
    qty = float(pos["qty"])
    avg = float(pos["avg_price"])
    current_value = round(qty * spot_price, 2)
    pnl = round((spot_price - avg) * qty, 2)

    conn = get_connection()
    conn.execute(
        "UPDATE positions SET current_price=?, total_value=?, pnl=?, updated=? "
        "WHERE symbol=? ORDER BY updated DESC LIMIT 1",
        (spot_price, current_value, pnl, date.today().isoformat(), symbol)
    )
    conn.commit()
    conn.close()


# ============================================================
# OPTIONS (registry replacement)
# ============================================================

def add_option(symbol: str, opt_type: str, strike: float, expiry: str,
               qty: int = 1, layer: str = None,
               entry_date: str = None, entry_price: float = None,
               iv_entry: float = None, iv_atm_entry: float = None,
               delta_entry: float = None, gamma_entry: float = None,
               theta_entry: float = None, vega_entry: float = None,
               notes: str = None) -> int:
    """Добавить опцион в реестр."""
    entry_date = entry_date or date.today().isoformat()
    conn = get_connection()
    conn.execute("""
        INSERT INTO options (symbol, type, strike, expiry, qty, layer, entry_date,
                             entry_price, iv_entry, iv_atm_entry, delta_entry,
                             gamma_entry, theta_entry, vega_entry, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol, opt_type, strike, expiry, qty, layer, entry_date,
          entry_price, iv_entry, iv_atm_entry, delta_entry,
          gamma_entry, theta_entry, vega_entry, notes))
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return row_id


def get_option_by_symbol(symbol: str) -> Optional[dict]:
    """Получить опцион по символу."""
    rows = execute_query("SELECT * FROM options WHERE symbol=?", (symbol,))
    return rows[0] if rows else None


def get_open_options(layer: str = None) -> list[dict]:
    """Получить открытые опционы, фильтр по layer."""
    query = "SELECT * FROM options WHERE status='open'"
    if layer:
        query += f" AND layer='{layer}'"
    return execute_query(query)


def get_all_open_options() -> list[dict]:
    """Получить ВСЕ открытые опционы (для monitor)."""
    return execute_query("SELECT * FROM options WHERE status='open'")


def close_option(option_id: int, close_price: float,
                 close_reason: str = "manual", notes: str = None) -> None:
    """Закрыть опцион, записать в closed_positions."""
    conn = get_connection()
    # 1. Закрыть в options
    conn.execute("UPDATE options SET status='closed' WHERE id=?", (option_id,))
    # 2. Записать в closed_positions
    conn.execute("""
        INSERT INTO closed_positions (option_id, symbol, close_date, close_price,
                                       entry_price, pnl, close_reason, notes)
        SELECT ?, symbol, ?, close_price, entry_price,
               (close_price - entry_price) * qty, ?, ?
        FROM options WHERE id=?
    """, (option_id, date.today().isoformat(), close_price,
          close_reason, notes, option_id))
    conn.commit()
    conn.close()


# ============================================================
# OPTION GREEKS HISTORY (incremental)
# ============================================================

def record_greeks(option_id: int, option_symbol: str,
                  current_price: float = None, delta: float = None,
                  gamma: float = None, theta: float = None,
                  vega: float = None, iv: float = None, iv_atm: float = None,
                  dte: int = None, intrinsic_value: float = None,
                  unrealized_pnl: float = None, timestamp: str = None) -> int:
    """Записать snapshot Greeks для опциона."""
    timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_connection()
    conn.execute("""
        INSERT INTO option_greeks_history
            (timestamp, option_id, option_symbol, current_price, delta, gamma,
             theta, vega, iv, iv_atm, dte, intrinsic_value, unrealized_pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, option_id, option_symbol, current_price, delta, gamma,
          theta, vega, iv, iv_atm, dte, intrinsic_value, unrealized_pnl))
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return row_id


def get_latest_greeks(option_id: int) -> Optional[dict]:
    """Получить последние Greeks для опциона."""
    rows = execute_query(
        "SELECT * FROM option_greeks_history WHERE option_id=? ORDER BY timestamp DESC LIMIT 1",
        (option_id,)
    )
    return rows[0] if rows else None


def get_greeks_trend(option_id: int, days: int = 7) -> list[dict]:
    """Получить историю Greeks за N дней (для LLM)."""
    cutoff = f"(datetime('now', '-{days} days'))"
    return execute_query(
        "SELECT * FROM option_greeks_history WHERE option_id=? AND timestamp>? ORDER BY timestamp",
        (option_id, cutoff)
    )


def get_all_latest_greeks() -> list[dict]:
    """Получить последние Greeks для ВСЕХ опционов (для monitor)."""
    return execute_query("""
        SELECT h.*
        FROM option_greeks_history h
        INNER JOIN (
            SELECT option_id, MAX(timestamp) as max_ts
            FROM option_greeks_history
            GROUP BY option_id
        ) latest ON h.option_id = latest.option_id AND h.timestamp = latest.max_ts
        ORDER BY h.timestamp DESC
    """)


# ============================================================
# OPTION CHAIN SNAPSHOT
# ============================================================

def record_chain_snapshot(base_coin: str, spot_price: float,
                          options_data: list[dict], timestamp: str = None) -> int:
    """Записать полный снимок option chain."""
    timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_connection()
    for opt in options_data:
        conn.execute("""
            INSERT INTO option_chain_snapshot
                (timestamp, base_coin, spot_price, symbol, type, strike, expiry,
                 dte, bid, ask, last_price, mark_price, volume, open_interest,
                 iv, delta, gamma, theta, vega, intrinsic_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, base_coin, spot_price,
              opt.get("symbol"), opt.get("type", "PUT"), opt.get("strike", 0),
              opt.get("expiry"), opt.get("dte", 0),
              opt.get("bid"), opt.get("ask"), opt.get("last_price"),
              opt.get("mark_price"), opt.get("volume"), opt.get("open_interest"),
              opt.get("iv"), opt.get("delta"), opt.get("gamma"),
              opt.get("theta"), opt.get("vega"), opt.get("intrinsic_value")))
    conn.commit()
    conn.close()
    return len(options_data)


def get_latest_chain_snapshot() -> list[dict]:
    """Получить самый свежий снимок chain."""
    ts = execute_query(
        "SELECT MAX(timestamp) as ts FROM option_chain_snapshot"
    )[0]["ts"]
    return execute_query(
        "SELECT * FROM option_chain_snapshot WHERE timestamp=?", (ts,)
    )


# ============================================================
# RECOMMENDATIONS (LLM integration)
# ============================================================

def add_recommendation(option_id: int = None, option_symbol: str = None,
                       action: str = None, reason: str = None,
                       confidence: float = None, llm_model: str = None,
                       prompt_tokens: int = None,
                       completion_tokens: int = None) -> int:
    """Добавить рекомендацию."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO recommendations
            (timestamp, option_id, option_symbol, action, reason, confidence,
             llm_model, llm_prompt_tokens, llm_completion_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M"),
          option_id, option_symbol, action, reason, confidence,
          llm_model, prompt_tokens, completion_tokens))
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return row_id


def update_recommendation_status(rec_id: int, status: str,
                                  user_feedback: str = None) -> None:
    """Обновить статус рекомендации (accepted/rejected) + фидбек."""
    conn = get_connection()
    if user_feedback:
        conn.execute(
            "UPDATE recommendations SET status=?, user_feedback=? WHERE id=?",
            (status, user_feedback, rec_id)
        )
    else:
        conn.execute(
            "UPDATE recommendations SET status=? WHERE id=?",
            (status, rec_id)
        )
    conn.commit()
    conn.close()


def get_pending_recommendations() -> list[dict]:
    """Получить все pending рекомендации."""
    return execute_query(
        "SELECT * FROM recommendations WHERE status='pending' ORDER BY timestamp DESC"
    )


def get_all_recommendations(limit: int = 20) -> list[dict]:
    """Получить последние N рекомендаций."""
    return execute_query(
        f"SELECT * FROM recommendations ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )


# ============================================================
# BUY HISTORY
# ============================================================

def add_buy_history(buy_date: str = None, qty: float = None,
                    price: float = None, total: float = None,
                    symbol: str = "SOL", notes: str = None) -> int:
    """Добавить запись о покупке SOL."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO buy_history (buy_date, qty, price, total, symbol, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (buy_date or date.today().isoformat(), qty, price, total, symbol, notes))
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return row_id


def get_buy_history() -> list[dict]:
    """Получить историю покупок SOL."""
    return execute_query("SELECT * FROM buy_history ORDER BY buy_date DESC")


# ============================================================
# CLOSED POSITIONS
# ============================================================

def get_closed_positions() -> list[dict]:
    """Получить историю закрытых опционов."""
    return execute_query(
        "SELECT * FROM closed_positions ORDER BY close_date DESC"
    )


# ============================================================
# STATISTICS / HELPERS
# ============================================================

def table_stats() -> dict:
    """Статистика по всем таблицам (кол-во строк)."""
    tables = [
        "positions", "options", "option_chain_snapshot",
        "option_greeks_history", "closed_positions",
        "buy_history", "recommendations"
    ]
    stats = {}
    for t in tables:
        rows = execute_query(f"SELECT COUNT(*) as cnt FROM {t}")
        stats[t] = rows[0]["cnt"] if rows else 0
    return stats


def check_db() -> None:
    """Проверить наличие БД и таблиц."""
    if not DB_PATH.exists():
        print("⚠️  БД не найдена. Запустите: python src/db.py init")
        return

    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()

    print(f"📊 БД: {DB_PATH} ({DB_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"📋 Таблиц: {len(tables)}")
    for t in tables:
        rows = execute_query(f"SELECT COUNT(*) as cnt FROM {t[0]}")
        print(f"   {t[0]:30s} {rows[0]['cnt']:6d} строк")
