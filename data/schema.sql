PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    region TEXT NOT NULL,
    business_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    current_time TEXT NOT NULL,
    conversation_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    region TEXT NOT NULL,
    business_type TEXT NOT NULL,
    status TEXT NOT NULL,
    paid_amount REAL NOT NULL,
    currency TEXT NOT NULL,
    created_at TEXT NOT NULL,
    promised_delivery_at TEXT,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS logistics_events (
    event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    detail TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    event_type TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS refunds (
    refund_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    amount REAL NOT NULL,
    status TEXT NOT NULL,
    initiated_at TEXT NOT NULL,
    completed_at TEXT,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS after_sales_cases (
    after_sales_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    approved_at TEXT,
    reason TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    region TEXT NOT NULL,
    business_type TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    rules_json TEXT NOT NULL,
    source_summary TEXT NOT NULL,
    PRIMARY KEY (policy_id, version)
);
