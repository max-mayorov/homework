"""Constants for the Smartschool Homework integration."""

from __future__ import annotations

DOMAIN = "smartschool_homework"

# Config entry data (set up in the config flow)
CONF_MAIN_URL = "main_url"
CONF_MFA = "mfa"

# Config entry options (Telegram and the receipt printer, both optional)
CONF_TELEGRAM_BOT_TOKEN = "telegram_bot_token"
CONF_TELEGRAM_CHAT_ID = "telegram_chat_id"
CONF_PRINTER_ADDRESS = "printer_address"
CONF_PRINTER_FONT = "printer_font"
CONF_PRINTER_FONT_BOLD = "printer_font_bold"

# Service calls
SERVICE_HOMEWORK_REPORT = "send_homework_report"
SERVICE_RESULTS_REPORT = "send_results_report"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_DATE = "date"
ATTR_SINCE = "since"
ATTR_TELEGRAM = "telegram"
ATTR_PRINT = "print"
