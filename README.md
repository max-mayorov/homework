# Smartschool homework → Telegram

Every evening this checks your child's Smartschool planner and sends you a short summary in plain English via Telegram. The summary covers what's due tomorrow, with tests flagged, and what's coming up in the next 7 days.

```
fetch.py    Smartschool planner  →  list of Item(subject, title, description, due, type)
explain.py  items               →  English summary (Anthropic API)
notify.py   summary             →  Telegram (split at 4096 characters)
main.py     runs the three steps; any failure is sent to you as a short Telegram message
probe.py    one-off diagnostic: dumps raw Smartschool data for the next 7 days
```

It uses the unofficial [`smartschool`](https://github.com/svaningelgem/smartschool) library. That library has no parent support as such, but a parent login (your child's username plus your own password) works. Only the **planner** (`PlannedElements`) returns data for a parent login. `FutureTasks` and the agenda lessons come back empty, so the app doesn't use them.

## Setup

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
| `ANTHROPIC_API_KEY` | from https://console.anthropic.com |
| `ANTHROPIC_MODEL` | optional, default `claude-opus-5-5` |
| `TELEGRAM_BOT_TOKEN` | from BotFather (below) |
| `TELEGRAM_CHAT_ID` | your chat id (below) |

Instead of `.env` you can use a `credentials.yml` next to the code:

```yaml
username: child.username
password: parent-password
main_url: myschool.smartschool.be
mfa: 2012-01-31
ANTHROPIC_API_KEY: sk-ant-...
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
.venv/bin/python main.py --dry-run                   # print the summary, don't send
.venv/bin/python main.py --dry-run --date 2026-10-05 # pretend today is 5 Oct
.venv/bin/python main.py                             # fetch, summarize, send
.venv/bin/python -m pytest                           # unit tests (fixture data, no logins)
```

"Tomorrow" means the next calendar day in Europe/Brussels time. On a Friday evening that's Saturday, so the message will usually say nothing is due tomorrow and list Monday's items under "coming up this week".

If any step fails (login, Anthropic API, Telegram), you get a short Telegram message naming the step and the error, with every configured secret masked. If Telegram itself is the step that fails, the error goes to stderr and the exit code is 1.

## Run it daily at 18:00 (Europe/Brussels)

With cron, on any Linux or macOS machine that's on at 18:00:

```cron
CRON_TZ=Europe/Brussels
0 18 * * * cd /path/to/homework && .venv/bin/python main.py >> "$HOME/homework.log" 2>&1
```

`CRON_TZ` works with cronie (Fedora, Arch, most other distros) and on macOS. On Debian/Ubuntu's default cron, `CRON_TZ` is ignored, so either set the machine's timezone to Europe/Brussels (`sudo timedatectl set-timezone Europe/Brussels`) or convert 18:00 to the machine's timezone yourself.

The app only needs outbound HTTPS access to your school's `*.smartschool.be` host, `api.anthropic.com` and `api.telegram.org`. Nothing about it is tied to a particular host.

## Privacy

- The log shows only counts, the model name and step names, never homework text or names. The smartschool library logs the username at INFO level; that's filtered out.
- The homework text is sent to the Anthropic API to write the summary, and the summary goes to Telegram.
- The smartschool library keeps its session cookies and the logged-in user's profile under `~/.cache/smartschool/<username>/`.
- `probe.py` prints raw data, your child's included, to the terminal. `probe_output*.txt` is git-ignored.

## Known limitations

- The planner list only has a title per item. The teacher's full text is usually in the title, and `description` is empty unless Smartschool starts sending one. The summary says "(no further details given)" when there's only a short title.
- Item types come from the school's own labels (`Toets`, `Grote toets` → test; `Taak`, `Opdracht`, `Les leren` → homework; `Meebrengen` → bring; anything else → other). If your school uses other labels, add them in `fetch.py`.
