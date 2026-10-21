# Smartschool homework → Telegram

Every afternoon this checks your child's Smartschool planner and sends you a Telegram message: what's due on the next school day, with tests flagged, and what's coming up in the next 7 days. An hour later it checks Smartschool's "Resultaten" and, if new results came in, sends you those with their scores. The teacher's text is shown as written (usually Dutch or French); there's no AI step.

```
fetch.py    Smartschool planner  →  list of Item(subject, title, description, due, type)
results.py  Smartschool results  →  list of new Result(subject, name, score, colour, taken, feedback)
message.py  items / results      →  plain-text message
notify.py   message              →  Telegram (split at 4096 characters)
printer.py  items / results      →  black-and-white receipt image → 80 mm ESC/POS network printer (optional)
main.py     runs the steps; any failure is sent to you as a short Telegram message
errors.py   failure  →  short error message with secrets masked
probe.py    one-off diagnostic: dumps raw Smartschool data for the next 7 days
custom_components/smartschool_homework   the same reports as a Home Assistant integration (see "Home Assistant")
```

It uses the unofficial [`smartschool`](https://github.com/svaningelgem/smartschool) library. That library has no parent support as such, but a parent login (your child's username plus your own password) works. For a parent login the **planner** (`PlannedElements`) and the **results** (`Results`) return data. `FutureTasks` and the agenda lessons come back empty, so the app doesn't use them.

## Quick install (DietPi / Raspberry Pi OS / Debian)

On a Raspberry Pi 4 with DietPi (as root, or as `dietpi` with the `sudo`s shown):

```bash
sudo apt install -y git
sudo git clone https://github.com/max-mayorov/homework.git /opt/homework
cd /opt/homework
sudo ./install.sh     # 1st run: installs everything, creates .env, stops
sudo nano .env        # fill in your settings (table below)
sudo ./install.sh     # 2nd run: dry run, then adds the 15:05 / 16:05 schedule
```

Each run of `install.sh`:
1. installs the system packages (Python, the fonts the receipt printer needs, cron) and the Python requirements in `.venv`;
2. checks that the required settings in `.env` are filled in;
3. does a dry run, which logs in and shows both reports without sending anything;
4. only if that works, adds the cron entry. See "Schedule" below.

It's safe to run again. To update: `cd /opt/homework && sudo git pull && sudo ./install.sh`. Both need `sudo` because the checkout belongs to root. For the same reason, run the commands under "Running" below with `sudo` too, e.g. `sudo .venv/bin/python main.py --dry-run`: `.env` is readable only by its owner. The app runs as whoever owns the checkout (root with the commands above). Scheduled runs write to `homework.log` in the same folder; the log never contains homework text.

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

**Special characters in `.env`:** put values in single quotes, e.g. `SMARTSCHOOL_PASSWORD='my#pass word'`. Without quotes, a `#` that follows a space starts a comment, and everything after it is dropped. Inside single quotes everything is literal, including `#`, `$`, `"` and backslashes. If the value itself contains a single quote, use double quotes instead and put a backslash before any `"` or `\` in it: `"it's#1"`. No spaces around `=`.

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
.venv/bin/python main.py --results --dry-run         # print the new results, don't send
.venv/bin/python main.py --results --since 2026-10-01  # results published since 1 Oct
.venv/bin/python main.py --results                   # send the new results
.venv/bin/python -m pytest                           # unit tests (fixture data, no logins)
```

The first section covers the **next school day** (Monday to Friday, Europe/Brussels time). Monday to Thursday, that's tomorrow; Friday, Saturday and Sunday, it's Monday. School holidays aren't known to the app, so during a holiday the message will just say nothing is due.

Every item has a checkbox: ✅ if it's marked as done in Smartschool, ⬜ if not. Done items stay in the list.

If any step fails (login, fetching, Telegram), you get a short Telegram message naming the step and the error, with every configured secret masked. If Telegram itself is the step that fails, the error goes to stderr and the exit code is 1.

## Results

`main.py --results` sends the results that were **published since the last results message**, and never more than 14 days back. So the very first run shows the last two weeks, and if the machine was off for a month you get the last two weeks only. If nothing new was published, nothing is sent or printed.

```
🎓 New results

😞 Frans · 4/10 (40%)
   Test Verbes colonne 4
   Taken Friday 9 October
   💬 Au travail! ...

😄 Muziek · 10/10 (100%)
   Opdracht: piano app
   Taken Monday 12 October
```

The smiley is Smartschool's own score colour: red 😞, yellow 😐, green 🙂, olive (dark green, the best) 😄. Results are listed by the day the test was taken, oldest first. Teacher feedback is shown in full; a result that doesn't count towards the grade says "(doesn't count)".

The time of the last results message is kept in `last_results_run.txt` next to the code. It's only updated once Telegram has the message, so after a failed run the same results come again the next day. A dry run doesn't update it; `--since YYYY-MM-DD` ignores it for one run. Delete the file to start again from the last 14 days.

## Receipt printer (optional)

If `PRINTER_ADDRESS` is set, each run also prints the report on an 80 mm thermal receipt printer. The printer must speak ESC/POS over the network (raw TCP, usually port 9100): most Epson TM, Xprinter, Rongta and Munbyn models do. The receipt has the same content as the Telegram message, laid out 576 px wide (72 mm at 203 dpi) in black and white. Checkboxes are printed as boxes, with a tick for done items, and tests get a black TEST badge. On the results receipt, each score gets a drawn face whose mouth goes from a frown (red) to a big smile (olive). After printing, the paper is fed and cut.

- **Test the layout first:** set `PRINTER_ADDRESS` and run `main.py --dry-run` (or `main.py --results --dry-run`). This saves `print_preview.png` instead of printing.
- **Find the printer's IP:** most printers print a self-test page with it if you hold the FEED button while switching them on. Give the printer a fixed IP (a DHCP reservation in your router), so the address in `.env` keeps working.
- **Delivery:** Telegram and the printer are independent. If printing fails (printer off, wrong address), you still get the Telegram report, plus a short Telegram error saying printing failed.
- **What it can't detect:** raw TCP printing gets no answer back from the printer, so an empty paper roll is **not** reported.
- **Fonts:** the receipt uses DejaVu Sans, Liberation Sans or Arial, whichever it finds. On a minimal Linux box, install one (`sudo apt install fonts-dejavu-core`) or point `PRINTER_FONT`/`PRINTER_FONT_BOLD` at `.ttf` files. As a last resort it falls back to Pillow's built-in font, which has no bold.

## Schedule (Europe/Brussels)

- **15:05** the homework check, every day except Friday. There's no Friday run: Saturday and Sunday both report Monday.
- **16:05** the results check, every day. Many results are published at exactly 16:00, so this catches them the same day.

`install.sh` sets this up (see "Quick install" above). To do it by hand, add one crontab line that runs `cron.sh` every hour at 5 past:

```cron
5 * * * * /path/to/homework/cron.sh >> /path/to/homework/homework.log 2>&1
```

`cron.sh` picks the check from the hour in Europe/Brussels, so the machine's own timezone doesn't matter and summer time is handled. The hourly calls at other times exit immediately.

The app only needs outbound HTTPS access to your school's `*.smartschool.be` host, and `api.telegram.org`, plus TCP to the printer if you use one. Nothing about it is tied to a particular host.

## Home Assistant

Instead of the Raspberry Pi setup, you can run the reports from Home Assistant with the **Smartschool Homework** integration in `custom_components/smartschool_homework`. It sends the same reports to the same Telegram chat and receipt printer, but you start them from HA: from buttons on a dashboard, or from your own automations. The integration has no schedule of its own.

Use one or the other, not both: with the Pi cron job running as well, you'd get every report twice.

### Install

With [HACS](https://hacs.xyz): **HACS → ⋮ → Custom repositories**, add `https://github.com/max-mayorov/homework` with type **Integration**, then download **Smartschool Homework** and restart Home Assistant.

Without HACS: copy the `custom_components/smartschool_homework` folder into the `custom_components` folder of your HA config (create it if needed), and restart Home Assistant.

Needs Home Assistant 2024.12 or newer.

### Set up

1. **Settings → Devices & services → Add integration → Smartschool Homework.**
2. Fill in the school host, your child's username, **your** parent password, and the birthday (`YYYY-MM-DD`) or authenticator secret. These are the same as the `SMARTSCHOOL_*` settings above. HA logs in once to check them.
3. Open the integration's **Configure** to add Telegram (bot token and chat id, see "Create the Telegram bot") and/or the receipt printer's address. Both are optional. If the receipt text looks wrong, you can also give paths to `.ttf` fonts here.

To change the password later, use **⋮ → Reconfigure** on the integration.

### What you get

| Entity | What it does |
|---|---|
| `button.…_send_homework_report` | sends the Homework report now |
| `button.…_send_results_report` | sends the new Results now; nothing if there are none |
| `switch.…_telegram` | whether reports go to Telegram |
| `switch.…_print_receipt` | whether reports are printed |

A switch is unavailable until its channel is set up in **Configure**. Pressing a button with both switches off gives an error instead of doing nothing.

When something fails (login, Telegram, the printer), the button or action shows the error, it's written to the HA log, and, if Telegram is on, it's sent to Telegram as well, with secrets masked. As with the Pi setup, Telegram and the printer are independent: if printing fails, the Telegram report still goes out.

### Actions (services)

`smartschool_homework.send_homework_report` and `smartschool_homework.send_results_report` do what the buttons do. Optional fields:

| Field | |
|---|---|
| `telegram`, `print` | `true`/`false` to override the switches for this call |
| `date` | homework only: pretend today is this date (like `--date`) |
| `since` | results only: report results published since this date (like `--since`) |
| `config_entry_id` | only needed if you set up more than one Smartschool account |

Both actions can return the report as a response (`message` with the text, and `count`). With `telegram: false` and `print: false` that's a preview, like `--dry-run`: nothing is sent, and the results bookkeeping isn't touched. You can use this to send the report through HA's own notifications instead of Telegram.

### Schedule with automations

The same schedule as the Pi (homework at 15:05 except Fridays, results at 16:05). HA uses its own timezone, so set it to Europe/Brussels or adjust the times.

```yaml
automation:
  - alias: Homework report
    triggers:
      - trigger: time
        at: "15:05:00"
    conditions:
      - condition: time
        weekday: [mon, tue, wed, thu, sat, sun]
    actions:
      - action: smartschool_homework.send_homework_report

  - alias: Results report
    triggers:
      - trigger: time
        at: "16:05:00"
    actions:
      - action: smartschool_homework.send_results_report
```

To send the report to the HA companion app instead of Telegram:

```yaml
    actions:
      - action: smartschool_homework.send_homework_report
        data:
          telegram: false
        response_variable: report
      - action: notify.mobile_app_your_phone
        data:
          title: Homework
          message: "{{ report.message }}"
```

For results, only send when there's something new: add `- condition: template` with `value_template: "{{ report.count > 0 }}"` before the notify step. Note that with `telegram: false` and `print: false`, the results report is a preview and the next run reports the same results again. Leave the printer on (or set `print: true`) to make it count as delivered.

### Notes

- HA keeps the time of the last delivered results report in its own storage (`.storage/smartschool_homework.<entry id>`), not in `last_results_run.txt`.
- The smartschool library's logging is routed into HA's normal log as the `smartschool` logger. (On its own it would take over all of Python's logging, which would break HA's log.) It logs the child's username at INFO level, which HA doesn't show by default.
- The integration keeps a copy of the app's modules in `custom_components/smartschool_homework/core/`. If you change `fetch.py`, `message.py` or the others, run `python scripts/sync_ha_core.py` to update the copy; a unit test fails until you do. The integration's own tests need Home Assistant's test harness: `pip install -r requirements_ha_test.txt`, then `python -m pytest tests_ha`.

## Privacy

- The log shows only counts, the model name and step names, never homework text or names. The smartschool library logs the username at INFO level; that's filtered out.
- The homework text and the results go only to Telegram (and the printer, if set).
- `last_results_run.txt` holds only a timestamp, and is git-ignored.
- The smartschool library keeps its session cookies and the logged-in user's profile under `~/.cache/smartschool/<username>/`.
- `probe.py` prints raw data, your child's included, to the terminal. `probe_output*.txt` is git-ignored.
- `print_preview.png` from a dry run contains the same data, and is git-ignored too.

## Known limitations

- The planner list only has a title per item. The teacher's full text is usually in the title, and `description` is empty unless Smartschool starts sending one. The message shows the title as written, plus the description when there is one.
- If a teacher changes a score after publishing it, the change isn't reported again: Smartschool keeps the original publication time.
- Smartschool also has `steel` and `grass` score colours, which haven't been seen in use. They get a plain • instead of a smiley.
- The class average isn't shown: reading it takes an extra request per result, and the library fails to parse it for some schools.
- Item types come from the school's own labels (`Toets`, `Grote toets` → ⚠️ TEST; `Taak`, `Opdracht`, `Les leren` → homework; `Meebrengen` → bring; anything else → other). If your school uses other labels, add them in `fetch.py`.
