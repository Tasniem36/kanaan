from fastapi import APIRouter, Depends, Request

from db import fetch_all
from security import require_manager

router = APIRouter()


# GET /api/audit — admin only: recent activity, filterable by action / email / date range
@router.get("")
def list_audit(request: Request, _m=Depends(require_manager)):
    q = request.query_params
    try:
        limit = min(int(q.get("limit", 200)), 500)
    except ValueError:
        limit = 200
    conds, params = [], []
    if q.get("action"):
        conds.append("a.action = %s")
        params.append(q["action"])
    if q.get("email"):
        conds.append("u.email ilike %s")
        params.append(f"%{q['email'].strip()}%")
    if q.get("from"):
        conds.append("a.created_at >= %s::date")
        params.append(q["from"])
    if q.get("to"):
        conds.append("a.created_at < (%s::date + 1)")  # inclusive of the whole day
        params.append(q["to"])
    where = ("where " + " and ".join(conds)) if conds else ""
    rows = fetch_all(
        f"""select a.id, a.action, a.detail, a.ip, a.created_at, u.email, u.full_name, u.role
            from audit_logs a left join users u on u.id = a.user_id
            {where} order by a.created_at desc limit %s""",
        params + [limit],
    )
    return {"logs": rows}
