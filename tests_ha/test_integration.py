import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smartschool_homework.const import DOMAIN
from custom_components.smartschool_homework.core.fetch import TZ, Item
from custom_components.smartschool_homework.core.printer import PrinterError
from custom_components.smartschool_homework.core.results import Result

REPORTER = "custom_components.smartschool_homework.reporter"
ACCOUNT = {"main_url": "myschool.smartschool.be", CONF_USERNAME: "kid.name", CONF_PASSWORD: "hunter22", "mfa": "2012-01-31"}
TELEGRAM = {"telegram_bot_token": "123:ABCsecret", "telegram_chat_id": "42"}
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


async def test_options_need_both_telegram_fields(hass: HomeAssistant):
    entry = await setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"telegram_bot_token": "123:ABC"})
    assert result["errors"] == {"base": "telegram_incomplete"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], dict(TELEGRAM, printer_address="10.0.0.9:abc"))
    assert result["errors"] == {"printer_address": "invalid_printer_address"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], dict(TELEGRAM, **PRINTER))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("switch.kid_name_myschool_smartschool_be_telegram").state == STATE_ON


async def test_switches_are_unavailable_until_set_up(hass: HomeAssistant):
    await setup(hass, TELEGRAM)
    assert hass.states.get("switch.kid_name_myschool_smartschool_be_telegram").state == STATE_ON
    assert hass.states.get("switch.kid_name_myschool_smartschool_be_print_receipt").state == STATE_UNAVAILABLE


async def test_button_sends_the_homework_report_to_telegram(hass: HomeAssistant):
    await setup(hass, TELEGRAM)
    sent = []
    with patch(f"{REPORTER}.fetch", return_value=[ITEM]), patch(f"{REPORTER}.send", side_effect=lambda s, text: sent.append(text)):
        await hass.services.async_call("button", "press", {"entity_id": "button.kid_name_myschool_smartschool_be_send_homework_report"}, blocking=True)
    assert len(sent) == 1
    assert "Verbes colonne 4" in sent[0]


async def test_switched_off_telegram_means_nowhere_to_send(hass: HomeAssistant):
    await setup(hass, TELEGRAM)
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.kid_name_myschool_smartschool_be_telegram"}, blocking=True)
    with patch(f"{REPORTER}.fetch", return_value=[ITEM]), patch(f"{REPORTER}.send") as send, pytest.raises(ServiceValidationError):
        await hass.services.async_call("button", "press", {"entity_id": "button.kid_name_myschool_smartschool_be_send_homework_report"}, blocking=True)
    send.assert_not_called()


async def test_service_returns_the_report_without_sending(hass: HomeAssistant):
    await setup(hass, TELEGRAM)
    with patch(f"{REPORTER}.fetch", return_value=[ITEM]) as fetch, patch(f"{REPORTER}.send") as send:
        response = await hass.services.async_call(DOMAIN, "send_homework_report", {"telegram": False, "date": "2026-09-29"}, blocking=True, return_response=True)
    send.assert_not_called()
    assert fetch.call_args.args[1] == date(2026, 9, 29)
    assert response["count"] == 1
    assert response["message"].startswith("📚 Due Wednesday 30 September")


async def test_printer_failure_still_sends_telegram_and_raises_one_error(hass: HomeAssistant):
    await setup(hass, dict(TELEGRAM, **PRINTER))
    sent = []
    with (
        patch(f"{REPORTER}.fetch", return_value=[ITEM]),
        patch(f"{REPORTER}.send", side_effect=lambda s, text: sent.append(text)),
        patch(f"{REPORTER}.print_image", side_effect=PrinterError("Could not print to 10.0.0.9:9100")),
        pytest.raises(HomeAssistantError, match="Homework report failed while printing: PrinterError: Could not print"),
    ):
        await hass.services.async_call(DOMAIN, "send_homework_report", {}, blocking=True)
    assert len(sent) == 1  # the report; the error isn't sent to Telegram
    assert "Verbes colonne 4" in sent[0]


async def test_fetch_failure_is_redacted_and_not_sent_to_telegram(hass: HomeAssistant):
    await setup(hass, TELEGRAM)
    with (
        patch(f"{REPORTER}.fetch", side_effect=RuntimeError("login failed for hunter22")),
        patch(f"{REPORTER}.send") as send,
        pytest.raises(HomeAssistantError) as raised,
    ):
        await hass.services.async_call(DOMAIN, "send_homework_report", {}, blocking=True)
    assert str(raised.value) == "Homework report failed while fetching from Smartschool: RuntimeError: login failed for ***"
    send.assert_not_called()


async def test_results_report_starts_after_the_last_delivered_one(hass: HomeAssistant):
    await setup(hass, TELEGRAM)
    published = datetime.now(TZ) - timedelta(hours=1)
    with patch(f"{REPORTER}.fetch_results", return_value=[result(published)]) as fetch_results, patch(f"{REPORTER}.send") as send:
        # A preview isn't a delivery, so the next report starts from the same point
        preview = await hass.services.async_call(DOMAIN, "send_results_report", {"telegram": False}, blocking=True, return_response=True)
        assert preview["count"] == 1
        first_since = fetch_results.call_args.args[1]
        send.assert_not_called()

        await hass.services.async_call(DOMAIN, "send_results_report", {}, blocking=True)
        assert abs(fetch_results.call_args.args[1] - first_since) < timedelta(minutes=1)  # still 14 days back
        send.assert_called_once()

        fetch_results.return_value = []
        await hass.services.async_call(DOMAIN, "send_results_report", {}, blocking=True)
        assert fetch_results.call_args.args[1] > datetime.now(TZ) - timedelta(minutes=1)  # since the delivered one
        send.assert_called_once()  # nothing new: nothing sent


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
