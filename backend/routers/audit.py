import ipaddress
import threading

import requests
from fastapi import APIRouter, Body, Depends, Request

from audit import log_action
from db import fetch_all
from ratelimit import rate_limit
from security import optional_user, require_manager

# What the storefront itself may add to the trail. Everything else in the log is
# written server-side from a real action; these are moments only the browser knows
# about. Whitelisted, so a page can't invent action names.
CLIENT_EVENTS = {"checkout_opened"}

# The failures that mean a customer is stuck. Kept in one place: the dashboard's
# follow-up list and the drop-off figure both read from it.
STRUGGLE_ACTIONS = ("login_failed", "verify_failed", "password_reset_failed",
                    "promo_invalid", "checkout_failed", "out_of_stock")

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
    # This is the *customer* activity log. log_action() no longer writes staff rows
    # at all, but rows from before that still exist, so the filter stays.
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
        f"""select a.id, a.action, a.detail, a.ip, a.page, a.api, a.created_at, u.email, u.full_name, u.role
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


# GET /api/audit/sources — admin only: where visitors came from, grouped by campaign,
# read off the tags on the landing URL that visit rows record. Same date range as the
# log. Direct visits (no tags) are counted together under a null source.
@router.get("/sources")
def visit_sources(request: Request, _m=Depends(require_manager)):
    q = request.query_params
    try:
        limit = min(int(q.get("limit", 12)), 50)
    except ValueError:
        limit = 12
    conds, params = ["a.action = 'visit'"], []
    if q.get("from"):
        conds.append("a.created_at >= %s::date")
        params.append(q["from"])
    if q.get("to"):
        conds.append("a.created_at < (%s::date + 1)")
        params.append(q["to"])
    where = "where " + " and ".join(conds)
    rows = fetch_all(
        f"""select a.detail->'from'->>'source'   as source,
                   a.detail->'from'->>'medium'   as medium,
                   a.detail->'from'->>'campaign' as campaign,
                   count(*)::int as visits,
                   -- one browser is one visitor; the address is only a fallback for
                   -- rows written before the vid cookie existed
                   count(distinct coalesce(a.user_id::text, a.visitor, a.ip)) as visitors
            from audit_logs a {where}
            group by 1, 2, 3
            order by visits desc
            limit %s""",
        params + [limit],
    )
    return {"sources": rows}

# POST /api/audit/event — the storefront reporting something only it can see, such as
# the checkout form being opened (which, against order_placed, is the drop-off rate).
# Whitelisted and rate limited: this is the one place the log takes client input.
@router.post("/event")
def client_event(request: Request, user=Depends(optional_user), payload: dict = Body(default={})):
    event = str((payload or {}).get("event") or "")
    if event not in CLIENT_EVENTS:
        return {"ok": False}
    rate_limit(request, bucket="audit_event", limit=30, window=60, key=(user or {}).get("id"))
    detail = payload.get("detail") if isinstance(payload.get("detail"), dict) else None
    log_action(user_id=(user or {}).get("id"), action=event,
               detail={k: v for k, v in (detail or {}).items()
                       if k in ("items", "total")} or None,
               request=request)
    return {"ok": True}


# GET /api/audit/struggling — admin only: customers worth following up, either because
# they hit repeated failures or because they opened the checkout and never ordered.
# Grouped per person (per IP for guests), newest trouble first.
@router.get("/struggling")
def struggling(request: Request, _m=Depends(require_manager)):
    q = request.query_params
    try:
        hours = min(max(int(q.get("hours", 24)), 1), 24 * 30)
    except ValueError:
        hours = 24
    rows = fetch_all(
        """with recent as (
               select coalesce(a.user_id::text, 'v:' || a.visitor, 'ip:' || a.ip) as who,
                      a.user_id, a.action, a.detail, a.created_at
                 from audit_logs a
                where a.created_at > now() - (%s || ' hours')::interval
           ),
           -- a checkout opened with no order from the same person afterwards
           abandoned as (
               select r.who, count(*)::int as n
                 from recent r
                where r.action = 'checkout_opened'
                  and not exists (select 1 from recent o
                                   where o.who = r.who and o.action = 'order_placed'
                                     and o.created_at > r.created_at)
                group by r.who
           ),
           failures as (
               select r.who, count(*)::int as n,
                      array_agg(distinct r.action) as kinds,
                      max(r.created_at) as last_at
                 from recent r
                where r.action = any(%s)
                group by r.who
           )
           select coalesce(f.who, ab.who)                as who,
                  coalesce(f.n, 0)                      as failures,
                  coalesce(f.kinds, '{}')               as kinds,
                  coalesce(ab.n, 0)                     as abandoned,
                  f.last_at,
                  u.id as user_id, u.email, u.full_name, u.phone
             from failures f
             full outer join abandoned ab on ab.who = f.who
             left join users u on u.id::text = coalesce(f.who, ab.who)
            where u.role is distinct from 'manager'
              and (coalesce(f.n, 0) >= 2 or coalesce(ab.n, 0) >= 1)
            order by coalesce(f.last_at, now()) desc
            limit 50""",
        [hours, list(STRUGGLE_ACTIONS)],
    )
    # checkout drop-off over the same window: opened vs actually ordered
    funnel = fetch_all(
        """select count(*) filter (where action = 'checkout_opened')::int as opened,
                  count(*) filter (where action = 'order_placed')::int   as ordered
             from audit_logs
            where created_at > now() - (%s || ' hours')::interval""",
        [hours],
    )[0]
    return {"customers": rows, "funnel": funnel, "hours": hours}

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
