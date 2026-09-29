#!/bin/sh
# Called every hour by cron (see install.sh). Runs the homework check at 18:xx Europe/Brussels
# time, every day except Friday, whatever timezone the machine itself is set to.
# Extra arguments are passed on to main.py.
set -eu

hour=$(TZ=Europe/Brussels date +%H)
weekday=$(TZ=Europe/Brussels date +%u)  # 1 = Monday ... 5 = Friday ... 7 = Sunday

[ "$hour" = "18" ] || exit 0
[ "$weekday" = "5" ] && exit 0

cd "$(dirname "$0")"
exec .venv/bin/python main.py "$@"
