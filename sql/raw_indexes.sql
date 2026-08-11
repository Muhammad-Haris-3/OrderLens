-- OrderLens — RAW layer indexes
-- Run once after sql/raw_schema.sql and the first load.
--
-- WHY THIS EXISTS (added in M2).
-- The raw layer carries no constraints by design — see sql/raw_schema.sql. An
-- index is not a constraint: it asserts nothing about the data and rejects
-- nothing, so source fidelity is untouched. What it changes is time.
--
-- The M2 audit joins raw.geolocation (1,000,163 rows) against customers and
-- sellers to measure ZIP coverage. Without an index that is a repeated
-- sequential scan of a million rows and the audit runs for minutes rather than
-- seconds. The same join keys are hit again by every dbt staging model in M3,
-- so the cost is paid once here and recovered on every build afterwards
-- (SRS NFR-4: full rebuild under 10 minutes on free-tier Postgres; risk R-4).
--
-- Idempotent: IF NOT EXISTS throughout, so re-running is free.
-- The loader TRUNCATEs rather than DROPs, so these survive a reload.

-- Join keys used by the audit and by every M3 staging/mart model.
CREATE INDEX IF NOT EXISTS ix_orders_order_id        ON raw.orders (order_id);
CREATE INDEX IF NOT EXISTS ix_orders_customer_id     ON raw.orders (customer_id);
CREATE INDEX IF NOT EXISTS ix_orders_status          ON raw.orders (order_status);

CREATE INDEX IF NOT EXISTS ix_order_items_order_id   ON raw.order_items (order_id);
CREATE INDEX IF NOT EXISTS ix_order_items_product_id ON raw.order_items (product_id);
CREATE INDEX IF NOT EXISTS ix_order_items_seller_id  ON raw.order_items (seller_id);

CREATE INDEX IF NOT EXISTS ix_order_payments_order_id ON raw.order_payments (order_id);

CREATE INDEX IF NOT EXISTS ix_order_reviews_order_id  ON raw.order_reviews (order_id);
CREATE INDEX IF NOT EXISTS ix_order_reviews_review_id ON raw.order_reviews (review_id);

CREATE INDEX IF NOT EXISTS ix_customers_customer_id   ON raw.customers (customer_id);
CREATE INDEX IF NOT EXISTS ix_customers_unique_id     ON raw.customers (customer_unique_id);
CREATE INDEX IF NOT EXISTS ix_customers_zip           ON raw.customers (customer_zip_code_prefix);

CREATE INDEX IF NOT EXISTS ix_sellers_seller_id       ON raw.sellers (seller_id);
CREATE INDEX IF NOT EXISTS ix_sellers_zip             ON raw.sellers (seller_zip_code_prefix);

CREATE INDEX IF NOT EXISTS ix_products_product_id     ON raw.products (product_id);
CREATE INDEX IF NOT EXISTS ix_products_category       ON raw.products (product_category_name);

CREATE INDEX IF NOT EXISTS ix_category_translation_pt ON raw.product_category_translation (product_category_name);

-- The expensive one: 1,000,163 rows, 19,015 distinct prefixes (M1 §4).
CREATE INDEX IF NOT EXISTS ix_geolocation_zip         ON raw.geolocation (geolocation_zip_code_prefix);
