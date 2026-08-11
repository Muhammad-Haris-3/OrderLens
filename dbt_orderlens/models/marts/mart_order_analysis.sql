-- The modelling table for M5 and M6. Grain: one delivery-eligible order. 96,470 rows.
--
-- FR-11 requires the delay effect to be estimated CONTROLLING FOR price, freight,
-- category, seller state, customer state and season. None of those live on
-- fct_orders, and Design Phase §8 is explicit about what to do when an analysis
-- needs a column that does not exist: add it to a mart, not to a script. A
-- regression whose control variables are assembled by an ad-hoc join in Python
-- is a regression nobody else can reproduce, and NFR-2 stops being true.
--
-- PRIMARY ITEM ATTRIBUTION. Category, seller and product dimensions are
-- order-level here, but 1,278 orders contain items from several sellers and many
-- contain several categories. Those attributes are taken from the
-- HIGHEST-PRICED item in the order, tie-broken on product_id for determinism.
-- That is a choice, not a fact: it is defensible because the dominant item drives
-- both the shipping profile and the customer's impression of the order, but
-- `is_single_seller` and `product_count` are carried so any analysis can restrict
-- to the unambiguous cases and check whether the choice mattered.
--
-- DISTANCE is computed here rather than in Python for the same reason. It is a
-- serious confounder — distance drives delay, and remote regions may also differ
-- in expectations — and FR-11's control set is weaker without it. Null for the
-- orders whose customer or seller ZIP prefix has no centroid (M2 F-07); the
-- regression drops those rows and reports how many.
--
-- M6 LEAKAGE: columns marked "post-delivery" in the schema yml may NOT be used by
-- the classifier. Everything else is known at purchase time. The allowlist is
-- enforced in the M6 script, not by discipline (Design Phase §8).

with primary_item as (

    select distinct on (i.order_id)
        i.order_id,
        i.product_id,
        i.seller_id,
        i.price                                             as primary_item_price
    from {{ ref('fct_order_items') }} i
    order by i.order_id, i.price desc, i.product_id

),

dominant_payment as (

    -- The instrument carrying the largest share of the order. Payment type is a
    -- plausible proxy for customer segment (boleto skews to the unbanked), so it
    -- earns a place in the control set even though FR-11 does not name it.
    select distinct on (order_id)
        order_id,
        payment_type,
        payment_installments
    from {{ ref('fct_payments') }}
    order by order_id, payment_value desc, payment_sequential

),

base as (

    select
        o.order_id,
        o.customer_unique_id,

        -- ---- Outcome ----------------------------------------------------
        o.review_score,
        o.is_low_score,
        o.reviewed_before_delivery,
        o.review_count,

        -- ---- Treatment (post-delivery — off-limits to M6) ----------------
        o.delay_days,
        o.is_late,
        o.delivery_days,
        o.seller_handover_days,
        o.carrier_transit_days,

        -- ---- Known at purchase time --------------------------------------
        o.estimated_days,
        o.purchase_date,
        o.purchased_at,

        o.order_item_total,
        o.order_freight_total,
        o.order_value,
        o.freight_ratio,
        o.item_count,
        o.product_count,
        o.seller_count,
        o.is_single_seller,

        p.category                                          as primary_category,
        p.category_source                                   as primary_category_source,
        p.product_weight_g                                  as primary_product_weight_g,
        p.product_volume_cm3                                as primary_product_volume_cm3,
        pi.primary_item_price,

        s.seller_id                                         as primary_seller_id,
        s.state                                             as seller_state,
        s.region                                            as seller_region,

        c.state                                             as customer_state,
        c.region                                            as customer_region,

        pay.payment_type,
        pay.payment_installments,

        gc.latitude                                         as customer_latitude,
        gc.longitude                                        as customer_longitude,
        gs.latitude                                         as seller_latitude,
        gs.longitude                                        as seller_longitude

    from {{ ref('fct_orders') }} o
    join primary_item pi                on pi.order_id = o.order_id
    join {{ ref('dim_products') }} p    on p.product_id = pi.product_id
    join {{ ref('dim_sellers') }} s     on s.seller_id = pi.seller_id
    join {{ ref('dim_customers') }} c   on c.customer_unique_id = o.customer_unique_id
    left join dominant_payment pay      on pay.order_id = o.order_id

    -- LEFT JOIN: 157 customer and 7 seller ZIP prefixes have no centroid (M2 F-07).
    left join {{ ref('dim_geography') }} gc on gc.zip_prefix = c.zip_prefix
    left join {{ ref('dim_geography') }} gs on gs.zip_prefix = s.zip_prefix

    -- The analysis population. Delivery measures are meaningless outside it.
    where o.is_delivery_eligible

)

select
    *,

    -- ---- Derived controls ------------------------------------------------

    -- Great-circle distance, kilometres. Null where either centroid is missing.
    case
        when customer_latitude is null or seller_latitude is null then null
        else round((
            2 * 6371 * asin(sqrt(
                power(sin(radians(seller_latitude - customer_latitude) / 2), 2)
                + cos(radians(customer_latitude)) * cos(radians(seller_latitude))
                * power(sin(radians(seller_longitude - customer_longitude) / 2), 2)
            ))
        )::numeric, 2)
    end                                                     as distance_km,

    customer_state = seller_state                           as is_same_state,

    extract(year  from purchased_at)::int                   as purchase_year,
    extract(month from purchased_at)::int                   as purchase_month,
    to_char(purchased_at, 'YYYY-MM')                        as purchase_year_month,
    extract(isodow from purchased_at)::int                  as purchase_day_of_week,
    extract(isodow from purchased_at)::int in (6, 7)        as purchased_on_weekend,

    -- Southern hemisphere. Getting this backwards would put Brazil's Christmas
    -- peak in "winter" and quietly invert every seasonal coefficient.
    case
        when extract(month from purchased_at) in (12, 1, 2) then 'summer'
        when extract(month from purchased_at) in (3, 4, 5)  then 'autumn'
        when extract(month from purchased_at) in (6, 7, 8)  then 'winter'
        else                                                     'spring'
    end                                                     as season

from base
