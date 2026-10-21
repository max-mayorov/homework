# Smartschool Homework

Keeps you up to date on your child's Smartschool, with two reports:

- **Homework report:** what's due on the next school day, with tests flagged, and what's coming up in the rest of the week.
- **Results report:** new grades ("Resultaten") with their scores and the teacher's feedback.

They go to Telegram, and optionally to an 80 mm receipt printer. The teacher's text is shown as written (usually Dutch or French); there's no AI step.

There are two ways to run it:

- **[In Home Assistant](#home-assistant) (recommended).** An integration you install with HACS and set up from the UI. You start the reports from dashboard buttons or your own automations.
- **[As a stand-alone app](#stand-alone-app-without-home-assistant)** on a Raspberry Pi or any Linux machine, without Home Assistant. Cron sends the reports at 15:05 and 16:05.

Both send the same reports. Use one or the other: with both running, you'd get every report twice.

It uses the unofficial [`smartschool`](https://github.com/svaningelgem/smartschool) library. That library has no parent support as such, but a parent login (your child's username plus your own password) works. For a parent login the **planner** and the **results** return data, and that's what the reports use.

## The reports

### Homework report

```
📚 Due Wednesday 30 September

⬜ ⚠️ TEST · Frans (Toets)
   Verbes colonne 4 leren
✅ 📝 Homework · Wiskunde (Taak, 08:25)
   Oefeningen p. 42, 1-8

Coming up this week

Friday 2 October
⬜ 🎒 Bring · Muziek (Meebrengen)
   Blokfluit
```

The first section covers the **next school day** (Monday to Friday, Europe/Brussels time). Monday to Thursday, that's tomorrow; Friday, Saturday and Sunday, it's Monday. Then come the items for the rest of the coming week. School holidays aren't known, so during a holiday the report just says nothing is due.

Every item has a checkbox: ✅ if it's marked as done in Smartschool, ⬜ if not. Done items stay in the list.

### Results report

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

It has the results **published since the last results report was delivered**, and never more than 14 days back. So the very first report shows the last two weeks, and after a month without reports you get the last two weeks only. If nothing new was published, nothing is sent or printed.

The smiley is Smartschool's own score colour: red 😞, yellow 😐, green 🙂, olive (dark green, the best) 😄. Results are listed by the day the test was taken, oldest first. Teacher feedback is shown in full; a result that doesn't count towards the grade says "(doesn't count)".

### Receipt printer (optional)

Each report can also be printed on an 80 mm thermal receipt printer. The printer must speak ESC/POS over the network (raw TCP, usually port 9100): most Epson TM, Xprinter, Rongta and Munbyn models do. The receipt has the same content as the Telegram message, laid out 576 px wide (72 mm at 203 dpi) in black and white. Checkboxes are printed as boxes, with a tick for done items, and tests get a black TEST badge. On the results receipt, each score gets a drawn face whose mouth goes from a frown (red) to a big smile (olive). After printing, the paper is fed and cut.

- **Printer address:** `host`, `host:port` or `[IPv6]:port`; the port is 9100 if left out.
- **Find the printer's IP:** most printers print a self-test page with it if you hold the FEED button while switching them on. Give the printer a fixed IP (a DHCP reservation in your router), so the address keeps working.
- **Delivery:** Telegram and the printer are independent. If printing fails (printer off, wrong address), the Telegram report still goes out.
- **What it can't detect:** raw TCP printing gets no answer back from the printer, so an empty paper roll is **not** reported.
- **Fonts:** the receipt uses DejaVu Sans, Liberation Sans or Arial, whichever it finds. You can also give paths to `.ttf` files. As a last resort it falls back to Pillow's built-in font, which has no bold.

## Home Assistant

The **Smartschool Homework** integration sends the reports from Home Assistant. It has no schedule of its own: you send a report with a dashboard button, or from an automation (see "Schedule with automations" below).

Needs Home Assistant 2025.7 or newer.

### Install

With [HACS](https://hacs.xyz): **HACS → ⋮ → Custom repositories**, add `https://github.com/max-mayorov/homework` with type **Integration**. Then download **Smartschool Homework** and restart Home Assistant.

Without HACS: copy the `custom_components/smartschool_homework` folder into the `custom_components` folder of your HA config (create it if needed), and restart Home Assistant.

### Set up

1. **Settings → Devices & services → Add integration → Smartschool Homework.**
2. Fill in the school host (e.g. `myschool.smartschool.be`), your child's username, **your** parent password, and the birthday Smartschool asks for (`YYYY-MM-DD`) or a Google Authenticator secret. HA logs in once to check them.
3. Optional, for Telegram: set up Home Assistant's own [Telegram bot](https://www.home-assistant.io/integrations/telegram_bot/) integration (see [Create the Telegram bot](#create-the-telegram-bot)), and add the chat the reports should go to as one of its allowed chats.
4. Open this integration's **Configure**. Pick that Telegram chat, and/or give the receipt printer's address. Both are optional. If the receipt text looks wrong, you can also give paths to `.ttf` fonts here.

To change the password later, use **⋮ → Reconfigure** on the integration.

Telegram messages go through the Telegram bot integration's `telegram_bot.send_message` action, so this integration never sees the bot token. They're sent as plain text, so teachers' text arrives exactly as written. A report longer than Telegram's 4096-character limit is split into several messages.

### What you get

| Entity | What it does |
|---|---|
| `button.…_send_homework_report` | sends the Homework report now |
| `button.…_send_results_report` | sends the new Results now; nothing if there are none |
| `switch.…_telegram` | whether reports go to Telegram |
| `switch.…_print_receipt` | whether reports are printed |

A switch is unavailable until its channel is set up in **Configure**. Pressing a button with both switches off gives an error instead of doing nothing.

When something fails (login, Telegram, the printer), the button or action fails with the error, with secrets masked. Home Assistant shows it in the UI, or in the automation's trace and the log. Errors aren't sent to Telegram.

### Actions

`smartschool_homework.send_homework_report` and `smartschool_homework.send_results_report` do what the buttons do. Optional fields:

| Field | |
|---|---|
| `telegram`, `print` | `true`/`false` to override the switches for this call |
| `date` | homework only: pretend today is this date |
| `since` | results only: report the results published since this date, instead of since the last report |
| `config_entry_id` | only needed if you set up more than one Smartschool account |

Both actions can return the report as a response: `message` with the text, and `count`. With `telegram: false` and `print: false` that's a preview: nothing is sent, and the results report doesn't count as delivered. You can use this to send the report through HA's own notifications instead of Telegram.

### Schedule with automations

The stand-alone app's schedule is homework at 15:05 except on Fridays, and results at 16:05. Many results are published at exactly 16:00, so that catches them the same day. There's no Friday homework report because Saturday and Sunday both report Monday. HA uses its own timezone, so set it to Europe/Brussels or adjust the times.

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

For results, only send when there's something new: add `- condition: template` with `value_template: "{{ report.count > 0 }}"` before the notify step. With `telegram: false` and `print: false`, the results report is a preview, so the next run reports the same results again. Leave the printer on (or set `print: true`) to make it count as delivered.

### Notes

- HA keeps the time of the last delivered results report in its own storage (`.storage/smartschool_homework.<entry id>`).
- **Logging** is Home Assistant's: everything, including the smartschool library's messages, is under `custom_components.smartschool_homework`. To debug, use **Enable debug logging** on the integration, or:
  ```yaml
  logger:
    logs:
      custom_components.smartschool_homework: debug
  ```
  At debug level the library logs the child's username. (On its own the library would take over all of Python's logging, which would break HA's log; the integration routes it into HA's instead.)

## Stand-alone app (without Home Assistant)

`main.py` runs the same reports without Home Assistant, from cron. It sends the reports to Telegram directly with your bot's token, and sends any failure to you as a short Telegram message. The reports themselves come from the integration's code in `custom_components/smartschool_homework/homework/`, which is part of the checkout.

### Quick install (DietPi / Raspberry Pi OS / Debian)

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

### Manual setup

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
| `TELEGRAM_BOT_TOKEN` | from BotFather (see [Create the Telegram bot](#create-the-telegram-bot)) |
| `TELEGRAM_CHAT_ID` | your chat id (same section) |
| `PRINTER_ADDRESS` | optional: the receipt printer's address (see "Receipt printer" above). If set, the report is also printed |
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

### Running

```bash
.venv/bin/python main.py --dry-run                   # print the message, don't send; with PRINTER_ADDRESS
                                                     # set, save print_preview.png instead of printing
.venv/bin/python main.py --dry-run --date 2026-10-05 # pretend today is 5 Oct
.venv/bin/python main.py                             # fetch, build the message, send
.venv/bin/python main.py --results --dry-run         # print the new results, don't send
.venv/bin/python main.py --results --since 2026-10-01  # results published since 1 Oct
.venv/bin/python main.py --results                   # send the new results
```

If any step fails (login, fetching, Telegram, printing), you get a short Telegram message naming the step and the error, with every configured secret masked. If Telegram itself is the step that fails, the error goes to stderr and the exit code is 1.

The time of the last results report is kept in `last_results_run.txt` next to the code. It's only updated once Telegram has the message, so after a failed run the same results come again the next day. A dry run doesn't update it; `--since YYYY-MM-DD` ignores it for one run. Delete the file to start again from the last 14 days.

To check the receipt layout, set `PRINTER_ADDRESS` and run `main.py --dry-run` (or `main.py --results --dry-run`): this saves `print_preview.png` instead of printing. On a minimal Linux box, install a font for the receipt with `sudo apt install fonts-dejavu-core` (`install.sh` does this).

### Schedule (Europe/Brussels)

- **15:05** the homework check, every day except Friday. There's no Friday run: Saturday and Sunday both report Monday.
- **16:05** the results check, every day. Many results are published at exactly 16:00, so this catches them the same day.

`install.sh` sets this up (see "Quick install" above). To do it by hand, add one crontab line that runs `cron.sh` every hour at 5 past:

```cron
5 * * * * /path/to/homework/cron.sh >> /path/to/homework/homework.log 2>&1
```

`cron.sh` picks the check from the hour in Europe/Brussels, so the machine's own timezone doesn't matter and summer time is handled. The hourly calls at other times exit immediately.

The app only needs outbound HTTPS access to your school's `*.smartschool.be` host, and `api.telegram.org`, plus TCP to the printer if you use one. Nothing about it is tied to a particular host.

## Create the Telegram bot

1. In Telegram, open a chat with **@BotFather** and send `/newbot`. Pick a name and a username (it must end in `bot`).
2. BotFather replies with a token like `123456789:AA...`.
3. Open a chat with your new bot and send it any message, e.g. `hi`. A bot can't message you until you've messaged it.

**Home Assistant:** add the bot with the [Telegram bot](https://www.home-assistant.io/integrations/telegram_bot/) integration, using the token, and add your chat to it as an allowed chat. Then pick that chat in this integration's **Configure**.

**Stand-alone app:** put the token in `TELEGRAM_BOT_TOKEN`. To get your chat id, open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser, with your token in place of `<TOKEN>`. Find `"chat":{"id":123456789,...}` and put that number in `TELEGRAM_CHAT_ID`.

You can use the same bot for both, e.g. while moving from the app to Home Assistant.

## Privacy

- The homework text and the results go only to Telegram (and the printer, if set).
- The smartschool library keeps its session cookies and the logged-in user's profile under `~/.cache/smartschool/<username>/` of whoever runs it.
- **Home Assistant:** the login is stored in HA's config entries, like any integration's. HA's log gets only errors (with secrets masked) unless you turn on debug logging, which also shows the child's username.
- **Stand-alone app:** the log shows only counts and step names, never homework text or names. The smartschool library logs the username at INFO level; that's filtered out. `last_results_run.txt` holds only a timestamp, and is git-ignored.
- `probe.py` prints raw data, your child's included, to the terminal. `probe_output*.txt` is git-ignored.
- `print_preview.png` from a dry run contains the same data, and is git-ignored too.

## Known limitations

- The planner list only has a title per item. The teacher's full text is usually in the title, and `description` is empty unless Smartschool starts sending one. The report shows the title as written, plus the description when there is one.
- If a teacher changes a score after publishing it, the change isn't reported again: Smartschool keeps the original publication time.
- Smartschool also has `steel` and `grass` score colours, which haven't been seen in use. They get a plain • instead of a smiley.
- The class average isn't shown: reading it takes an extra request per result, and the library fails to parse it for some schools.
- Item types come from the school's own labels (`Toets`, `Grote toets` → ⚠️ TEST; `Taak`, `Opdracht`, `Les leren` → homework; `Meebrengen` → bring; anything else → other). If your school uses other labels, add them in `custom_components/smartschool_homework/homework/fetch.py`.
- For a parent login, the library's `FutureTasks` and agenda lessons come back empty, so the reports don't use them.

## Development

The integration is the main source of the reports. Their logic is its `homework` package, which must not import Home Assistant:

```
custom_components/smartschool_homework/
  homework/fetch.py       Smartschool planner  →  list of Item(subject, title, description, due, type)
  homework/results.py     Smartschool results  →  list of new Result(subject, name, score, colour, taken, feedback)
  homework/message.py     items / results      →  plain-text message
  homework/notify.py      message              →  Telegram (split at 4096 characters)
  homework/printer.py     items / results      →  black-and-white receipt image → 80 mm ESC/POS network printer
  homework/credentials.py settings             →  Smartschool login
  config_flow.py, reporter.py, button.py, switch.py, library_logging.py   the Home Assistant side

main.py      the stand-alone app: puts the integration's folder on sys.path, imports homework,
             and adds settings, logging, error messages to Telegram and the results bookkeeping
config.py    reads the app's settings from .env or credentials.yml
cron.sh      the app's schedule
probe.py     one-off diagnostic: dumps raw Smartschool data for the next 7 days
```

Tests:

```bash
.venv/bin/python -m pytest                    # the homework package and the app (fixture data, no logins)
pip install -r requirements_ha_test.txt       # Home Assistant's test harness, for the integration's tests
python -m pytest tests_ha
```
