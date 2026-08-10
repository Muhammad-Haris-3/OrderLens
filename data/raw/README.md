# Raw data

The nine source CSVs are **not committed** — they're ~120 MB and the licence
covers redistribution poorly. Fetch them once, locally.

## Get the dataset

**Source:** Brazilian E-Commerce Public Dataset by Olist (Kaggle)
`https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce`

Download the archive and extract all nine CSVs directly into **this directory**
(`data/raw/`), flat — no nested folder.

## Expected files

| File | Approx. rows |
|---|---|
| `olist_orders_dataset.csv` | 99,441 |
| `olist_order_items_dataset.csv` | 112,650 |
| `olist_order_payments_dataset.csv` | 103,886 |
| `olist_order_reviews_dataset.csv` | 99,224 |
| `olist_customers_dataset.csv` | 99,441 |
| `olist_sellers_dataset.csv` | 3,095 |
| `olist_products_dataset.csv` | 32,951 |
| `product_category_name_translation.csv` | 71 |
| `olist_geolocation_dataset.csv` | 1,000,163 |

Row counts are approximate and are reconciled exactly at load time — the loader
records file-vs-database counts in `raw.load_log` and fails on any mismatch.

## Verify before loading

```bash
python scripts/load_raw.py --check
```

This confirms every file is present and every header matches what the raw schema
expects, without touching the database. Run it before the first load — a header
mismatch caught here is a minute; caught after `COPY` it's a silent column shift.
