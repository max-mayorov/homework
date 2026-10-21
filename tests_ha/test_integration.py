import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smartschool_homework.const import DOMAIN
from custom_components.smartschool_homework.core.fetch import TZ, Item
from custom_components.smartschool_homework.core.printer import PrinterError
from custom_components.smartschool_homework.core.results import Result

REPORTER = "custom_components.smartschool_homework.reporter"
ACCOUNT = {"main_url": "myschool.smartschool.be", CONF_USERNAME: "kid.name", CONF_PASSWORD: "hunter22", "mfa": "2012-01-31"}
TELEGRAM = {"telegram_chat": "bot-entry:42"}
PRINTER = {"printer_address": "10.0.0.9"}

ITEM = Item("Frans", "Verbes colonne 4", None, date(2026, 9, 30), None, "test", "Toets")


def result(published: datetime) -> Result:
    return Result("Muziek", "Opdracht: piano app", "10/10", 100, "olive", published.date(), published)


async def setup(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="kid.name (myschool.smartschool.be)", data=ACCOUNT, options=options or {}, unique_id="myschool.smartschool.be/kid.name")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def telegram(hass: HomeAssistant) -> list[dict]:
    """A stand-in for the Telegram bot integration's send_message action. Returns the calls it gets."""
    calls: list[dict] = []

    async def send_message(call: ServiceCall):
        calls.append(dict(call.data))
        return {"chats": [{"chat_id": 42, "message_id": len(calls)}]}

    hass.services.async_register("telegram_bot", "send_message", send_message, supports_response=SupportsResponse.OPTIONAL)
    return calls


async def test_config_flow_logs_in_and_creates_the_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    with patch("custom_components.smartschool_homework.config_flow._try_login", return_value="invalid_auth"):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], ACCOUNT)
    assert result["errors"] == {"base": "invalid_auth"}

    with patch("custom_components.smartschool_homework.config_flow._try_login", return_value=None):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(ACCOUNT, main_url="https://myschool.smartschool.be/"))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["main_url"] == "myschool.smartschool.be"


async def test_options_offer_the_telegram_bot_chats(hass: HomeAssistant):
    bot = MockConfigEntry(
        domain="telegram_bot",
        title="Home bot",
        subentries_data=[ConfigSubentryData(data={"chat_id": 42}, subentry_type="allowed_chat_ids", title="Family", unique_id="42")],
    )
    bot.add_to_hass(hass)
    entry = await setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    chat_field = next(f for f in result["data_schema"].schema if f == "telegram_chat")
    assert result["data_schema"].schema[chat_field].config["options"] == [{"value": f"{bot.entry_id}:42", "label": "Home bot: Family"}]

    result = await hass.config_entries.options.async_configure(result["flow_id"], {"telegram_chat": f"{bot.entry_id}:42", "printer_address": "10.0.0.9:abc"})
    assert result["errors"] == {"printer_address": "invalid_printer_address"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"telegram_chat": f"{bot.entry_id}:42", **PRINTER})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"telegram_chat": f"{bot.entry_id}:42", **PRINTER}
    await hass.async_block_till_done()
    assert hass.states.get("switch.kid_name_myschool_smartschool_be_telegram").state == STATE_ON


async def test_options_without_a_telegram_bot_have_no_telegram_field(hass: HomeAssistant):
    entry = await setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "telegram_chat" not in [str(f) for f in result["data_schema"].schema]


async def test_switches_are_unavailable_until_set_up(hass: HomeAssistant):
    await setup(hass, TELEGRAM)
    assert hass.states.get("switch.kid_name_myschool_smartschool_be_telegram").state == STATE_ON
    assert hass.states.get("switch.kid_name_myschool_smartschool_be_print_receipt").state == STATE_UNAVAILABLE


async def test_button_sends_the_report_through_the_telegram_bot_as_plain_text(hass: HomeAssistant, telegram):
    await setup(hass, TELEGRAM)
    with patch(f"{REPORTER}.fetch", return_value=[ITEM]):
        await hass.services.async_call("button", "press", {"entity_id": "button.kid_name_myschool_smartschool_be_send_homework_report"}, blocking=True)
    assert len(telegram) == 1
    assert telegram[0]["config_entry_id"] == "bot-entry"
    assert telegram[0]["target"] == [42]
    assert telegram[0]["parse_mode"] == "plain_text"
    assert "Verbes colonne 4" in telegram[0]["message"]


async def test_long_reports_are_split_at_telegrams_limit(hass: HomeAssistant, telegram):
    await setup(hass, TELEGRAM)
    items = [Item("Frans", f"Les {n}: " + "x" * 200, None, date(2026, 9, 30), None, "homework", "Taak") for n in range(40)]
    with patch(f"{REPORTER}.fetch", return_value=items):
        await hass.services.async_call(DOMAIN, "send_homework_report", {"date": "2026-09-29"}, blocking=True)
    assert len(telegram) > 1
    assert all(len(call["message"]) <= 4096 for call in telegram)
    assert "".join(call["message"] for call in telegram).count("Les ") == 40


