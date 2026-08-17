import ipaddress
import threading

import requests
from fastapi import APIRouter, Depends, Request

from db import fetch_all
from security import require_manager

router = APIRouter()

# ip → "City, Country" (or None), resolved lazily when the audit page asks. Cached
# for the process lifetime so the same IP isn't looked up twice.
_geo_cache = {}
_geo_lock = threading.Lock()


def _is_public(ip):
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


# GET /api/audit — admin only: recent activity, filterable by action / email / date range
@router.get("")
def list_audit(request: Request, _m=Depends(require_manager)):
    q = request.query_params
    try:
        limit = min(int(q.get("limit", 200)), 500)
    except ValueError:
        limit = 200
    # this is the *customer* activity log — never show the manager's own actions.
    # (u.role is null for guests, so `is distinct from` keeps guest visits.)
    conds, params = ["u.role is distinct from 'manager'"], []
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
        f"""select a.id, a.action, a.detail, a.ip, a.page, a.created_at, u.email, u.full_name, u.role
            from audit_logs a left join users u on u.id = a.user_id
            {where} order by a.created_at desc limit %s""",
        params + [limit],
    )
    return {"logs": rows}


# GET /api/audit/top-products — admin only: the products shoppers opened most,
# from the product_view trail. Honours the same from/to date range as the log.
@router.get("/top-products")
def top_products(request: Request, _m=Depends(require_manager)):
    q = request.query_params
    try:
        limit = min(int(q.get("limit", 10)), 50)
    except ValueError:
        limit = 10
    conds = ["a.action = 'product_view'", "a.detail->>'product_id' is not null"]
    params = []
    if q.get("from"):
        conds.append("a.created_at >= %s::date")
        params.append(q["from"])
    if q.get("to"):
        conds.append("a.created_at < (%s::date + 1)")
        params.append(q["to"])
    where = "where " + " and ".join(conds)
    rows = fetch_all(
        f"""select a.detail->>'product_id' as product_id,
                   max(a.detail->>'name') as name,
                   count(*)::int as views
            from audit_logs a {where}
            group by a.detail->>'product_id'
            order by views desc, name limit %s""",
        params + [limit],
    )
    return {"products": rows}


# GET /api/audit/geo?ips=a,b,c — admin only: resolve IPs to "City, Country".
# Best-effort via ip-api.com (free, HTTP-only, server-side); private/unknown → null.
@router.get("/geo")
def audit_geo(request: Request, _m=Depends(require_manager)):
    raw = request.query_params.get("ips", "")
    ips = [ip.strip() for ip in raw.split(",") if ip.strip()]
    result, todo = {}, []
    for ip in ips:
        with _geo_lock:
            if ip in _geo_cache:
                result[ip] = _geo_cache[ip]
            else:
                todo.append(ip)
    resolvable = [ip for ip in todo if _is_public(ip)][:100]  # ip-api batch cap
    if resolvable:
        try:
            resp = requests.post(
                "http://ip-api.com/batch?fields=query,status,city,country",
                json=resolvable, timeout=4,
            )
            for item in resp.json():
                ip = item.get("query")
                loc = ", ".join(x for x in (item.get("city"), item.get("country")) if x) \
                    if item.get("status") == "success" else None
                with _geo_lock:
                    _geo_cache[ip] = loc
                result[ip] = loc
        except Exception as e:  # offline / rate-limited → leave those unresolved
            print("[audit.geo]", e)
    for ip in todo:
        result.setdefault(ip, None)  # private or failed lookups
    return {"geo": result}
