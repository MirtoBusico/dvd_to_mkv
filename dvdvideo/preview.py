"""Build direct-disc FFplay previews without copying or temporary video files."""

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

import os
import re
import shutil
import stat
import subprocess
from collections.abc import Callable

from dvdvideo.gui_support import ManagedProcess


def preview_command(
    source: str, *, is_bluray: bool, playlist: str | None, operation: ManagedProcess,
) -> list[str]:
    operation.check_cancelled()
    if not source:
        raise RuntimeError("Choose a source first.")
    player = shutil.which("ffplay")
    if player is None:
        raise RuntimeError("Preview requires FFplay. Install it to use Preview; copying doesn't need it.")
    if is_bluray and (playlist is None or re.fullmatch(r"[0-9]{1,5}", playlist) is None):
        raise RuntimeError("Select exactly one valid Blu-ray playlist to preview.")
    path = os.path.abspath(source)
    info = os.stat(path)
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode) or stat.S_ISBLK(info.st_mode)):
        raise RuntimeError("Preview source must be a disc image, device, or disc folder.")
    if stat.S_ISDIR(info.st_mode):
        folder = os.path.basename(path).upper()
        if is_bluray and folder == "BDMV":
            path = os.path.dirname(path)
        elif not is_bluray and folder != "VIDEO_TS":
            matches = [
                os.path.join(path, entry) for entry in os.listdir(path)
                if entry.upper() == "VIDEO_TS" and os.path.isdir(os.path.join(path, entry))
            ]
            if len(matches) != 1:
                raise RuntimeError("DVD preview requires exactly one VIDEO_TS folder.")
            path = matches[0]
    capability = "-protocols" if is_bluray else "-demuxers"
    result = operation.run([player, "-hide_banner", capability], timeout=10)
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise RuntimeError(f"Could not check FFplay support: {detail}")
    supported = (
        "bluray" in result.stdout.split()
        if is_bluray else re.search(r"^\s*D\s+dvdvideo\b", result.stdout, re.MULTILINE) is not None
    )
    if not supported:
        feature = "Blu-ray protocol" if is_bluray else "dvdvideo input format"
        raise RuntimeError(f"This FFplay build lacks the {feature} required for preview.")
    operation.check_cancelled()
    command = [
        player, "-hide_banner", "-loglevel", "level+warning", "-nostats", "-autoexit",
        "-window_title", "Disc preview (2D)",
    ]
    if is_bluray:
        assert playlist is not None
        command += ["-playlist", str(int(playlist)), "-i", "bluray:" + path]
    else:
        command += ["-f", "dvdvideo", "-title", "1", "-i", path]
    return command


def play_preview(
    command: list[str], *, operation: ManagedProcess, log: Callable[[str], None],
) -> subprocess.CompletedProcess[str]:
    reported_error = False
    tail = ""

    def output(text: str) -> None:
        nonlocal reported_error, tail
        # FFplay can exit zero after an input/decoder failure; tags also span pipe reads.
        combined = tail + text
        reported_error = reported_error or "[error]" in combined or "[fatal]" in combined
        tail = combined[-8:]
        log(text)

    result = operation.run(command, collect=False, log=output, abandon_unresponsive=True)
    if reported_error:
        raise RuntimeError("FFplay reported a playback error; see Activity above.")
    return result