async def test_telegram_failure_is_raised(hass: HomeAssistant):
    async def send_message(call: ServiceCall):
        raise HomeAssistantError("Chat not found")

    hass.services.async_register("telegram_bot", "send_message", send_message, supports_response=SupportsResponse.OPTIONAL)
    await setup(hass, TELEGRAM)
    with patch(f"{REPORTER}.fetch", return_value=[ITEM]), pytest.raises(HomeAssistantError, match="Homework report failed while sending to Telegram: HomeAssistantError: Chat not found"):
        await hass.services.async_call(DOMAIN, "send_homework_report", {}, blocking=True)


async def test_switched_off_telegram_means_nowhere_to_send(hass: HomeAssistant, telegram):
    await setup(hass, TELEGRAM)
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.kid_name_myschool_smartschool_be_telegram"}, blocking=True)
    with patch(f"{REPORTER}.fetch", return_value=[ITEM]), pytest.raises(ServiceValidationError):
        await hass.services.async_call("button", "press", {"entity_id": "button.kid_name_myschool_smartschool_be_send_homework_report"}, blocking=True)
    assert telegram == []


async def test_service_returns_the_report_without_sending(hass: HomeAssistant, telegram):
    await setup(hass, TELEGRAM)
    with patch(f"{REPORTER}.fetch", return_value=[ITEM]) as fetch:
        response = await hass.services.async_call(DOMAIN, "send_homework_report", {"telegram": False, "date": "2026-09-29"}, blocking=True, return_response=True)
    assert telegram == []
    assert fetch.call_args.args[1] == date(2026, 9, 29)
    assert response["count"] == 1
    assert response["message"].startswith("📚 Due Wednesday 30 September")


async def test_printer_failure_still_sends_telegram_and_raises_one_error(hass: HomeAssistant, telegram):
    await setup(hass, dict(TELEGRAM, **PRINTER))
    with (
        patch(f"{REPORTER}.fetch", return_value=[ITEM]),
        patch(f"{REPORTER}.print_image", side_effect=PrinterError("Could not print to 10.0.0.9:9100")),
        pytest.raises(HomeAssistantError, match="Homework report failed while printing: PrinterError: Could not print"),
    ):
        await hass.services.async_call(DOMAIN, "send_homework_report", {}, blocking=True)
    assert len(telegram) == 1  # the report; the error isn't sent to Telegram
    assert "Verbes colonne 4" in telegram[0]["message"]


async def test_fetch_failure_is_redacted_and_not_sent_to_telegram(hass: HomeAssistant, telegram):
    await setup(hass, TELEGRAM)
    with patch(f"{REPORTER}.fetch", side_effect=RuntimeError("login failed for hunter22")), pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(DOMAIN, "send_homework_report", {}, blocking=True)
    assert str(raised.value) == "Homework report failed while fetching from Smartschool: RuntimeError: login failed for ***"
    assert telegram == []


async def test_results_report_starts_after_the_last_delivered_one(hass: HomeAssistant, telegram):
    await setup(hass, TELEGRAM)
    published = datetime.now(TZ) - timedelta(hours=1)
    with patch(f"{REPORTER}.fetch_results", return_value=[result(published)]) as fetch_results:
        # A preview isn't a delivery, so the next report starts from the same point
        preview = await hass.services.async_call(DOMAIN, "send_results_report", {"telegram": False}, blocking=True, return_response=True)
        assert preview["count"] == 1
        first_since = fetch_results.call_args.args[1]
        assert telegram == []

        await hass.services.async_call(DOMAIN, "send_results_report", {}, blocking=True)
        assert abs(fetch_results.call_args.args[1] - first_since) < timedelta(minutes=1)  # still 14 days back
        assert len(telegram) == 1

        fetch_results.return_value = []
        await hass.services.async_call(DOMAIN, "send_results_report", {}, blocking=True)
        assert fetch_results.call_args.args[1] > datetime.now(TZ) - timedelta(minutes=1)  # since the delivered one
        assert len(telegram) == 1  # nothing new: nothing sent


def test_library_logs_go_to_the_integration_logger():
    # In a fresh interpreter, imported the way Home Assistant imports the integration
    code = """
import logging, sys
import custom_components.smartschool_homework
import smartschool
from smartschool import _session
assert not hasattr(sys.modules["logprise"], "appriser"), "the real logprise was imported"
assert not hasattr(logging.Logger._log, "_intercepted_by_logprise"), "logging was taken over"

records = []
handler = logging.Handler()
handler.emit = records.append
logging.getLogger("custom_components.smartschool_homework").addHandler(handler)
logging.getLogger("custom_components.smartschool_homework").setLevel(logging.DEBUG)
_session.logger.info("Logging in with {}", "kid")
assert [(r.name, r.getMessage()) for r in records] == [("custom_components.smartschool_homework.smartschool", "Logging in with kid")], records
"""
    root = Path(__file__).resolve().parent.parent
    subprocess.run([sys.executable, "-c", code], cwd=root, check=True)
