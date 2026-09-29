#!/bin/bash
# One-shot installer for DietPi / Debian / Raspberry Pi OS. Safe to run again (e.g. after a git pull).
#
#   sudo git clone https://github.com/max-mayorov/homework.git /opt/homework
#   cd /opt/homework && sudo ./install.sh
#
# 1. installs system packages (Python venv, fonts for the receipt printer, cron)
# 2. creates .venv and installs the Python requirements
# 3. creates .env from .env.example on the first run, then stops so you can fill it in
# 4. checks the settings with a dry run (prints the report here, sends nothing)
# 5. adds an hourly cron entry for cron.sh, which runs the check at 18:00 Brussels time,
#    except Fridays
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OWNER="$(stat -c %U "$DIR")"  # the app runs as whoever owns the checkout, not as root
CRON_MARKER="# homework-check"
REQUIRED=(SMARTSCHOOL_USERNAME SMARTSCHOOL_PASSWORD SMARTSCHOOL_MAIN_URL SMARTSCHOOL_MFA TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID)

step() { printf '\n==> %s\n' "$*"; }
as_owner() { if [ "$OWNER" = root ]; then "$@"; else runuser -u "$OWNER" -- "$@"; fi; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root: sudo $0" >&2
    exit 1
fi
cd "$DIR"

step "Installing system packages"
arch="$(dpkg --print-architecture)"
packages=(python3 python3-venv python3-pip fonts-dejavu-core cron ca-certificates)
pip_extra=()
if [ "$arch" = armhf ] || [ "$arch" = armel ]; then
    # 32-bit ARM: PyPI has few prebuilt packages. Use piwheels, and keep build tools as a fallback.
    packages+=(build-essential python3-dev libjpeg-dev zlib1g-dev libfreetype-dev)
    pip_extra=(--extra-index-url https://www.piwheels.org/simple)
fi
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${packages[@]}"
systemctl enable --now cron >/dev/null 2>&1 || true

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    echo "Python 3.10 or newer is needed, found $(python3 --version). Upgrade the OS (DietPi on Debian Bookworm has 3.11)." >&2
    exit 1
fi

step "Installing Python requirements into $DIR/.venv"
[ -d .venv ] || as_owner python3 -m venv .venv
as_owner .venv/bin/pip install --quiet --upgrade pip
as_owner .venv/bin/pip install --quiet "${pip_extra[@]}" -r requirements.txt

if [ ! -f .env ] && [ ! -f credentials.yml ]; then
    step "Creating .env"
    as_owner cp .env.example .env
    chmod 600 .env
    echo "Fill in your settings, then run this script again:"
    echo "    nano $DIR/.env"
    exit 0
fi

if [ -f .env ]; then
    chmod 600 .env
    missing=()
    for key in "${REQUIRED[@]}"; do
        grep -Eq "^${key}=.+" .env || missing+=("$key")
    done
    if [ ${#missing[@]} -gt 0 ] && [ ! -f credentials.yml ]; then
        echo "These settings are empty in $DIR/.env: ${missing[*]}" >&2
        echo "Fill them in and run this script again." >&2
        exit 1
    fi
fi

step "Dry run (logs in to Smartschool and prints the report here; nothing is sent)"
if ! as_owner .venv/bin/python main.py --dry-run; then
    echo "The dry run failed, so the schedule was not installed. Fix the error above and run this script again." >&2
    exit 1
fi

step "Scheduling: cron.sh every hour; it runs the check at 18:00 Europe/Brussels, except Fridays"
chmod +x cron.sh
touch homework.log
chown "$OWNER": homework.log
cron_line="0 * * * * $DIR/cron.sh >> $DIR/homework.log 2>&1 $CRON_MARKER"
{ crontab -u "$OWNER" -l 2>/dev/null | grep -vF "$CRON_MARKER" || true; echo "$cron_line"; } | crontab -u "$OWNER" -
echo "Cron entry for user $OWNER:"
echo "    $cron_line"

# Commands must run as the checkout's owner: git needs to write to .git, and .env is readable only by the owner
sudo_=""; [ "$OWNER" = root ] && sudo_="sudo "

cat <<EOF

Done. Useful commands:
    cd $DIR
    ${sudo_}.venv/bin/python main.py --dry-run   # preview the report
    ${sudo_}.venv/bin/python main.py             # send it now (Telegram, and printer if PRINTER_ADDRESS is set)
    tail $DIR/homework.log               # what the scheduled runs did
    ${sudo_}git pull && sudo ./install.sh   # update
EOF
