import socket
import threading
from datetime import date, datetime

import pytest
from PIL import Image

from fetch import Item
from printer import WIDTH, PrinterError, _font, escpos_raster, parse_address, print_image, render_report, wrap

TODAY = date(2026, 9, 29)
NOW = datetime(2026, 9, 29, 18, 0)


def _item(due, title, type_="homework", done=False):
    return Item(subject="Wiskunde", title=title, description=None, due=due, due_time="08:15", type=type_, type_label="Toets" if type_ == "test" else "Taak", done=done)


def test_render_is_black_and_white_and_receipt_width():
    img = render_report([_item(date(2026, 9, 30), "Oefeningen p 12"), _item(date(2026, 10, 2), "Toets H 1.3", "test")], TODAY, now=NOW)
    assert img.mode == "1"
    assert img.width == WIDTH
    assert 200 < img.height < 2000
    low, high = img.getextrema()
    assert low == 0 and high > 0  # has both black and white pixels


def test_render_empty_report():
    img = render_report([], TODAY, now=NOW)
    assert img.width == WIDTH and img.height > 100


def test_done_item_renders_differently_from_open_item():
    open_img = render_report([_item(date(2026, 9, 30), "Taak")], TODAY, now=NOW)
    done_img = render_report([_item(date(2026, 9, 30), "Taak", done=True)], TODAY, now=NOW)
    assert open_img.size == done_img.size
    assert open_img.tobytes() != done_img.tobytes()  # the check mark


def test_many_items_grow_the_canvas():
    items = [_item(date(2026, 10, 2), f"Taak nummer {n} " * 5) for n in range(60)]
    img = render_report(items, TODAY, now=NOW)
    assert img.height > 4000


def test_wrap_respects_width_and_breaks_long_words():
    font = _font("regular", 24)
    lines = wrap("kort " + "x" * 200 + " einde", font, 300)
    assert all(font.getlength(line) <= 300 for line in lines)
    assert "".join(lines).replace(" ", "") == ("kort" + "x" * 200 + "einde")


def test_escpos_raster_layout():
    img = Image.new("1", (WIDTH, 300), 1)
    img.putpixel((0, 0), 0)  # one black dot top-left
    data = escpos_raster(img)
    assert data.startswith(b"\x1b@")
    assert data.endswith(b"\x1dV\x42\x00")
    # first band: GS v 0, 72 bytes per row, 256 rows
    header = data[2:10]
    assert header == b"\x1dv0\x00" + (72).to_bytes(2, "little") + (256).to_bytes(2, "little")
    assert data[10] == 0x80  # black dot -> high bit set
    assert data.count(b"\x1dv0\x00") == 2  # 256 + 44 rows
    assert len(data) == 2 + 8 + 72 * 256 + 8 + 72 * 44 + 3 + 4


def test_parse_address():
    assert parse_address("192.168.1.50") == ("192.168.1.50", 9100)
    assert parse_address(" 192.168.1.50:9200 ") == ("192.168.1.50", 9200)
    assert parse_address("printer.local") == ("printer.local", 9100)


def test_print_image_sends_bytes_to_printer():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    received = bytearray()

    def accept():
        conn, _ = server.accept()
        with conn:
            while chunk := conn.recv(65536):
                received.extend(chunk)

    t = threading.Thread(target=accept)
    t.start()
    img = render_report([_item(date(2026, 9, 30), "Taak")], TODAY, now=NOW)
    print_image(f"127.0.0.1:{server.getsockname()[1]}", img)
    t.join(timeout=5)
    server.close()
    assert bytes(received) == escpos_raster(img)


def test_print_image_unreachable_printer_raises_printer_error():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # nothing listening on this port now
    with pytest.raises(PrinterError, match=f"127.0.0.1:{port}"):
        print_image(f"127.0.0.1:{port}", Image.new("1", (WIDTH, 10), 1), timeout=2)
