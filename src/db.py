"""
db.py — PostgreSQL database wrapper for HedgeModel.
"""

import os
from datetime import datetime, date
from typing import Optional

import psycopg
from psycopg.rows import dict_row


# ============================================================
# POSTGRESQL CONNECTION
# ============================================================

PG_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "hedge_model",
    "user": "hedge_app",
    "password": os.environ.get("POSTGRES_PASSWORD", "U8AGsOhdPO"),
}


def get_connection():
    """Подключение к PostgreSQL."""
    return psycopg.connect(
        **PG_CONFIG,
        row_factory=dict_row,
    )


def execute_query(query: str, params: tuple = ()) -> list[dict]:
    """SELECT → list[dict]."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    except Exception as e:
        print(f"DB query error: {e}")
        return []
    finally:
        conn.close()


def execute_write(query: str, params: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            affected = cur.rowcount
        conn.commit()
        return affected
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# BUY HISTORY
# ============================================================

def insert_buy_history(
    symbol: str,
    qty: float,
    price: float,
    total: float,
    buy_date: str,
    notes: str = "",
) -> int:

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO buy_history
                    (buy_date, qty, price, total, symbol, notes, closed)
                VALUES (%s, %s, %s, %s, %s, %s, 0)
                RETURNING id
                """,
                (buy_date, qty, price, total, symbol, notes),
            )
            row_id = cur.fetchone()["id"]

        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_buy_history(
    buy_date: str = None,
    qty: float = None,
    price: float = None,
    total: float = None,
    symbol: str = "SOL",
    notes: str = None,
) -> int:

    return insert_buy_history(
        symbol=symbol,
        qty=qty,
        price=price,
        total=total,
        buy_date=buy_date or date.today().isoformat(),
        notes=notes or "",
    )


def get_buy_history() -> list[dict]:
    return execute_query(
        "SELECT * FROM buy_history ORDER BY buy_date DESC"
    )


def get_buy_history_all(symbol: str = "SOL") -> list[dict]:
    return execute_query(
        """
        SELECT *
        FROM buy_history
        WHERE symbol=%s
        ORDER BY buy_date DESC
        """,
        (symbol,),
    )


# ============================================================
# SELL HISTORY
# ============================================================

def get_sell_history() -> list[dict]:
    return execute_query(
        "SELECT * FROM sell_history ORDER BY sell_date DESC"
    )


def insert_sell_history(
    buy_id: int,
    symbol: str,
    qty: float,
    buy_price: float,
    sell_price: float,
    total: float,
    pnl: float,
    sell_date: str,
    notes: str = "",
) -> int:

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sell_history
                    (buy_id, symbol, qty, buy_price, sell_price,
                     total, pnl, sell_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    buy_id,
                    symbol,
                    qty,
                    buy_price,
                    sell_price,
                    total,
                    pnl,
                    sell_date,
                    notes,
                ),
            )
            row_id = cur.fetchone()["id"]

        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# PORTFOLIO
# ============================================================

def update_portfolio_position(
    token: str,
    qty: float,
    avg_price: float,
    notes: str = "",
) -> bool:

    existing = execute_query(
        "SELECT id FROM portf WHERE token=%s",
        (token,),
    )

    if existing:
        execute_write(
            """
            UPDATE portf
            SET qty=%s, avg_price=%s, notes=%s
            WHERE token=%s
            """,
            (qty, avg_price, notes, token),
        )
    else:
        execute_write(
            """
            INSERT INTO portf
                (token, qty, avg_price, notes)
            VALUES (%s, %s, %s, %s)
            """,
            (token, qty, avg_price, notes),
        )

    return True


# ============================================================
# POSITIONS
# ============================================================

def get_portfolio_position(symbol: str = "SOL") -> Optional[dict]:

    rows = execute_query(
        """
        SELECT
            symbol,
            SUM(qty) AS qty,
            CASE
                WHEN SUM(qty) > 0
                THEN SUM(total) / SUM(qty)
                ELSE 0
            END AS avg_price,
            SUM(total) AS total_cost
        FROM buy_history
        WHERE symbol=%s
          AND closed=0
        GROUP BY symbol
        """,
        (symbol,),
    )

    if not rows:
        return None

    row = rows[0]

    if not row["qty"] or float(row["qty"]) <= 0:
        return None

    return {
        "symbol": symbol,
        "qty": float(row["qty"]),
        "avg_price": round(float(row["avg_price"]), 4),
        "total_cost": round(float(row["total_cost"]), 2),
    }


