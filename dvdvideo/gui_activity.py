"""Thread-safe, bounded Activity output buffering independent of GTK."""

# @copyright: 2026 libertypo <libertypo@proton.me>
# @license: GNU GPL-3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import re
import threading
from collections import deque

MAX_PENDING_CHARS = 256 * 1024
MAX_FLUSH_CHARS = 16 * 1024
# GTK lays out each line as a whole; unbroken output would grow memory without bound.
MAX_LOG_LINE_CHARS = 1024
# C0/C1 controls (except tab and newline) and bidirectional overrides can disguise external text.
UNSAFE_TEXT = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069\ud800-\udfff]")


def clean_text(text: str) -> str:
    return UNSAFE_TEXT.sub("", text)


class ActivityBuffer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: deque[str] = deque()
        self._pending_chars = 0
        self._dropped_chars = 0
        self._column = 0

    def _break_long_lines(self, text: str) -> str:
        pieces: list[str] = []
        for index, part in enumerate(text.split("\n")):
            if index:
                pieces.append("\n")
                self._column = 0
            start = 0
            while self._column + len(part) - start > MAX_LOG_LINE_CHARS:
                room = MAX_LOG_LINE_CHARS - self._column
                pieces += [part[start:start + room], "\n"]
                start += room
                self._column = 0
            pieces.append(part[start:])
            self._column += len(part) - start
        return "".join(pieces)

    def queue(self, text: str) -> None:
        dropped = max(0, len(text) - MAX_PENDING_CHARS)
        text = clean_text(text[-MAX_PENDING_CHARS:])
        if not text and not dropped:
            return
        with self._lock:
            self._dropped_chars += dropped
            if not text:
                return
            text = self._break_long_lines(text)
            if len(text) > MAX_PENDING_CHARS:
                self._dropped_chars += len(text) - MAX_PENDING_CHARS
                text = text[-MAX_PENDING_CHARS:]
            self._pending.append(text)
            self._pending_chars += len(text)
            while self._pending_chars > MAX_PENDING_CHARS:
                removed = self._pending.popleft()
                self._pending_chars -= len(removed)
                self._dropped_chars += len(removed)

    def drain(self) -> tuple[str, int]:
        with self._lock:
            text = "".join(self._pending)
            dropped = self._dropped_chars
            self._pending.clear()
            self._pending_chars = 0
            self._dropped_chars = 0
        if len(text) > MAX_FLUSH_CHARS:
            dropped += len(text) - MAX_FLUSH_CHARS
            text = text[-MAX_FLUSH_CHARS:]
        return text, dropped

    def clear(self) -> None:
        with self._lock:
            self._pending.clear()
            self._pending_chars = 0
            self._dropped_chars = 0
            self._column = 0
