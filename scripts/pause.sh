#!/usr/bin/env bash
# Close the shop behind the pause screen, and open it again.
#
#   ./scripts/pause.sh on 2026-12-10   # close now, reopening on that date
#   ./scripts/pause.sh off             # open now
#   ./scripts/pause.sh status          # which it currently is
#   ./scripts/pause.sh due             # open if the date has arrived (for cron)
#
# The switch is the file pause/ON, which holds the reopening date. Caddy tests for
# it on every request, so both directions take effect on the next page load with no
# restart, no rebuild and no deploy — and if anything goes wrong, `off` is the whole
# recovery.
#
# What does NOT stop while the shop is closed: the api and db containers keep
# running, so reconcile.py still settles payments that were in flight, releases the
# stock they reserved, and sends the customer their confirmation. That cron is the
# reason a closed shop still finishes the orders it already took — leave it alone.
set -euo pipefail

cd "$(dirname "$0")/.."
FLAG=pause/ON
# The shop counts its days in Dubai (see backend/routers/stats.py). The server is
# almost certainly on UTC, four hours behind — reading "today" off the server clock
# would reopen a day early for anyone who asked for a date in the shop's own terms.
SHOP_TZ=Asia/Dubai

today() { TZ="$SHOP_TZ" date +%F; }

case "${1:-status}" in
  on)
    until_date="${2:-}"
    if [[ ! "$until_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
      echo "usage: $0 on YYYY-MM-DD   (the date the shop reopens, Dubai time)" >&2
      exit 2
    fi
    mkdir -p pause
    printf '%s\n' "$until_date" > "$FLAG"
    echo "Shop closed. The pause screen is up, and it reopens on $until_date (Dubai)."
    echo "Reopen by hand at any time with:  $0 off"
    ;;

  off)
    rm -f "$FLAG"
    echo "Shop open. ($(today) Dubai)"
    ;;

  due)
    # Run hourly from cron. Silent while there is nothing to do, so the log it
    # appends to stays a record of the one moment that mattered.
    [[ -f "$FLAG" ]] || exit 0
    want=$(tr -d '[:space:]' < "$FLAG")
    [[ -n "$want" ]] || exit 0
    # ISO dates compare correctly as plain strings, which is most of why they are
    # written this way round.
    if [[ ! "$(today)" < "$want" ]]; then
      rm -f "$FLAG"
      echo "$(TZ="$SHOP_TZ" date '+%F %H:%M %Z') — reopened (was due $want)"
    fi
    ;;

  status)
    if [[ -f "$FLAG" ]]; then
      echo "CLOSED — reopens $(tr -d '[:space:]' < "$FLAG") (today is $(today) Dubai)"
    else
      echo "OPEN (today is $(today) Dubai)"
    fi
    ;;

  *)
    echo "usage: $0 {on YYYY-MM-DD|off|status|due}" >&2
    exit 2
    ;;
esac
