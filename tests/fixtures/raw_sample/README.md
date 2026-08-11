# CI sample fixture

**Generated. Do not edit by hand.** Regenerate with:

```bash
python scripts/make_sample.py
```

Regenerating needs the full dataset in `data/raw/` — see
[data/raw/README.md](../../../data/raw/README.md).

---

## What this is

A referentially-complete sample of the nine Olist source CSVs, committed so that
CI can load a warehouse and run the **dbt data tests** on every push (SRS NFR-3).

Before this existed, CI could only check that the dbt project *parsed*. The 193
data tests — including the seven bespoke ones that guard risks R-1 and R-2 and
the M2 findings — ran on one laptop against one warehouse. A test suite that runs
somewhere other than CI is a test suite that will eventually stop running.

| Table | Rows |
|---|---|
| `orders` | 1,550 |
| `order_items` | 1,782 |
| `order_payments` | 1,629 |
| `order_reviews` | 1,564 |
| `customers` | 1,550 |
| `products` | 1,361 |
| `sellers` | 641 |
| `product_category_translation` | 71 (complete) |
| `geolocation` | 6,624 |

~1.5 MB total.

## How it was built, and why not simply `head -n 1000`

Sampling rows independently from nine files produces items whose order does not
exist and orders whose customer does not exist. Every `relationships` test then
fails for reasons that have nothing to do with the code under test.

So the sample is **grown outward** from a seed set of orders:

```
orders  ->  their items, payments, reviews, and customer
        ->  the products and sellers those items reference
        ->  the geolocation prefixes those customers and sellers reference
```

Three properties are preserved deliberately, because losing any of them would
silently disable a test while leaving CI green:

1. **All eight order statuses.** `created` has 5 rows in 99,441; a uniform sample
   would miss it and `accepted_values` would never exercise it. The seed is
   stratified by status.

2. **Repeat customers — 194 of them.** Only 3.12% of people order twice, so a
   1.5% sample of orders lands *both* orders of a repeat customer essentially
   never. The first attempt produced a fixture with exactly zero, which makes
   `assert_repeat_customers_exist` (risk R-1) impossible to satisfy at any
   threshold — and the tempting fix is to stop running it in CI, which is
   precisely the failure it guards. Repeat customers are now included on purpose,
   with all of their orders, and the sample is closed over `customer_unique_id`.

3. **More than one geolocation row per ZIP prefix.** Otherwise the 52.6× fan-out
   that `stg_geolocation` exists to kill is not represented, and its uniqueness
   test proves nothing.

`tests/test_sample_fixture.py` asserts all three on every push, because the
fixture is committed and can drift from the sampler that produced it.

## Deviations from the full dataset

- **Geolocation is capped at 4 rows per prefix** (the real table averages 52.6).
  The fan-out behaviour is preserved; the volume is not. `source_point_count` in
  `stg_geolocation` is therefore much smaller here than in the warehouse.
- **Row counts differ from every figure in the milestone documents.** Those come
  from the full warehouse. Tests that assert absolute counts are parameterised —
  see `min_repeat_customers` in `dbt_project.yml`.

## Provenance and licence

Derived from the Brazilian E-Commerce Public Dataset by Olist, released for
research under an open licence (SRS §3). It contains no direct personal
identifiers — customer keys are anonymised hashes and geolocation is aggregated
to ZIP prefix — which is what makes committing a derived sample acceptable here.
