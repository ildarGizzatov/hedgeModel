-- ============================================================
-- HedgeModel — SQLite Schema
-- ============================================================
-- Назначение: история Greeks, IV, option chain snapshots,
--             рекомендации LLM, история позиций.
--
-- CSV-файлы остаются как "быстрое чтение", но источник
-- истины для анализа → SQLite.
-- ============================================================

-- ----------------------------------------
-- 1. Опционы (реестр, справочник)
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS options (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL UNIQUE,   -- "SOL-31JUL26-54-P-USDT"
    type            TEXT NOT NULL,           -- PUT / CALL
    strike          REAL NOT NULL,
    expiry          TEXT NOT NULL,           -- ISO date
    qty             INTEGER NOT NULL DEFAULT 1,
    entry_date      TEXT,                    -- ISO date
    entry_price     REAL,
    total_cost      REAL,
    iv_entry        REAL,
    iv_atm_entry    REAL,
    delta_entry     REAL,
    gamma_entry     REAL,
    theta_entry     REAL,
    vega_entry      REAL,
    layer           TEXT,                    -- anchor / adaptation / active
    status          TEXT NOT NULL DEFAULT 'open',  -- open / closed / expired
    notes           TEXT
);

-- ----------------------------------------
-- 2. Опционный чейн (полный снимок рынка по каждому fetch)
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS option_chain_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,            -- ISO datetime, момент fetch
    base_coin       TEXT NOT NULL,            -- SOL
    spot_price      REAL NOT NULL,

    -- Поля опциона (один снимок = одна строка)
    symbol          TEXT NOT NULL,
    type            TEXT NOT NULL,
    strike          REAL NOT NULL,
    expiry          TEXT NOT NULL,
    dte             INTEGER,                  -- days to expiry

    -- Рыночные данные
    bid             REAL,
    ask             REAL,
    last_price      REAL,
    mark_price      REAL,
    volume          REAL,
    open_interest   REAL,

    -- Greeks
    iv              REAL,
    delta           REAL,
    gamma           REAL,
    theta           REAL,
    vega            REAL,

    -- Дополнительная информация
    intrinsic_value REAL
);

-- ----------------------------------------
-- 3. История Greeks (инкрементная, для LLM-анализа)
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS option_greeks_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,            -- ISO datetime
    option_id       INTEGER NOT NULL,         -- FK → options.id
    option_symbol   TEXT NOT NULL,            -- дубликат для удобных JOIN-less запросов

    current_price   REAL,
    delta           REAL,
    gamma           REAL,
    theta           REAL,
    vega            REAL,
    iv              REAL,
    iv_atm          REAL,
    dte             INTEGER,
    intrinsic_value REAL,

    -- PnL от entry
    unrealized_pnl  REAL,

    FOREIGN KEY (option_id) REFERENCES options(id) ON DELETE CASCADE
);

-- ----------------------------------------
-- 4. Закрытые позиции опционов
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS closed_positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    option_id       INTEGER NOT NULL,         -- FK → options.id
    symbol          TEXT NOT NULL,

    close_date      TEXT NOT NULL,            -- ISO date
    close_price     REAL NOT NULL,
    entry_price     REAL NOT NULL,
    pnl             REAL NOT NULL,

    close_reason    TEXT,                     -- auto / manual / roll
    notes           TEXT,

    FOREIGN KEY (option_id) REFERENCES options(id)
);

-- ----------------------------------------
-- 5. История покупок SOL
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS buy_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    buy_date        TEXT NOT NULL,            -- ISO date
    qty             REAL NOT NULL,            -- >0 покупка, <0 продажа
    price           REAL NOT NULL,
    total           REAL NOT NULL,
    symbol          TEXT NOT NULL DEFAULT 'SOL',
    notes           TEXT,
    closed          INTEGER NOT NULL DEFAULT 0 -- 0=open, 1=closed (soft delete)
);

-- ----------------------------------------
-- 5b. Портфель других активов (JUPSOL и т.д.)
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS Portf (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token           TEXT NOT NULL,
    qty             REAL NOT NULL,
    avg_price       REAL NOT NULL,
    notes           TEXT
);

-- ----------------------------------------
-- 6. Рекомендации LLM
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS recommendations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    option_id       INTEGER,                  -- FK → options.id (NULL для общих рекомендаций)
    option_symbol   TEXT,

    action          TEXT NOT NULL,            -- buy / sell / hold / roll / hedge
    reason          TEXT NOT NULL,
    confidence      REAL,                     -- 0.0 — 1.0

    -- Метаданные модели
    llm_model       TEXT,
    llm_prompt_tokens   INTEGER,
    llm_completion_tokens INTEGER,

    -- Статус
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending / accepted / rejected
    user_feedback   TEXT,                     -- комментарий пользователя

    FOREIGN KEY (option_id) REFERENCES options(id)
);

-- ----------------------------------------
-- Индексы
-- ----------------------------------------
CREATE INDEX IF NOT EXISTS idx_gh_option   ON option_greeks_history(option_id);
CREATE INDEX IF NOT EXISTS idx_gh_time     ON option_greeks_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_ocs_time    ON option_chain_snapshot(timestamp);
CREATE INDEX IF NOT EXISTS idx_ocs_symbol  ON option_chain_snapshot(symbol);
CREATE INDEX IF NOT EXISTS idx_rec_option  ON recommendations(option_id);
CREATE INDEX IF NOT EXISTS idx_rec_time    ON recommendations(timestamp);
