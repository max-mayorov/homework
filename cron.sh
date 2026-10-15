#!/bin/sh
# Called every hour by cron (see install.sh). In Europe/Brussels time, whatever timezone the
# machine itself is set to, it runs:
#   15:xx  the homework check, every day except Friday
#   16:xx  the results check, every day
# Extra arguments are passed on to main.py.
set -eu

hour=$(TZ=Europe/Brussels date +%H)
weekday=$(TZ=Europe/Brussels date +%u)  # 1 = Monday ... 5 = Friday ... 7 = Sunday

cd "$(dirname "$0")"
case "$hour" in
    15) [ "$weekday" = "5" ] && exit 0
        exec .venv/bin/python main.py "$@" ;;
    16) exec .venv/bin/python main.py --results "$@" ;;
esac
