-- OrderLens — RAW layer DDL
-- Canonical DDL for OrderLens_Design_Phase / SRS FR-1.
-- Run once against a fresh Neon database before the first load.
--
-- DESIGN DECISION — every column is TEXT.
-- The raw layer's job is source fidelity, not correctness. Typing here would
-- reject malformed rows at load time, which would silently hide exactly the
-- anomalies the M2 data-quality audit (FR-4) exists to find. Casting happens in
-- the dbt staging layer, where a failed cast is visible and testable.
-- No foreign keys, no NOT NULL, no CHECK constraints — for the same reason.

CREATE SCHEMA IF NOT EXISTS raw;

DROP TABLE IF EXISTS raw.orders;
CREATE TABLE raw.orders (
    order_id                      text,
    customer_id                   text,  -- NOTE: per-order key, NOT the person. See SRS 6.3 / risk R-1.
    order_status                  text,
    order_purchase_timestamp      text,
    order_approved_at             text,
    order_delivered_carrier_date  text,
    order_delivered_customer_date text,
    order_estimated_delivery_date text
);

DROP TABLE IF EXISTS raw.order_items;
CREATE TABLE raw.order_items (
    order_id            text,
    order_item_id       text,
    product_id          text,
    seller_id           text,
    shipping_limit_date text,
    price               text,
    freight_value       text
);

DROP TABLE IF EXISTS raw.order_payments;
CREATE TABLE raw.order_payments (
    order_id             text,
    payment_sequential   text,
    payment_type         text,
    payment_installments text,
    payment_value        text
);

DROP TABLE IF EXISTS raw.order_reviews;
CREATE TABLE raw.order_reviews (
    review_id               text,
    order_id                text,
    review_score            text,
    review_comment_title    text,
    review_comment_message  text,
    review_creation_date    text,
    review_answer_timestamp text
);

DROP TABLE IF EXISTS raw.customers;
CREATE TABLE raw.customers (
    customer_id              text,  -- per-order key
    customer_unique_id       text,  -- the actual person — use this for retention
    customer_zip_code_prefix text,
    customer_city            text,
    customer_state           text
);

DROP TABLE IF EXISTS raw.sellers;
CREATE TABLE raw.sellers (
    seller_id              text,
    seller_zip_code_prefix text,
    seller_city            text,
    seller_state           text
);

DROP TABLE IF EXISTS raw.products;
CREATE TABLE raw.products (
    product_id                 text,
    product_category_name      text,
    product_name_lenght        text,  -- [sic] — misspelled in source; preserved deliberately
    product_description_lenght text,  -- [sic]
    product_photos_qty         text,
    product_weight_g           text,
    product_length_cm          text,
    product_height_cm          text,
    product_width_cm           text
);

DROP TABLE IF EXISTS raw.product_category_translation;
CREATE TABLE raw.product_category_translation (
    product_category_name         text,
    product_category_name_english text
);

DROP TABLE IF EXISTS raw.geolocation;
CREATE TABLE raw.geolocation (
    geolocation_zip_code_prefix text,  -- NOT unique — many rows per prefix. See risk R-2.
    geolocation_lat             text,
    geolocation_lng             text,
    geolocation_city            text,
    geolocation_state           text
);

-- Load audit trail — one row per table per load, for row-count reconciliation (FR-1).
DROP TABLE IF EXISTS raw.load_log;
CREATE TABLE raw.load_log (
    id           serial PRIMARY KEY,
    table_name   text        NOT NULL,
    source_file  text        NOT NULL,
    rows_in_file integer     NOT NULL,
    rows_loaded  integer     NOT NULL,
    loaded_at    timestamptz NOT NULL DEFAULT now()
);
