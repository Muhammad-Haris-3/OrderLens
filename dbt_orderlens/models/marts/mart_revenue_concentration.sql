-- FR-8 — revenue concentration. Grain: (dimension, dimension_key).
--
-- One model rather than three, because the ranking and cumulative-share logic is
-- identical for category, seller and state, and three copies of a window
-- function is three places for the denominator to end up subtly different. The
-- dashboard filters on `dimension`.
--
-- SELLER REVENUE IS MEASURED AT ITEM GRAIN, and so is category revenue: an order
-- can contain items from several sellers and several categories, so attributing
-- a whole order's value to either would double-count. State revenue is measured
-- at ORDER grain, because a customer's state is a property of the order, not of
-- the item — summing item values there would be correct but pointlessly indirect.
--
-- pct_late is carried alongside revenue on purpose. BQ-4 asks which segments
-- concentrate the damage, and that is a question about revenue AND failure rate
-- together: a segment with 4% of revenue and a 12% late rate is a different
-- proposition from one with 37% of revenue and a 4.5% late rate.
--
-- Late rates on the seller dimension use SINGLE-SELLER ORDERS ONLY (M2 F-12).
-- 1,278 orders contain items from several sellers but carry one delivery
-- outcome; attributing that outcome to each seller involved would blame every
-- one of them for a failure at most one of them caused.

with by_category as (

    select
        'category'                                          as dimension,
        p.category                                          as dimension_key,
        sum(i.item_value)                                   as revenue,
        count(distinct i.order_id)                          as orders,
        count(*)                                            as items,
        count(*) filter (where i.is_late)                   as late_items,
        count(*) filter (where i.is_delivery_eligible)      as delivery_eligible_items,
        avg(i.review_score)                                 as mean_review_score
    from {{ ref('fct_order_items') }} i
    join {{ ref('dim_products') }} p on p.product_id = i.product_id
    group by p.category

),

by_seller as (

    select
        'seller',
        i.seller_id,
        sum(i.item_value),
        count(distinct i.order_id),
        count(*),
        count(*) filter (where i.is_late and i.is_single_seller),
        count(*) filter (where i.is_delivery_eligible and i.is_single_seller),
        avg(i.review_score) filter (where i.is_single_seller)
    from {{ ref('fct_order_items') }} i
    group by i.seller_id

),

by_state as (

    select
        'customer_state',
        c.state,
        sum(o.order_value),
        count(*),
        count(*),
        count(*) filter (where o.is_late),
        count(*) filter (where o.is_delivery_eligible),
        avg(o.review_score)
    from {{ ref('fct_orders') }} o
    join {{ ref('dim_customers') }} c on c.customer_unique_id = o.customer_unique_id
    where o.order_value is not null
    group by c.state

),

combined as (
    select * from by_category
    union all select * from by_seller
    union all select * from by_state
)

select
    dimension,
    dimension_key,

    round(revenue, 2)                                       as revenue,
    orders,
    items,

    row_number() over (partition by dimension order by revenue desc)
                                                            as revenue_rank,
    count(*)      over (partition by dimension)             as members_in_dimension,

    round(100.0 * revenue / sum(revenue) over (partition by dimension), 4)
                                                            as pct_of_revenue,
    round(100.0 * sum(revenue) over (
              partition by dimension
              order by revenue desc
              rows between unbounded preceding and current row
          ) / sum(revenue) over (partition by dimension), 4)
                                                            as cumulative_pct_of_revenue,

    round(100.0 * late_items / nullif(delivery_eligible_items, 0), 2)
                                                            as pct_late,
    round(mean_review_score, 3)                             as mean_review_score

from combined
