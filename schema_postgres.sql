BEGIN;

CREATE TABLE IF NOT EXISTS options (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL UNIQUE,
    type            TEXT NOT NULL,
    strike          DOUBLE PRECISION NOT NULL,
    expiry          TEXT NOT NULL,
    qty             INTEGER NOT NULL DEFAULT 1,
    entry_date      TEXT,
    entry_price     DOUBLE PRECISION,
    total_cost      DOUBLE PRECISION,
    iv_entry        DOUBLE PRECISION,
    iv_atm_entry    DOUBLE PRECISION,
    delta_entry     DOUBLE PRECISION,
    gamma_entry     DOUBLE PRECISION,
    theta_entry     DOUBLE PRECISION,
    vega_entry      DOUBLE PRECISION,
    layer           TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS option_chain_snapshot (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    base_coin       TEXT NOT NULL,
    spot_price      DOUBLE PRECISION NOT NULL,
    symbol          TEXT NOT NULL,
    type            TEXT NOT NULL,
    strike          DOUBLE PRECISION NOT NULL,
    expiry          TEXT NOT NULL,
    dte             INTEGER,
    bid             DOUBLE PRECISION,
    ask             DOUBLE PRECISION,
    last_price      DOUBLE PRECISION,
    mark_price      DOUBLE PRECISION,
    volume          DOUBLE PRECISION,
    open_interest   DOUBLE PRECISION,
    iv              DOUBLE PRECISION,
    delta           DOUBLE PRECISION,
    gamma           DOUBLE PRECISION,
    theta           DOUBLE PRECISION,
    vega            DOUBLE PRECISION,
    intrinsic_value DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS option_greeks_history (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    option_id       BIGINT NOT NULL,
    option_symbol   TEXT NOT NULL,
    current_price   DOUBLE PRECISION,
    delta           DOUBLE PRECISION,
    gamma           DOUBLE PRECISION,
    theta           DOUBLE PRECISION,
    vega            DOUBLE PRECISION,
    iv              DOUBLE PRECISION,
    iv_atm          DOUBLE PRECISION,
    dte             INTEGER,
    intrinsic_value DOUBLE PRECISION,
    unrealized_pnl  DOUBLE PRECISION,
    CONSTRAINT fk_greeks_option
        FOREIGN KEY (option_id)
        REFERENCES options(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS closed_positions (
    id              BIGSERIAL PRIMARY KEY,
    option_id       BIGINT NOT NULL,
    symbol          TEXT NOT NULL,
    close_date      TEXT NOT NULL,
    close_price     DOUBLE PRECISION NOT NULL,
    entry_price     DOUBLE PRECISION NOT NULL,
    pnl             DOUBLE PRECISION NOT NULL,
    close_reason    TEXT,
    notes           TEXT,
    CONSTRAINT fk_closed_option
        FOREIGN KEY (option_id)
        REFERENCES options(id)
);

CREATE TABLE IF NOT EXISTS buy_history (
    id              BIGSERIAL PRIMARY KEY,
    buy_date        TEXT NOT NULL,
    qty             DOUBLE PRECISION NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    total           DOUBLE PRECISION NOT NULL,
    symbol          TEXT NOT NULL DEFAULT 'SOL',
    notes           TEXT,
    closed          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sell_history (
    id              BIGSERIAL PRIMARY KEY,
    buy_id          BIGINT NOT NULL,
    symbol          TEXT NOT NULL,
    qty             DOUBLE PRECISION NOT NULL,
    buy_price       DOUBLE PRECISION NOT NULL,
    sell_price      DOUBLE PRECISION NOT NULL,
    total           DOUBLE PRECISION NOT NULL,
    pnl             DOUBLE PRECISION NOT NULL,
    sell_date       TEXT NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS Portf (
    id              BIGSERIAL PRIMARY KEY,
    token           TEXT NOT NULL,
    qty             DOUBLE PRECISION NOT NULL,
    avg_price       DOUBLE PRECISION NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS recommendations (
    id                  BIGSERIAL PRIMARY KEY,
    timestamp           TEXT NOT NULL,
    option_id           BIGINT,
    option_symbol       TEXT,
    action              TEXT NOT NULL,
    reason              TEXT NOT NULL,
    confidence          DOUBLE PRECISION,
    llm_model           TEXT,
    llm_prompt_tokens   INTEGER,
    llm_completion_tokens INTEGER,
    status              TEXT NOT NULL DEFAULT 'pending',
    user_feedback       TEXT,
    CONSTRAINT fk_rec_option
        FOREIGN KEY (option_id)
        REFERENCES options(id)
);

CREATE TABLE IF NOT EXISTS pnl_profile_current (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    target_pnl      DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_gh_option
    ON option_greeks_history(option_id);

CREATE INDEX IF NOT EXISTS idx_gh_time
    ON option_greeks_history(timestamp);

CREATE INDEX IF NOT EXISTS idx_ocs_time
    ON option_chain_snapshot(timestamp);

CREATE INDEX IF NOT EXISTS idx_ocs_symbol
    ON option_chain_snapshot(symbol);

CREATE INDEX IF NOT EXISTS idx_rec_option
    ON recommendations(option_id);

CREATE INDEX IF NOT EXISTS idx_rec_time
    ON recommendations(timestamp);

COMMIT;
