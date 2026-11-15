"""Isolated filesystem checks needed before starting a GUI operation."""

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

from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import cast

from dvdvideo import gui_support
from dvdvideo.gui_source import validate_source_links
from dvdvideo.gui_support import (
    ManagedProcess,
    OperationCancelled,
    validate_output_paths,
)
from dvdvideo.preview import preview_command

PREFLIGHT_TIMEOUT = 15


@dataclass(frozen=True)
class OperationPreflight:
    source_is_block_device: bool = False
    directory_output: bool = False
    output_path: str | None = None
    preview_command: tuple[str, ...] | None = None
    output_error: str | None = None
    source_classified: bool = False


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return cast(dict[str, object], value)


def perform_preflight(request: object, operation: ManagedProcess) -> dict[str, object]:
    data = _object(request, "preflight request")
    source = data.get("source")
    is_bluray = data.get("is_bluray")
    is_preview = data.get("preview")
    playlist = data.get("preview_playlist")
    output = data.get("output")
    if (
        not isinstance(source, str) or not isinstance(is_bluray, bool)
        or not isinstance(is_preview, bool)
        or (playlist is not None and not isinstance(playlist, str))
    ):
        raise ValueError("preflight request has invalid source or media settings")

    source_is_block_device = False
    source_classified = False
    if source:
        validate_source_links(source)
        try:
            source_mode = os.stat(source).st_mode
        except FileNotFoundError:
            pass
        else:
            source_classified = True
            source_is_block_device = stat.S_ISBLK(source_mode)

    command = None
    if is_preview:
        command = preview_command(
            source, is_bluray=is_bluray, playlist=playlist, operation=operation,
        )

    directory_output = False
    output_path = None
    output_error = None
    if output is not None:
        spec = _object(output, "output settings")
        path, name, playlists, formats = (
            spec.get("path"), spec.get("name"), spec.get("playlists"), spec.get("formats"),
        )
        output_is_bluray = spec.get("is_bluray")
        if (
            not isinstance(path, str) or not isinstance(name, str)
            or not isinstance(playlists, list) or not isinstance(formats, dict)
            or not isinstance(output_is_bluray, bool)
        ):
            raise ValueError("preflight request has invalid output settings")
        playlist_values = cast(list[object], playlists)
        format_values = cast(dict[object, object], formats)
        if (
            not all(isinstance(item, str) for item in playlist_values)
            or not all(isinstance(key, str) and isinstance(value, str) for key, value in format_values.items())
        ):
            raise ValueError("preflight request has invalid output settings")
        playlist_strings = cast(list[str], playlists)
        format_strings = cast(dict[str, str], formats)
        output_path = path
        directory_output = os.path.isdir(path)
        if output_is_bluray and not directory_output and len(playlist_strings) == 1:
            if playlist_strings[0] not in format_strings:
                raise ValueError(f"No output format is set for playlist {playlist_strings[0]}")
            extension = "." + format_strings[playlist_strings[0]]
            if os.path.splitext(output_path)[1].lower() != extension:
                output_path = os.path.splitext(output_path)[0] + extension
        try:
            validate_output_paths(
                output_path, output_is_bluray, name, playlist_strings,
                operation, formats=format_strings,
            )
        except (OSError, ValueError) as error:
            output_error = str(error)

    return {
        "source_is_block_device": source_is_block_device,
        "source_classified": source_classified,
        "directory_output": directory_output,
        "output_path": output_path,
        "preview_command": command,
        "output_error": output_error,
    }


def run_operation_preflight(
    source: str,
    is_bluray: bool,
    output: dict[str, object] | None,
    preview: bool,
    preview_playlist: str | None,
    operation: ManagedProcess,
    log: Callable[[str], None],
) -> OperationPreflight | None:
    if not source and output is None and not preview:
        return None
    request: dict[str, object] = {
        "source": source,
        "is_bluray": is_bluray,
        "output": output,
        "preview": preview,
        "preview_playlist": preview_playlist,
    }
    command = [
        sys.executable, "-c",
        ("import sys; sys.path.insert(0, sys.argv.pop(1)); "
         "from dvdvideo.gui_preflight import main; raise SystemExit(main())"),
        str(Path(__file__).parent.parent),
    ]
    result = operation.run(
        command, timeout=PREFLIGHT_TIMEOUT,
        input_data=json.dumps(request, ensure_ascii=True).encode("ascii"),
        abandon_unresponsive=True, stderr_log=log,
    )
    if result.returncode:
        raise RuntimeError(f"Operation preflight failed with exit status {result.returncode}")
    try:
        data = _object(json.loads(result.stdout), "preflight result")
    except (TypeError, ValueError) as error:
        raise RuntimeError("Operation preflight returned invalid JSON") from error
    error = data.get("error")
    if error is not None:
        if not isinstance(error, str):
            raise RuntimeError("Operation preflight returned an invalid error")
        raise RuntimeError(error)
    source_is_block_device = data.get("source_is_block_device")
    source_classified = data.get("source_classified")
    directory_output = data.get("directory_output")
    output_path = data.get("output_path")
    preview_result = data.get("preview_command")
    output_error = data.get("output_error")
    if (
        not isinstance(source_is_block_device, bool)
        or not isinstance(source_classified, bool)
        or (source_is_block_device and not source_classified)
        or not isinstance(directory_output, bool)
        or (output_path is not None and not isinstance(output_path, str))
        or (preview_result is not None and not isinstance(preview_result, list))
        or (output_error is not None and not isinstance(output_error, str))
    ):
        raise RuntimeError("Operation preflight returned an invalid result")
    preview_values = cast(list[object], preview_result) if isinstance(preview_result, list) else None
    if preview_values is not None and not all(isinstance(item, str) for item in preview_values):
        raise RuntimeError("Operation preflight returned an invalid result")
    return OperationPreflight(
        source_is_block_device,
        directory_output,
        output_path,
        tuple(cast(list[str], preview_values)) if preview_values is not None else None,
        output_error,
        source_classified,
    )


def main() -> int:
    if len(sys.argv) != 1:
        return 2
    operation = ManagedProcess()
    previous_grace = gui_support.TERMINATION_GRACE
    gui_support.TERMINATION_GRACE = 1
    previous_handlers: dict[signal.Signals, signal.Handlers] = {}

    def cancel(_signum: int, _frame: FrameType | None) -> None:
        operation.cancel()

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = cast(signal.Handlers, signal.signal(signum, cancel))
        try:
            request = json.load(sys.stdin)
            result = perform_preflight(request, operation)
        except OperationCancelled:
            return 130
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError) as error:
            result = {"error": str(error)}
        sys.stdout.write(json.dumps(result, ensure_ascii=True))
        return 0
    finally:
        gui_support.TERMINATION_GRACE = previous_grace
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
