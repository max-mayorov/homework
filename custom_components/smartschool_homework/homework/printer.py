"""Render the report as a black-and-white image and print it on an 80 mm ESC/POS network printer."""

from __future__ import annotations

import logging
import socket
from datetime import date, datetime
from itertools import groupby
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .fetch import TZ, next_school_day

log = logging.getLogger(__name__)

WIDTH = 576  # printable dots on 80 mm paper at 203 dpi (72 mm)
MARGIN = 8
DEFAULT_PORT = 9100
BAND_ROWS = 256  # send the raster in bands; some printers choke on one huge block

FONT_CANDIDATES = {
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
}


# Mouth for each score colour on the receipt (the printer has no colour or emoji): >0 smile, <0 frown.
FACE_MOUTHS = {"red": -1, "yellow": 0, "green": 1, "olive": 2}


class PrinterError(RuntimeError):
    pass


def _font(style: str, size: int, settings: dict[str, str] | None = None):
    override = (settings or {}).get("PRINTER_FONT_BOLD" if style == "bold" else "PRINTER_FONT")
    for path in ([override] if override else []) + FONT_CANDIDATES[style]:
        if path and Path(path).is_file():
            return ImageFont.truetype(path, size)
    if style == "bold":
        return _font("regular", size, settings)
    return ImageFont.load_default(size)


def wrap(text: str, font, max_width: int) -> list[str]:
    """Word-wrap `text` to `max_width` pixels, breaking words that are too long on their own."""
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if font.getlength(candidate) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            while font.getlength(word) > max_width:  # a single word wider than the line
                cut = len(word)
                while cut > 1 and font.getlength(word[:cut]) > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines


