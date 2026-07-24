from fastapi import APIRouter, Depends, Request

from db import fetch_all
from security import require_manager

router = APIRouter()


# GET /api/audit — admin only: recent customer activity. ?action= filter, ?limit=
@router.get("")
def list_audit(request: Request, _m=Depends(require_manager)):
    try:
        limit = min(int(request.query_params.get("limit", 200)), 500)
    except ValueError:
        limit = 200
    action = request.query_params.get("action")
    if action:
        rows = fetch_all(
            """select a.id, a.action, a.detail, a.ip, a.created_at, u.email, u.full_name
               from audit_logs a left join users u on u.id = a.user_id
               where a.action = %s order by a.created_at desc limit %s""",
            [action, limit],
        )
    else:
        rows = fetch_all(
            """select a.id, a.action, a.detail, a.ip, a.created_at, u.email, u.full_name
               from audit_logs a left join users u on u.id = a.user_id
               order by a.created_at desc limit %s""",
            [limit],
        )
    return {"logs": rows}
