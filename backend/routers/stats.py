"""Manager dashboard figures.

One endpoint returns the whole overview, so opening the dashboard is a single
request. Each metric is one aggregate query using FILTER clauses rather than a
query per time window.

Times are bucketed in Asia/Dubai, the shop's local day — otherwise "today"
would roll over at 4am local time.
"""
from fastapi import APIRouter, Depends

from db import fetch_all, fetch_one
from security import require_manager

router = APIRouter()

TZ = "Asia/Dubai"

# What counts as real money: not cancelled, not an abandoned online payment.
# A cash-on-delivery order counts from the moment it's placed.
REAL_ORDER = "not hidden and status <> 'cancelled' and (payment_method <> 'ziina' or payment_status = 'paid')"

# `created_at` bucketed into the shop's local day, and today's local date
_LOCAL_DAY = f"(created_at at time zone '{TZ}')::date"
_TODAY = f"(now() at time zone '{TZ}')::date"

LOW_STOCK_THRESHOLD = 5


@router.get("/overview")
def overview(_m=Depends(require_manager)):
    money = fetch_one(f"""
        select
          coalesce(sum(total) filter (where {_LOCAL_DAY} = {_TODAY}), 0)                as revenue_today,
          coalesce(sum(total) filter (where {_LOCAL_DAY} > {_TODAY} - 7), 0)            as revenue_7d,
          coalesce(sum(total) filter (where {_LOCAL_DAY} > {_TODAY} - 30), 0)           as revenue_30d,
          coalesce(sum(total), 0)                                                       as revenue_all,
          count(*) filter (where {_LOCAL_DAY} = {_TODAY})::int                          as orders_today,
          count(*) filter (where {_LOCAL_DAY} > {_TODAY} - 7)::int                      as orders_7d,
          count(*) filter (where {_LOCAL_DAY} > {_TODAY} - 30)::int                     as orders_30d,
          count(*)::int                                                                 as orders_all,
          coalesce(avg(total) filter (where {_LOCAL_DAY} > {_TODAY} - 30), 0)           as aov_30d
        from orders where {REAL_ORDER}
    """)

    # every status gets a row, including the ones with no orders yet
    by_status = fetch_all("""
        select s.status, count(o.id)::int as n
        from unnest(enum_range(null::order_status)) as s(status)
        left join orders o on o.status = s.status and not o.hidden
        group by s.status order by s.status
    """)

    customers = fetch_one(f"""
        select
          count(*)::int                                                            as total,
          count(*) filter (where (created_at at time zone '{TZ}')::date > {_TODAY} - 7)::int  as new_7d,
          count(*) filter (where (created_at at time zone '{TZ}')::date > {_TODAY} - 30)::int as new_30d
        from users where role = 'customer'
    """)

    top_products = fetch_all(f"""
        select oi.product_id, oi.name,
               sum(oi.qty)::int as qty,
               sum(oi.qty * oi.price) as revenue
        from order_items oi join orders o on o.id = oi.order_id
        where {REAL_ORDER} and (o.created_at at time zone '{TZ}')::date > {_TODAY} - 30
        group by oi.product_id, oi.name
        order by qty desc, revenue desc
        limit 8
    """)

    low_stock = fetch_all(
        """select id, name, stock from products
           where is_active = true and stock <= %s
           order by stock, name limit 12""",
        [LOW_STOCK_THRESHOLD],
    )

    # a 14-day series for the revenue sparkline, gap-filled so quiet days show zero
    daily = fetch_all(f"""
        select d::date as day,
               coalesce(sum(o.total), 0) as revenue,
               count(o.id)::int as orders
        from generate_series({_TODAY} - 13, {_TODAY}, interval '1 day') as d
        left join orders o on {_LOCAL_DAY} = d::date and {REAL_ORDER}
        group by d order by d
    """)

    return {
        "money": money,
        "by_status": by_status,
        "customers": customers,
        "top_products": top_products,
        "low_stock": low_stock,
        "daily": daily,
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
    }