def get_all_portfolio_symbols() -> list[str]:

    rows = execute_query(
        """
        SELECT DISTINCT symbol
        FROM buy_history
        WHERE closed=0
          AND qty > 0
        ORDER BY symbol
        """
    )

    return [r["symbol"] for r in rows]


def sell(
    symbol: str,
    qty: float,
    price: float,
    notes: str = "",
) -> Optional[dict]:

    if qty <= 0:
        return None

    existing = get_portfolio_position(symbol)

    if not existing:
        return None

    if qty > existing["qty"]:
        print(
            f"⚠️ Продажа {qty} > текущая позиция "
            f"{existing['qty']}"
        )
        return None

    total = round(qty * price, 2)

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO buy_history
                    (buy_date, qty, price, total, symbol, notes, closed)
                VALUES (%s, %s, %s, %s, %s, %s, 0)
                """,
                (
                    date.today().isoformat(),
                    -qty,
                    price,
                    -total,
                    symbol,
                    notes or "продажа",
                ),
            )

            new_qty = existing["qty"] - qty

            if new_qty <= 0:
                cur.execute(
                    """
                    UPDATE buy_history
                    SET closed=1
                    WHERE symbol=%s
                      AND closed=0
                    """,
                    (symbol,),
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return get_portfolio_position(symbol)


# ============================================================
# OPTIONS
# ============================================================

def add_option(
    symbol: str,
    opt_type: str,
    strike: float,
    expiry: str,
    qty: int = 1,
    layer: str = None,
    entry_date: str = None,
    entry_price: float = None,
    iv_entry: float = None,
    iv_atm_entry: float = None,
    delta_entry: float = None,
    gamma_entry: float = None,
    theta_entry: float = None,
    vega_entry: float = None,
    notes: str = None,
) -> int:

    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO options
                    (
                        symbol,
                        type,
                        strike,
                        expiry,
                        qty,
                        layer,
                        entry_date,
                        entry_price,
                        iv_entry,
                        iv_atm_entry,
                        delta_entry,
                        gamma_entry,
                        theta_entry,
                        vega_entry,
                        notes
                    )
                VALUES
                    (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                RETURNING id
                """,
                (
                    symbol,
                    opt_type,
                    strike,
                    expiry,
                    qty,
                    layer,
                    entry_date or date.today().isoformat(),
                    entry_price,
                    iv_entry,
                    iv_atm_entry,
                    delta_entry,
                    gamma_entry,
                    theta_entry,
                    vega_entry,
                    notes,
                ),
            )

            row_id = cur.fetchone()["id"]

        conn.commit()
        return row_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_option_by_id(option_id: int) -> Optional[dict]:

    rows = execute_query(
        "SELECT * FROM options WHERE id=%s",
        (option_id,),
    )

    return rows[0] if rows else None


def get_option_by_symbol(symbol: str) -> Optional[dict]:

    rows = execute_query(
        """
        SELECT *
        FROM options
        WHERE symbol=%s
        ORDER BY id DESC
        LIMIT 1
        """,
        (symbol,),
    )

    return rows[0] if rows else None


def get_all_options(
    layer: str = None,
    status: str = None,
) -> list[dict]:

    query = "SELECT * FROM options WHERE 1=1"
    params = []

    if layer:
        query += " AND layer=%s"
        params.append(layer)

    if status:
        query += " AND status=%s"
        params.append(status)

    query += " ORDER BY id DESC"

    return execute_query(query, tuple(params))


def get_open_options(layer: str = None) -> list[dict]:

    query = """
        SELECT *
        FROM options
        WHERE status='open'
    """

    params = []

    if layer:
        query += " AND layer=%s"
        params.append(layer)

    query += " ORDER BY id DESC"

    return execute_query(query, tuple(params))


def get_all_open_options() -> list[dict]:

    return execute_query(
        """
        SELECT *
        FROM options
        WHERE status='open'
        ORDER BY id DESC
        """
    )