class _Canvas:
    """Draws top to bottom on a tall page; `image()` crops to what was used."""

    def __init__(self, settings: dict[str, str] | None):
        self.settings = settings
        self.img = Image.new("1", (WIDTH, 4000), 1)
        self.draw = ImageDraw.Draw(self.img)
        self.y = MARGIN

    def _room(self, needed: int = 600) -> None:
        if self.y + needed > self.img.height:
            bigger = Image.new("1", (WIDTH, self.img.height * 2), 1)
            bigger.paste(self.img, (0, 0))
            self.img, self.draw = bigger, ImageDraw.Draw(bigger)

    def font(self, style: str, size: int):
        return _font(style, size, self.settings)

    def text(self, text: str, size: int, style: str = "regular", indent: int = 0, gap: int = 4) -> None:
        font = self.font(style, size)
        for line in wrap(text, font, WIDTH - 2 * MARGIN - indent):
            self._room()
            self.draw.text((MARGIN + indent, self.y), line, font=font, fill=0)
            self.y += int(size * 1.25)
        self.y += gap

    def rule(self, thick: int = 2) -> None:
        self._room()
        self.y += 6
        self.draw.rectangle((MARGIN, self.y, WIDTH - MARGIN, self.y + thick - 1), fill=0)
        self.y += thick + 10

    def item(self, item, show_day: bool = False) -> None:
        self._room()
        box, top = 26, self.y + 2
        self.draw.rectangle((MARGIN, top, MARGIN + box, top + box), outline=0, width=3)
        if item.done:  # draw a check mark inside the box
            self.draw.line((MARGIN + 5, top + 13, MARGIN + 11, top + 20, MARGIN + 22, top + 5), fill=0, width=4)

        x = MARGIN + box + 12
        if item.type == "test":  # inverse "TEST" badge
            font = self.font("bold", 24)
            w = int(font.getlength("TEST")) + 12
            self.draw.rectangle((x, top - 1, x + w, top + 28), fill=0)
            self.draw.text((x + 6, top), "TEST", font=font, fill=1)
            x += w + 10

        details = [item.type_label]
        if show_day:
            details.append(f"{item.due:%A}")
        if item.due_time:
            details.append(item.due_time)
        font = self.font("bold", 26)
        heading = wrap(f"{item.subject} ({', '.join(details)})", font, WIDTH - MARGIN - x)
        for line in heading:
            self.draw.text((x, self.y), line, font=font, fill=0)
            self.y += 33
        self.y += 2

        indent = box + 12
        self.text(item.title or "(no title)", 24, indent=indent, gap=0)
        if item.description:
            self.text(item.description, 22, indent=indent, gap=0)
        self.y += 14

    def face(self, colour: str | None, x: int, top: int, size: int = 30) -> None:
        """A smiley whose mouth turns up the better the score colour; a plain dot for colours without a face."""
        d = self.draw
        if colour not in FACE_MOUTHS:
            r = size // 5
            d.ellipse((x + size // 2 - r, top + size // 2 - r, x + size // 2 + r, top + size // 2 + r), fill=0)
            return
        d.ellipse((x, top, x + size, top + size), outline=0, width=3)
        eye = max(2, size // 12)
        for ex in (x + size * 0.34, x + size * 0.66):
            d.ellipse((ex - eye, top + size * 0.36 - eye, ex + eye, top + size * 0.36 + eye), fill=0)
        left, right = x + size * 0.27, x + size * 0.73
        curve = FACE_MOUTHS[colour]  # >0 smile, <0 frown, 0 straight
        if curve == 0:
            d.line((left, top + size * 0.68, right, top + size * 0.68), fill=0, width=3)
        elif curve > 0:
            depth = size * 0.1 * curve
            d.arc((left, top + size * 0.62 - depth, right, top + size * 0.62 + depth), 0, 180, fill=0, width=3)
        else:
            d.arc((left, top + size * 0.66, right, top + size * 0.86), 180, 360, fill=0, width=3)

    def result(self, result) -> None:
        self._room()
        size, top = 30, self.y
        self.face(result.colour, MARGIN, top, size)

        x = MARGIN + size + 12
        score = f"{result.score} ({result.percentage}%)" if result.percentage is not None else result.score
        note = " (doesn't count)" if not result.counts else ""
        font = self.font("bold", 26)
        for line in wrap(f"{result.subject} · {score}{note}", font, WIDTH - MARGIN - x):
            self.draw.text((x, self.y), line, font=font, fill=0)
            self.y += 33
        self.y += 2

        indent = size + 12
        self.text(result.name or "(no name)", 24, indent=indent, gap=0)
        self.text(f"Taken {_day(result.taken)}", 22, indent=indent, gap=0)
        for text in result.feedback:
            self.text(f"“{text}”", 22, indent=indent, gap=0)
        self.y += 14

    def image(self) -> Image.Image:
        return self.img.crop((0, 0, WIDTH, self.y + MARGIN))


def _day(d: date) -> str:
    return f"{d:%A} {d.day} {d:%B}"


def render_report(items, today: date, settings: dict[str, str] | None = None, now: datetime | None = None) -> Image.Image:
    """Same content as the Telegram message, laid out for an 80 mm receipt (mode "1", 576 px wide)."""
    target = next_school_day(today)
    due_next = [i for i in items if i.due <= target]
    later = [i for i in items if i.due > target]
    now = now or datetime.now(TZ)

    c = _Canvas(settings)
    c.text("HOMEWORK", 44, "bold", gap=0)
    c.text(_day(target), 30, "bold", gap=0)
    c.text(f"Printed {now:%a %d %b %H:%M}", 20, gap=0)
    c.rule(4)

    if not items:
        c.text("Nothing due for the next school day, and nothing on the planner for the coming week.", 26)
        return c.image()

    if due_next:
        c.text(f"Due {_day(target)}", 30, "bold", gap=10)
        for item in due_next:
            c.item(item, show_day=item.due != target)
    else:
        c.text(f"Nothing due {_day(target)}.", 28, "bold")

    if later:
        c.rule()
        c.text("Coming up this week", 30, "bold", gap=6)
        for day, day_items in groupby(later, key=lambda i: i.due):
            c.text(_day(day), 26, "bold", gap=8)
            for item in day_items:
                c.item(item)
    return c.image()


def render_results(results, settings: dict[str, str] | None = None, now: datetime | None = None) -> Image.Image:
    """Same content as the Results report message, laid out for an 80 mm receipt."""
    now = now or datetime.now(TZ)
    c = _Canvas(settings)
    c.text("RESULTS", 44, "bold", gap=0)
    c.text(f"Printed {now:%a %d %b %H:%M}", 20, gap=0)
    c.rule(4)
    for result in results:
        c.result(result)
    return c.image()


def escpos_raster(img: Image.Image) -> bytes:
    """ESC/POS bytes: initialize, print `img` with GS v 0 (in bands), feed and cut."""
    img = img.convert("1")
    width_bytes = (img.width + 7) // 8
    out = bytearray(b"\x1b@")  # ESC @: initialize
    for top in range(0, img.height, BAND_ROWS):
        band = img.crop((0, top, width_bytes * 8, min(top + BAND_ROWS, img.height)))
        # PIL mode "1" packs white as 1; ESC/POS prints 1 bits as black, so invert.
        data = bytes(b ^ 0xFF for b in band.tobytes())
        out += b"\x1dv0\x00" + width_bytes.to_bytes(2, "little") + band.height.to_bytes(2, "little") + data
    out += b"\x1bd\x04"  # ESC d 4: feed 4 lines
    out += b"\x1dV\x42\x00"  # GS V 66 0: feed to cutter and partial cut
    return bytes(out)


def parse_address(address: str) -> tuple[str, int]:
    """"host", "host:port", "[IPv6]" or "[IPv6]:port" as (host, port). Raises ValueError for anything else."""
    address = address.strip()
    host, port = address, str(DEFAULT_PORT)
    if address.startswith("["):
        host, _, rest = address[1:].partition("]")
        if rest:
            if not rest.startswith(":"):
                raise ValueError(f"Not a printer address: {address!r}")
            port = rest[1:]
    elif address.count(":") == 1:
        host, port = address.split(":")
    host, port = host.strip(), int(port)
    if not host or not 0 < port < 65536:
        raise ValueError(f"Not a printer address: {address!r}")
    return host, port


def print_image(address: str, img: Image.Image, timeout: float = 15.0) -> None:
    host, port = parse_address(address)
    payload = escpos_raster(img)
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(payload)
    except OSError as exc:
        raise PrinterError(f"Could not print to {host}:{port} ({type(exc).__name__}: {exc})") from None
    log.info("Printed report (%dx%d px, %d bytes)", img.width, img.height, len(payload))
