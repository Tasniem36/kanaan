"""How an order is named and shown to a person.

One place, because the alternative is what this shop had: the customer's order was
DK-EPBV9SH on their tracking page and #a1b2c3d4 in طلباتي, at the till, in the
manager's Telegram alert and on the audit log — five names for one order, so nobody
could quote it to anybody. Anything that puts an order in front of a human — a page,
an e-mail, a push, an alert, a payment description — takes its name from here.

A leaf module on purpose: routers/orders.py imports notify.py, so neither of them
can own this without a cycle. It imports nothing itself.

Server logs are the exception and keep the raw id: they exist to be matched against
the database, not read out over the phone.
"""


def display_ref(ref, oid):
    """What the customer sees. Orders from before ref existed fall back to the id."""
    return f"DK-{ref}" if ref else f"#{str(oid)[:8]}"


def phone_hint(phone):
    """The phone shown back partially, so a customer can check what they typed
    without the full number sitting behind a link that might be forwarded."""
    phone = phone or ""
    return (phone[:4] + "*" * (len(phone) - 8) + phone[-4:]) if len(phone) > 8 else phone
