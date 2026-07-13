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
    """Инициализация БД: создание таблиц из schema.sql + миграции."""
    conn = get_connection(db_path)
    if SCHEMA_PATH.exists():
        conn.executescript(SCHEMA_PATH.read_text())
    migrate_db(conn)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    print(f"✅ БД инициализирована ({len(tables)} таблиц)")
    conn.close()
    return conn


def migrate_db(conn: sqlite3.Connection) -> None:
    """Миграции БД: добавление новых столбцов."""
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t[0] for t in tables]
    
    # buy_history: добавить closed=1 если таблица есть
    if "buy_history" in table_names:
        cols = conn.execute("PRAGMA table_info(buy_history)").fetchall()
        col_names = [c[1] for c in cols]
        if "closed" not in col_names:
            conn.execute("ALTER TABLE buy_history ADD COLUMN closed INTEGER NOT NULL DEFAULT 0")
            print("  → Добавлен столбец buy_history.closed")
        else:
            # Установить все существующие строки как open=0
            conn.execute("UPDATE buy_history SET closed=0 WHERE closed IS NULL")
    
    # Portf: создать если нет
    if "Portf" not in table_names:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Portf (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                token           TEXT NOT NULL,
                qty             REAL NOT NULL,
                avg_price       REAL NOT NULL,
                notes           TEXT
            )
        """)
        print("  → Создана таблица Portf")
    
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
# POSITIONS — агрегация из buy_history
# ============================================================

def get_portfolio_position(symbol: str = "SOL") -> Optional[dict]:
    """Получить текущую позицию, агрегированную из buy_history (только open записи)."""
    rows = execute_query(
        "SELECT * FROM buy_history WHERE symbol=? AND closed=0 ORDER BY buy_date DESC",
        (symbol,)
    )
    if not rows:
        return None
    total_qty = sum(float(r["qty"]) for r in rows)
    total_cost = sum(float(r["total"]) for r in rows)
    if total_qty <= 0:
        return None
    return {
        "symbol": symbol,
        "qty": total_qty,
        "avg_price": round(total_cost / total_qty, 4),
        "total_cost": round(total_cost, 2),
    }


def sell(symbol: str, qty: float, price: float, notes: str = "") -> Optional[dict]:
    """Продать часть/всю позицию. Записывает отрицательный qty в buy_history."""
    if qty <= 0:
        return None
    
    existing = get_portfolio_position(symbol)
    if not existing:
        return None
    
    if qty > existing["qty"]:
        print(f"  ⚠️ Продажа {qty} > текущая позиция {existing['qty']}")
        return None
    
    total = round(qty * price, 2)
    conn = get_connection()
    conn.execute(
        "INSERT INTO buy_history (buy_date, qty, price, total, symbol, notes, closed) "
        "VALUES (?, ?, ?, ?, ?, ?, 0)",
        (date.today().isoformat(), -qty, price, -total, symbol, notes or "продажа")
    )
    
    # Если позиция закрыта полностью — пометить все записи closed=1
    new_qty = existing["qty"] - qty
    if new_qty <= 0:
        conn.execute(
            "UPDATE buy_history SET closed=1 WHERE symbol=? AND closed=0",
            (symbol,)
        )
    
    conn.commit()
    conn.close()
    return get_portfolio_position(symbol)  # Вернуть новую позицию


def get_buy_history_all(symbol: str = "SOL") -> list[dict]:
    """Получить все записи buy_history для символа (вкл. closed)."""
    return execute_query(
        "SELECT * FROM buy_history WHERE symbol=? ORDER BY buy_date DESC",
        (symbol,)
    )


def get_all_portfolio_symbols() -> list[str]:
    """Получить все символы с открытыми позициями."""
    rows = execute_query(
        "SELECT DISTINCT symbol FROM buy_history WHERE closed=0 AND qty > 0 ORDER BY symbol"
    )
    return [r["symbol"] for r in rows]


# ============================================================
# PORTFOLIO (не-SOL активы из таблицы Portf)
# ============================================================

def get_portfolio_all() -> list[dict]:
    """Получить все позиции из таблицы Portf."""
    return execute_query(
        "SELECT * FROM Portf ORDER BY token"
    )


def update_portfolio(token: str, qty: float, avg_price: float, notes: str = "") -> None:
    """Добавить/обновить позицию в Portf."""
    existing = execute_query("SELECT * FROM Portf WHERE token=?", (token,))
    conn = get_connection()
    if existing:
        conn.execute(
            "UPDATE Portf SET qty=?, avg_price=?, notes=? WHERE token=?",
            (qty, avg_price, notes, token)
        )
    else:
        conn.execute(
            "INSERT INTO Portf (token, qty, avg_price, notes) VALUES (?, ?, ?, ?)",
            (token, qty, avg_price, notes)
        )
    conn.commit()
    conn.close()


def delete_portfolio(token: str) -> None:
    """Удалить позицию из Portf."""
    conn = get_connection()
    conn.execute("DELETE FROM Portf WHERE token=?", (token,))
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
    """Добавить опцион в реестр. Если уже есть — обновить qty и avg_price."""
    entry_date = entry_date or date.today().isoformat()
    conn = get_connection()
    existing = conn.execute("SELECT id, qty, entry_price FROM options WHERE symbol=?", (symbol,)).fetchone()
    if existing:
        # Обновляем среднюю цену покупки
        old_id, old_qty, old_price = existing
        new_qty = old_qty + qty
        avg_price = round((old_price * old_qty + entry_price * qty) / new_qty, 4)
        conn.execute("""
            UPDATE options SET
                qty = ?, entry_price = ?, layer = ?, entry_date = ?,
                notes = ?, status = 'open'
            WHERE id = ?
        """, (new_qty, avg_price, layer or "", entry_date, notes or "", old_id))
        conn.commit()
        conn.close()
        return old_id
    else:
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


def get_option_by_id(option_id: int) -> Optional[dict]:
    """Получить опцион по id."""
    rows = execute_query("SELECT * FROM options WHERE id=?", (option_id,))
    return rows[0] if rows else None


def get_option_by_symbol(symbol: str) -> Optional[dict]:
    """Получить опцион по символу."""
    rows = execute_query("SELECT * FROM options WHERE symbol=?", (symbol,))
    return rows[0] if rows else None


def get_all_options(layer: str = None, status: str = None) -> list[dict]:
    """Получить все опционы (вкл. закрытые). Фильтры по layer и status."""
    query = "SELECT * FROM options WHERE 1=1"
    if layer:
        query += f" AND layer='{layer}'"
    if status:
        query += f" AND status='{status}'"
    query += " ORDER BY id DESC"
    return execute_query(query)


def update_option(option_id: int, **kwargs) -> int:
    """Обновить поля опциона. Возвращает rowcount.
    
    Доступные поля: entry_price, qty, notes, layer,
                     iv_entry, delta_entry, gamma_entry,
                     theta_entry, vega_entry, status
    """
    allowed_fields = {
        "entry_price", "qty", "notes", "layer",
        "iv_entry", "delta_entry", "gamma_entry",
        "theta_entry", "vega_entry", "status",
        "entry_date", "type", "strike", "expiry",
        "total_cost", "iv_atm_entry"
    }
    invalid = set(kwargs.keys()) - allowed_fields
    if invalid:
        raise ValueError(f"Недопустимые поля: {invalid}. Доступные: {allowed_fields}")

    if not kwargs:
        return 0

    set_parts = ", ".join(f"{k}=?" for k in kwargs)
    values = tuple(kwargs.values()) + (option_id,)

    return execute_write(
        f"UPDATE options SET {set_parts} WHERE id=?",
        values
    )


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
    # 1. Прочитать данные опциона
    row = conn.execute("SELECT * FROM options WHERE id=?", (option_id,)).fetchone()
    if not row:
        conn.close()
        return
    entry_price = float(row["entry_price"] or 0)
    qty = int(row["qty"])
    symbol = row["symbol"]
    pnl = round((close_price - entry_price) * qty, 2)

    # 2. Закрыть в options
    conn.execute("UPDATE options SET status='closed' WHERE id=?", (option_id,))
    # 3. Записать в closed_positions
    conn.execute("""
        INSERT INTO closed_positions
            (option_id, symbol, close_date, close_price, entry_price, pnl, close_reason, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (option_id, symbol, date.today().isoformat(), close_price,
          entry_price, pnl, close_reason, notes))
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
        "options", "option_chain_snapshot",
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