def update_option(option_id: int, **kwargs) -> int:

    allowed_fields = {
        "entry_price",
        "qty",
        "notes",
        "layer",
        "iv_entry",
        "iv_atm_entry",
        "delta_entry",
        "gamma_entry",
        "theta_entry",
        "vega_entry",
        "status",
        "entry_date",
        "type",
        "strike",
        "expiry",
    }

    invalid = set(kwargs.keys()) - allowed_fields

    if invalid:
        raise ValueError(
            f"Недопустимые поля: {invalid}"
        )

    if not kwargs:
        return 0

    set_parts = ", ".join(
        f"{field}=%s"
        for field in kwargs
    )

    values = tuple(kwargs.values()) + (option_id,)

    return execute_write(
        f"""
        UPDATE options
        SET {set_parts}
        WHERE id=%s
        """,
        values,
    )


def close_option(
    option_id: int,
    close_price: float,
    close_reason: str = "manual",
    notes: str = None,
) -> None:

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT * FROM options WHERE id=%s",
                (option_id,),
            )

            row = cur.fetchone()

            if not row:
                return

            entry_price = float(row["entry_price"] or 0)
            qty = int(row["qty"])
            symbol = row["symbol"]

            pnl = round(
                (close_price - entry_price) * qty,
                2,
            )

            cur.execute(
                """
                UPDATE options
                SET status='closed'
                WHERE id=%s
                """,
                (option_id,),
            )

            cur.execute(
                """
                INSERT INTO closed_positions
                    (
                        option_id,
                        symbol,
                        close_date,
                        close_price,
                        entry_price,
                        pnl,
                        close_reason,
                        notes
                    )
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    option_id,
                    symbol,
                    date.today().isoformat(),
                    close_price,
                    entry_price,
                    pnl,
                    close_reason,
                    notes,
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# GREEKS
# ============================================================

def record_greeks(
    option_id: int,
    option_symbol: str,
    current_price: float = None,
    delta: float = None,
    gamma: float = None,
    theta: float = None,
    vega: float = None,
    iv: float = None,
    iv_atm: float = None,
    dte: int = None,
    intrinsic_value: float = None,
    unrealized_pnl: float = None,
    timestamp: str = None,
) -> int:

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO option_greeks_history
                    (
                        timestamp,
                        option_id,
                        option_symbol,
                        current_price,
                        delta,
                        gamma,
                        theta,
                        vega,
                        iv,
                        iv_atm,
                        dte,
                        intrinsic_value,
                        unrealized_pnl
                    )
                VALUES
                    (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                RETURNING id
                """,
                (
                    timestamp or datetime.now().strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    option_id,
                    option_symbol,
                    current_price,
                    delta,
                    gamma,
                    theta,
                    vega,
                    iv,
                    iv_atm,
                    dte,
                    intrinsic_value,
                    unrealized_pnl,
                ),
            )

            row_id = cur.fetchone()["id"]

        conn.commit()
        return row_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_latest_greeks(option_id: int) -> Optional[dict]:

    rows = execute_query(
        """
        SELECT *
        FROM option_greeks_history
        WHERE option_id=%s
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (option_id,),
    )

    return rows[0] if rows else None


def get_all_latest_greeks() -> list[dict]:

    return execute_query(
        """
        SELECT h.*
        FROM option_greeks_history h
        INNER JOIN (
            SELECT
                option_id,
                MAX(timestamp) AS max_ts
            FROM option_greeks_history
            GROUP BY option_id
        ) latest
        ON h.option_id = latest.option_id
        AND h.timestamp = latest.max_ts
        ORDER BY h.timestamp DESC
        """
    )


def get_greeks_trend(
    option_id: int,
    days: int = 7,
) -> list[dict]:

    return execute_query(
        """
        SELECT *
        FROM option_greeks_history
        WHERE option_id=%s
          AND timestamp >= NOW() - (%s * INTERVAL '1 day')
        ORDER BY timestamp
        """,
        (option_id, days),
    )


# ============================================================
# OPTION CHAIN
# ============================================================

def record_chain_snapshot(
    base_coin: str,
    spot_price: float,
    options_data: list[dict],
    timestamp: str = None,
) -> int:

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            timestamp = timestamp or datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            )

            for opt in options_data:

                cur.execute(
                    """
                    INSERT INTO option_chain_snapshot
                        (
                            timestamp,
                            base_coin,
                            spot_price,
                            symbol,
                            type,
                            strike,
                            expiry,
                            dte,
                            bid,
                            ask,
                            last_price,
                            mark_price,
                            volume,
                            open_interest,
                            iv,
                            delta,
                            gamma,
                            theta,
                            vega,
                            intrinsic_value
                        )
                    VALUES
                        (
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                    """,
                    (
                        timestamp,
                        base_coin,
                        spot_price,
                        opt.get("symbol"),
                        opt.get("type", "PUT"),
                        opt.get("strike", 0),
                        opt.get("expiry"),
                        opt.get("dte", 0),
                        opt.get("bid"),
                        opt.get("ask"),
                        opt.get("last_price"),
                        opt.get("mark_price"),
                        opt.get("volume"),
                        opt.get("open_interest"),
                        opt.get("iv"),
                        opt.get("delta"),
                        opt.get("gamma"),
                        opt.get("theta"),
                        opt.get("vega"),
                        opt.get("intrinsic_value"),
                    ),
                )

        conn.commit()
        return len(options_data)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_latest_chain_snapshot() -> list[dict]:

    rows = execute_query(
        """
        SELECT MAX(timestamp) AS ts
        FROM option_chain_snapshot
        """
    )

    if not rows or not rows[0]["ts"]:
        return []

    return execute_query(
        """
        SELECT *
        FROM option_chain_snapshot
        WHERE timestamp=%s
        """,
        (rows[0]["ts"],),
    )


# ============================================================
# RECOMMENDATIONS
# ============================================================

def add_recommendation(
    option_id: int = None,
    option_symbol: str = None,
    action: str = None,
    reason: str = None,
    confidence: float = None,
    llm_model: str = None,
    prompt_tokens: int = None,
    completion_tokens: int = None,
) -> int:

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO recommendations
                    (
                        timestamp,
                        option_id,
                        option_symbol,
                        action,
                        reason,
                        confidence,
                        llm_model,
                        llm_prompt_tokens,
                        llm_completion_tokens
                    )
                VALUES
                    (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                RETURNING id
                """,
                (
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    option_id,
                    option_symbol,
                    action,
                    reason,
                    confidence,
                    llm_model,
                    prompt_tokens,
                    completion_tokens,
                ),
            )

            row_id = cur.fetchone()["id"]

        conn.commit()
        return row_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def update_recommendation_status(
    rec_id: int,
    status: str,
    user_feedback: str = None,
) -> None:

    if user_feedback:
        execute_write(
            """
            UPDATE recommendations
            SET status=%s, user_feedback=%s
            WHERE id=%s
            """,
            (status, user_feedback, rec_id),
        )
    else:
        execute_write(
            """
            UPDATE recommendations
            SET status=%s
            WHERE id=%s
            """,
            (status, rec_id),
        )


def get_pending_recommendations() -> list[dict]:

    return execute_query(
        """
        SELECT *
        FROM recommendations
        WHERE status='pending'
        ORDER BY timestamp DESC
        """
    )


def get_all_recommendations(limit: int = 20) -> list[dict]:

    return execute_query(
        """
        SELECT *
        FROM recommendations
        ORDER BY timestamp DESC
        LIMIT %s
        """,
        (limit,),
    )


# ============================================================
# CLOSED POSITIONS
# ============================================================

def get_closed_positions() -> list[dict]:

    return execute_query(
        """
        SELECT *
        FROM closed_positions
        ORDER BY close_date DESC
        """
    )


# ============================================================
# STATISTICS
# ============================================================

def table_stats() -> dict:

    tables = [
        "options",
        "option_chain_snapshot",
        "option_greeks_history",
        "closed_positions",
        "buy_history",
        "sell_history",
        "portf",
        "recommendations",
        "pnl_profile_current",
    ]

    stats = {}

    for table in tables:

        rows = execute_query(
            f"SELECT COUNT(*) AS cnt FROM {table}"
        )

        stats[table] = (
            rows[0]["cnt"]
            if rows
            else 0
        )

    return stats


def check_db() -> None:

    print("📊 PostgreSQL: hedge_model")

    rows = execute_query(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
        ORDER BY table_name
        """
    )

    print(f"📋 Таблиц: {len(rows)}")

    for row in rows:

        table = row["table_name"]

        count = execute_query(
            f"SELECT COUNT(*) AS cnt FROM {table}"
        )

        print(
            f"   {table:30s}"
            f"{count[0]['cnt']:6d} строк"
        )


if __name__ == "__main__":
    check_db()
