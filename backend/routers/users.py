from fastapi import APIRouter, Depends

from db import fetch_all
from security import require_manager

router = APIRouter()


@router.get("/clients")
def clients(_m=Depends(require_manager)):
    rows = fetch_all(
        """select u.id, u.full_name, u.email, u.phone, u.created_at,
                  count(o.id)::int                   as orders_count,
                  coalesce(sum(o.total), 0)::numeric as total_spent,
                  max(o.created_at)                  as last_order_at
           from users u
           left join orders o on o.user_id = u.id
           where u.role = 'customer'
           group by u.id
           order by last_order_at desc nulls last, u.created_at desc"""
    )
    return {"clients": rows}
