"""
ANSI escape sequence parser for terminal rendering.

Parses VT100/ANSI codes and converts to Tkinter text tags.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

# ANSI color codes to hex
ANSI_COLORS = {
    # Standard colors
    0: "#000000",   # Black
    1: "#cd0000",   # Red
    2: "#00cd00",   # Green
    3: "#cdcd00",   # Yellow
    4: "#0000ee",   # Blue
    5: "#cd00cd",   # Magenta
    6: "#00cdcd",   # Cyan
    7: "#e5e5e5",   # White
    # Bright colors
    8: "#7f7f7f",   # Bright Black (Gray)
    9: "#ff0000",   # Bright Red
    10: "#00ff00",  # Bright Green
    11: "#ffff00",  # Bright Yellow
    12: "#5c5cff",  # Bright Blue
    13: "#ff00ff",  # Bright Magenta
    14: "#00ffff",  # Bright Cyan
    15: "#ffffff",  # Bright White
}

# Extended 256 colors (basic + cube + grayscale)
def get_256_color(n: int) -> str:
    """Get hex color for 256-color palette."""
    if n < 16:
        return ANSI_COLORS.get(n, "#ffffff")
    elif n < 232:
        # 6x6x6 color cube
        n -= 16
        b = n % 6
        g = (n // 6) % 6
        r = n // 36
        return f"#{r * 51:02x}{g * 51:02x}{b * 51:02x}"
    else:
        # Grayscale
        gray = (n - 232) * 10 + 8
        return f"#{gray:02x}{gray:02x}{gray:02x}"


@dataclass
class TextStyle:
    """Current text style state."""
    fg: str = "#d4d4d4"      # Foreground color
    bg: str = "#1e1e1e"      # Background color
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    reverse: bool = False
    hidden: bool = False
    strikethrough: bool = False

    def copy(self) -> "TextStyle":
        return TextStyle(
            fg=self.fg, bg=self.bg, bold=self.bold, dim=self.dim,
            italic=self.italic, underline=self.underline, blink=self.blink,
            reverse=self.reverse, hidden=self.hidden, strikethrough=self.strikethrough
        )

    def reset(self) -> None:
        self.fg = "#d4d4d4"
        self.bg = "#1e1e1e"
        self.bold = False
        self.dim = False
        self.italic = False
        self.underline = False
        self.blink = False
        self.reverse = False
        self.hidden = False
        self.strikethrough = False

    def to_tag_name(self) -> str:
        """Generate unique tag name for this style."""
        parts = [self.fg.replace("#", "fg"), self.bg.replace("#", "bg")]
        if self.bold:
            parts.append("bold")
        if self.italic:
            parts.append("italic")
        if self.underline:
            parts.append("underline")
        if self.strikethrough:
            parts.append("strike")
        return "_".join(parts)


@dataclass
class ParsedSegment:
    """A segment of text with associated style."""
    text: str
    style: TextStyle


class ANSIParser:
    """
    Parse ANSI escape sequences and convert to styled text segments.
    """

    # Regex patterns
    CSI_PATTERN = re.compile(r'\x1b\[([0-9;]*)([A-Za-z])')
    OSC_PATTERN = re.compile(r'\x1b\]([^\x07\x1b]*)(?:\x07|\x1b\\)')
    SIMPLE_ESCAPE = re.compile(r'\x1b[()][AB012]')  # Charset selection

    def __init__(self, default_fg: str = "#d4d4d4", default_bg: str = "#1e1e1e"):
        self.default_fg = default_fg
        self.default_bg = default_bg
        self.style = TextStyle(fg=default_fg, bg=default_bg)
        self.buffer = ""

    def reset(self) -> None:
        """Reset parser state."""
        self.style = TextStyle(fg=self.default_fg, bg=self.default_bg)
        self.buffer = ""

    def parse(self, data: str) -> List[ParsedSegment]:
        """
        Parse input data and return list of styled segments.
        """
        segments: List[ParsedSegment] = []
        self.buffer += data

        i = 0
        text_start = 0

        while i < len(self.buffer):
            if self.buffer[i] == '\x1b':
                # Flush text before escape sequence
                if i > text_start:
                    text = self.buffer[text_start:i]
                    if text:
                        segments.append(ParsedSegment(text, self.style.copy()))

                # Try to match CSI sequence
                csi_match = self.CSI_PATTERN.match(self.buffer, i)
                if csi_match:
                    self._handle_csi(csi_match.group(1), csi_match.group(2))
                    i = csi_match.end()
                    text_start = i
                    continue

                # Try to match OSC sequence
                osc_match = self.OSC_PATTERN.match(self.buffer, i)
                if osc_match:
                    # OSC sequences (title, etc.) - ignore for now
                    i = osc_match.end()
                    text_start = i
                    continue

                # Try to match simple escape
                simple_match = self.SIMPLE_ESCAPE.match(self.buffer, i)
                if simple_match:
                    i = simple_match.end()
                    text_start = i
                    continue

                # Check for incomplete sequence at end
                if i == len(self.buffer) - 1 or (
                    i < len(self.buffer) - 1 and self.buffer[i + 1] == '['
                ):
                    # Might be incomplete, save for later
                    break

                # Unknown escape, skip
                i += 1
                text_start = i
            else:
                i += 1

        # Flush remaining text
        if text_start < len(self.buffer):
            remaining = self.buffer[text_start:]
            # Check if we have incomplete escape at end
            if '\x1b' in remaining:
                esc_pos = remaining.rfind('\x1b')
                if esc_pos > 0:
                    segments.append(ParsedSegment(remaining[:esc_pos], self.style.copy()))
                self.buffer = remaining[esc_pos:]
            else:
                segments.append(ParsedSegment(remaining, self.style.copy()))
                self.buffer = ""
        else:
            self.buffer = ""

        return segments

    def _handle_csi(self, params: str, command: str) -> None:
        """Handle CSI escape sequence."""
        if command == 'm':
            # SGR - Select Graphic Rendition
            self._handle_sgr(params)
        # Other commands (cursor movement, etc.) can be added here

    def _handle_sgr(self, params: str) -> None:
        """Handle SGR (color/style) codes."""
        if not params:
            params = "0"

        codes = [int(p) if p else 0 for p in params.split(';')]
        i = 0

        while i < len(codes):
            code = codes[i]

            if code == 0:
                self.style.reset()
            elif code == 1:
                self.style.bold = True
            elif code == 2:
                self.style.dim = True
            elif code == 3:
                self.style.italic = True
            elif code == 4:
                self.style.underline = True
            elif code == 5 or code == 6:
                self.style.blink = True
            elif code == 7:
                self.style.reverse = True
            elif code == 8:
                self.style.hidden = True
            elif code == 9:
                self.style.strikethrough = True
            elif code == 22:
                self.style.bold = False
                self.style.dim = False
            elif code == 23:
                self.style.italic = False
            elif code == 24:
                self.style.underline = False
            elif code == 25:
                self.style.blink = False
            elif code == 27:
                self.style.reverse = False
            elif code == 28:
                self.style.hidden = False
            elif code == 29:
                self.style.strikethrough = False
            elif 30 <= code <= 37:
                # Standard foreground colors
                self.style.fg = ANSI_COLORS[code - 30]
            elif code == 38:
                # Extended foreground color
                if i + 2 < len(codes) and codes[i + 1] == 5:
                    # 256 color
                    self.style.fg = get_256_color(codes[i + 2])
                    i += 2
                elif i + 4 < len(codes) and codes[i + 1] == 2:
                    # True color RGB
                    r, g, b = codes[i + 2], codes[i + 3], codes[i + 4]
                    self.style.fg = f"#{r:02x}{g:02x}{b:02x}"
                    i += 4
            elif code == 39:
                self.style.fg = self.default_fg
            elif 40 <= code <= 47:
                # Standard background colors
                self.style.bg = ANSI_COLORS[code - 40]
            elif code == 48:
                # Extended background color
                if i + 2 < len(codes) and codes[i + 1] == 5:
                    # 256 color
                    self.style.bg = get_256_color(codes[i + 2])
                    i += 2
                elif i + 4 < len(codes) and codes[i + 1] == 2:
                    # True color RGB
                    r, g, b = codes[i + 2], codes[i + 3], codes[i + 4]
                    self.style.bg = f"#{r:02x}{g:02x}{b:02x}"
                    i += 4
            elif code == 49:
                self.style.bg = self.default_bg
            elif 90 <= code <= 97:
                # Bright foreground colors
                self.style.fg = ANSI_COLORS[code - 90 + 8]
            elif 100 <= code <= 107:
                # Bright background colors
                self.style.bg = ANSI_COLORS[code - 100 + 8]

            i += 1
