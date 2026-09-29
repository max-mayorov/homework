# Smartschool homework → Telegram

Every evening this checks your child's Smartschool planner and sends you a Telegram message: what's due on the next school day, with tests flagged, and what's coming up in the next 7 days. The teacher's text is shown as written (usually Dutch or French); there's no AI step.

```
fetch.py    Smartschool planner  →  list of Item(subject, title, description, due, type)
message.py  items               →  plain-text message (next school day first, then the week)
notify.py   summary             →  Telegram (split at 4096 characters)
printer.py  items               →  black-and-white receipt image → 80 mm ESC/POS network printer (optional)
main.py     runs the three steps; any failure is sent to you as a short Telegram message
probe.py    one-off diagnostic: dumps raw Smartschool data for the next 7 days
```

It uses the unofficial [`smartschool`](https://github.com/svaningelgem/smartschool) library. That library has no parent support as such, but a parent login (your child's username plus your own password) works. Only the **planner** (`PlannedElements`) returns data for a parent login. `FutureTasks` and the agenda lessons come back empty, so the app doesn't use them.

## Quick install (DietPi / Raspberry Pi OS / Debian)

On a Raspberry Pi 4 with DietPi, as root:

```bash
apt install -y git
git clone https://github.com/max-mayorov/homework.git /opt/homework
cd /opt/homework
./install.sh          # 1st run: installs everything, creates .env, stops
nano .env             # fill in your settings (table below)
./install.sh          # 2nd run: dry run, then adds the 18:00 schedule
```

Each run of `install.sh`:
1. installs the system packages (Python, the fonts the receipt printer needs, cron) and the Python requirements in `.venv`;
2. checks that the required settings in `.env` are filled in;
3. does a dry run, which logs in and shows the report without sending anything;
4. only if that works, adds the cron entry. See "Run it at 18:00" below.

It's safe to run again: after `git pull`, run `./install.sh` to update. The app runs as whoever owns the checkout (root with the commands above). Scheduled runs write to `homework.log` in the same folder; the log never contains homework text.

## Manual setup

Requires Python 3.10+.

```bash
git clone https://github.com/max-mayorov/homework.git && cd homework
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # then fill it in (see below)
chmod 600 .env
```

### Settings

All settings come from `.env` or from environment variables, which override `.env`. Both `.env` and `credentials.yml` are in `.gitignore`.

| Variable | What to put there |
|---|---|
| `SMARTSCHOOL_USERNAME` | your child's Smartschool username |
| `SMARTSCHOOL_PASSWORD` | **your** parent password |
| `SMARTSCHOOL_MAIN_URL` | school host only, e.g. `myschool.smartschool.be` |
| `SMARTSCHOOL_MFA` | the birthday Smartschool asks for, as `YYYY-MM-DD` (just the date), or a Google Authenticator secret |
| `TELEGRAM_BOT_TOKEN` | from BotFather (below) |
| `TELEGRAM_CHAT_ID` | your chat id (below) |
| `PRINTER_ADDRESS` | optional: receipt printer as `host` or `host:port` (port 9100 by default). If set, the report is also printed |
| `PRINTER_FONT`, `PRINTER_FONT_BOLD` | optional: paths to `.ttf` files for the receipt, if the defaults aren't found |

Instead of `.env` you can use a `credentials.yml` next to the code:

```yaml
username: child.username
password: parent-password
main_url: myschool.smartschool.be
mfa: 2012-01-31
TELEGRAM_BOT_TOKEN: "123456:ABC..."
TELEGRAM_CHAT_ID: "123456789"
```

### Create the Telegram bot

1. In Telegram, open a chat with **@BotFather** and send `/newbot`. Pick a name and a username (it must end in `bot`).
2. BotFather replies with a token like `123456789:AA...`. Put it in `TELEGRAM_BOT_TOKEN`.
3. Open a chat with your new bot and send it any message, e.g. `hi`. A bot can't message you until you've messaged it.
4. Get your chat id: open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser, with your token in place of `<TOKEN>`. Find `"chat":{"id":123456789,...}` and put that number in `TELEGRAM_CHAT_ID`.

## Running

```bash
.venv/bin/python main.py --dry-run                   # print the message, don't send; with PRINTER_ADDRESS
                                                     # set, save print_preview.png instead of printing
.venv/bin/python main.py --dry-run --date 2026-10-05 # pretend today is 5 Oct
.venv/bin/python main.py                             # fetch, build the message, send
.venv/bin/python -m pytest                           # unit tests (fixture data, no logins)
```

The first section covers the **next school day** (Monday to Friday, Europe/Brussels time). Monday to Thursday evenings, that's tomorrow; Friday, Saturday and Sunday evenings, it's Monday. School holidays aren't known to the app, so during a holiday the message will just say nothing is due.

Every item has a checkbox: ✅ if it's marked as done in Smartschool, ⬜ if not. Done items stay in the list.

If any step fails (login, fetching, Telegram), you get a short Telegram message naming the step and the error, with every configured secret masked. If Telegram itself is the step that fails, the error goes to stderr and the exit code is 1.

## Receipt printer (optional)

If `PRINTER_ADDRESS` is set, each run also prints the report on an 80 mm thermal receipt printer. The printer must speak ESC/POS over the network (raw TCP, usually port 9100): most Epson TM, Xprinter, Rongta and Munbyn models do. The receipt has the same content as the Telegram message, laid out 576 px wide (72 mm at 203 dpi) in black and white. Checkboxes are printed as boxes, with a tick for done items, and tests get a black TEST badge. After printing, the paper is fed and cut.

- **Test the layout first:** set `PRINTER_ADDRESS` and run `main.py --dry-run`. This saves `print_preview.png` instead of printing.
- **Find the printer's IP:** most printers print a self-test page with it if you hold the FEED button while switching them on. Give the printer a fixed IP (a DHCP reservation in your router), so the address in `.env` keeps working.
- **Delivery:** Telegram and the printer are independent. If printing fails (printer off, wrong address), you still get the Telegram report, plus a short Telegram error saying printing failed.
- **What it can't detect:** raw TCP printing gets no answer back from the printer, so an empty paper roll is **not** reported.
- **Fonts:** the receipt uses DejaVu Sans, Liberation Sans or Arial, whichever it finds. On a minimal Linux box, install one (`sudo apt install fonts-dejavu-core`) or point `PRINTER_FONT`/`PRINTER_FONT_BOLD` at `.ttf` files. As a last resort it falls back to Pillow's built-in font, which has no bold.

## Run it at 18:00 (Europe/Brussels), every day except Friday

`install.sh` sets this up (see "Quick install" above). To do it by hand, add one crontab line that runs `cron.sh` every hour:

```cron
0 * * * * /path/to/homework/cron.sh >> /path/to/homework/homework.log 2>&1
```

`cron.sh` only runs the check when it's 18:xx in Europe/Brussels and not a Friday, so the machine's own timezone doesn't matter and summer time is handled. The hourly calls at other times exit immediately. There's no Friday run: Saturday and Sunday evenings both report Monday.

The app only needs outbound HTTPS access to your school's `*.smartschool.be` host, and `api.telegram.org`, plus TCP to the printer if you use one. Nothing about it is tied to a particular host.

## Privacy

- The log shows only counts, the model name and step names, never homework text or names. The smartschool library logs the username at INFO level; that's filtered out.
- The homework text goes only to Telegram.
- The smartschool library keeps its session cookies and the logged-in user's profile under `~/.cache/smartschool/<username>/`.
- `probe.py` prints raw data, your child's included, to the terminal. `probe_output*.txt` is git-ignored.
- `print_preview.png` from a dry run contains the same data, and is git-ignored too.

## Known limitations

- The planner list only has a title per item. The teacher's full text is usually in the title, and `description` is empty unless Smartschool starts sending one. The message shows the title as written, plus the description when there is one.
- Item types come from the school's own labels (`Toets`, `Grote toets` → ⚠️ TEST; `Taak`, `Opdracht`, `Les leren` → homework; `Meebrengen` → bring; anything else → other). If your school uses other labels, add them in `fetch.py`.
