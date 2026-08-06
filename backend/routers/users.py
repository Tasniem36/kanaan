from fastapi import APIRouter, Depends, HTTPException

from db import fetch_all, fetch_one, execute
from security import require_manager

router = APIRouter()


@router.get("/clients")
def clients(_m=Depends(require_manager)):
    rows = fetch_all(
        """select u.id, u.full_name, u.email, u.phone, u.role, u.created_at,
                  count(o.id)::int                   as orders_count,
                  coalesce(sum(o.total), 0)::numeric as total_spent,
                  max(o.created_at)                  as last_order_at
           from users u
           left join orders o on o.user_id = u.id
           group by u.id
           order by last_order_at desc nulls last, u.created_at desc"""
    )
    return {"clients": rows}


@router.delete("/{uid}")
def delete_user(uid: str, mgr=Depends(require_manager)):
    if str(uid) == str(mgr["id"]):
        raise HTTPException(400, "You can't delete your own account")
    target = fetch_one("select id, role from users where id = %s", [uid])
    if not target:
        raise HTTPException(404, "User not found")
    if target["role"] == "manager":
        raise HTTPException(400, "Managers can't be deleted here")
    # orders reference user_id ON DELETE SET NULL, so order history is preserved
    # (just unlinked); addresses/messages/notifications cascade away.
    execute("delete from users where id = %s", [uid])
    return {"deleted": True}
