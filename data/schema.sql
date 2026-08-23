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

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    sku_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    category TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS payment_gateway_events (
    gateway_event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    transaction_id TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS delivery_proofs (
    proof_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    recipient TEXT,
    proof_type TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    detail TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS delivery_addresses (
    address_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    city TEXT NOT NULL,
    masked_address TEXT NOT NULL,
    contact_suffix TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cancellation_requests (
    cancellation_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    accepted_at TEXT,
    reason TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS return_requests (
    return_request_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    order_item_id TEXT NOT NULL REFERENCES order_items(order_item_id),
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    item_condition TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS warehouse_pack_records (
    pack_record_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    sku_id TEXT NOT NULL,
    packed_quantity INTEGER NOT NULL,
    scanned_at TEXT NOT NULL,
    station_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS claim_attachments (
    attachment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    attachment_type TEXT NOT NULL,
    uri TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS order_fee_records (
    fee_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    fee_type TEXT NOT NULL,
    expected_amount REAL NOT NULL,
    charged_amount REAL NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS charge_dispute_records (
    charge_claim_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    payment_id TEXT,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS return_tracking_events (
    tracking_event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS exchange_options (
    exchange_option_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    target_sku TEXT,
    price_difference REAL NOT NULL DEFAULT 0,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS order_change_options (
    change_option_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS product_catalog_records (
    product_record_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    attributes_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS inventory_records (
    inventory_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    sku_id TEXT NOT NULL,
    available_quantity INTEGER NOT NULL,
    restock_at TEXT,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS price_records (
    price_record_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    purchase_price REAL,
    current_price REAL NOT NULL,
    competitor_price REAL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS promotion_records (
    promotion_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    code TEXT NOT NULL,
    expires_at TEXT,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS shipping_option_records (
    shipping_option_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    option_name TEXT NOT NULL,
    amount REAL NOT NULL,
    estimated_days INTEGER NOT NULL,
    region TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS membership_records (
    membership_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    level TEXT NOT NULL,
    credit_balance REAL NOT NULL,
    benefits_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS checkout_events (
    checkout_event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cart_events (
    cart_event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS search_events (
    search_event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    query_text TEXT NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS site_health_events (
    health_event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    error_rate REAL NOT NULL,
    p95_ms INTEGER NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS review_tasks (
    review_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL UNIQUE REFERENCES cases(case_id),
    reason TEXT NOT NULL,
    conflict_evidence_json TEXT NOT NULL,
    status TEXT NOT NULL,
    system_decision TEXT NOT NULL,
    system_responsible_party TEXT NOT NULL,
    reviewer_decision TEXT,
    reviewer_responsible_party TEXT,
    reviewer_comment TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
