# Smartschool Homework for Home Assistant

This integration sends the same reports as the [Raspberry Pi app](../../README.md) to Telegram and the receipt printer, but you start them from HA: from buttons on a dashboard, or from your own automations. The integration has no schedule of its own.

Use one or the other, not both: with the Pi cron job running as well, you'd get every report twice.

## Install

With [HACS](https://hacs.xyz): **HACS → ⋮ → Custom repositories**, add `https://github.com/max-mayorov/homework` with type **Integration**, then download **Smartschool Homework** and restart Home Assistant.

Without HACS: copy the `custom_components/smartschool_homework` folder into the `custom_components` folder of your HA config (create it if needed), and restart Home Assistant.

Needs Home Assistant 2025.7 or newer.

## Set up

1. **Settings → Devices & services → Add integration → Smartschool Homework.**
2. Fill in the school host, your child's username, **your** parent password, and the birthday (`YYYY-MM-DD`) or authenticator secret. These are the same as the app's `SMARTSCHOOL_*` settings. HA logs in once to check them.
3. Optional: for Telegram, set up Home Assistant's own [Telegram bot](https://www.home-assistant.io/integrations/telegram_bot/) integration, and add the chat the reports should go to as one of its allowed chats. You can use the same bot as the Pi app (see "Create the Telegram bot" in the [app's README](../../README.md#create-the-telegram-bot)): sending from both is fine.
4. Open this integration's **Configure** and pick that Telegram chat, and/or give the receipt printer's address. Both are optional. If the receipt text looks wrong, you can also give paths to `.ttf` fonts here.

Telegram messages go through the Telegram bot integration's `telegram_bot.send_message` action, so this integration never sees the bot token. They're sent as plain text, so teachers' text arrives exactly as written, and a report longer than Telegram's 4096-character limit is split into several messages.

To change the password later, use **⋮ → Reconfigure** on the integration.

## What you get

| Entity | What it does |
|---|---|
| `button.…_send_homework_report` | sends the Homework report now |
| `button.…_send_results_report` | sends the new Results now; nothing if there are none |
| `switch.…_telegram` | whether reports go to Telegram |
| `switch.…_print_receipt` | whether reports are printed |

A switch is unavailable until its channel is set up in **Configure**. Pressing a button with both switches off gives an error instead of doing nothing.

When something fails (login, Telegram, the printer), the button or action fails with the error, with secrets masked. Home Assistant shows it in the UI, or in the automation's trace and the log. Errors aren't sent to Telegram. Telegram and the printer are independent: if printing fails, the Telegram report still goes out.

## Actions (services)

`smartschool_homework.send_homework_report` and `smartschool_homework.send_results_report` do what the buttons do. Optional fields:

| Field | |
|---|---|
| `telegram`, `print` | `true`/`false` to override the switches for this call |
| `date` | homework only: pretend today is this date (like `--date`) |
| `since` | results only: report results published since this date (like `--since`) |
| `config_entry_id` | only needed if you set up more than one Smartschool account |

Both actions can return the report as a response (`message` with the text, and `count`). With `telegram: false` and `print: false` that's a preview, like `--dry-run`: nothing is sent, and the results bookkeeping isn't touched. You can use this to send the report through HA's own notifications instead of Telegram.

## Schedule with automations

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

## Notes

- HA keeps the time of the last delivered results report in its own storage (`.storage/smartschool_homework.<entry id>`), not in the app's `last_results_run.txt`.
- **Logging** is Home Assistant's: everything, including the smartschool library's messages, is under `custom_components.smartschool_homework`. To debug, use **Enable debug logging** on the integration, or:
  ```yaml
  logger:
    logs:
      custom_components.smartschool_homework: debug
  ```
  At debug level the library logs the child's username. (On its own the library would take over all of Python's logging, which would break HA's log; the integration routes it into HA's instead.)

## Development

This integration is the main source of the reports. Their logic is the `homework` package in this folder: fetching from Smartschool (`fetch.py`, `results.py`), the messages (`message.py`), Telegram's message splitting (`notify.py`) and the receipt (`printer.py`). It must not import Home Assistant.

The [stand-alone app](../../README.md) at the top of the repo runs the same reports without Home Assistant. It puts this folder on `sys.path` and imports `homework`, adding the parts HA would otherwise provide: settings from `.env`, logging, the cron schedule, and error messages to Telegram. Here, those parts are `config_flow.py`, `library_logging.py`, `reporter.py` and your automations.

Tests: the app's tests (`python -m pytest`) cover the `homework` package. This integration's own tests need Home Assistant's test harness:

```bash
pip install -r requirements_ha_test.txt
python -m pytest tests_ha
```
