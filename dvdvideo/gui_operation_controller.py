"""Coordinate GUI operation decisions and lifecycle without importing GTK."""

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

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dvdvideo.gui_commands import (
    CommandInput,
    PlaylistChoice,
    build_bluray_streams_command,
    build_command,
    build_disc_details_command,
)
from dvdvideo.gui_listing import (
    Listing,
    parse_bluray_streams,
    parse_dvd_streams,
    parse_playlists,
)
from dvdvideo.gui_operations import (
    OperationHooks,
    OperationRequest,
    OperationResult,
    OutputSpec,
    VerificationSpec,
    WorkerLifecycle,
    execute_operation,
)
from dvdvideo.gui_preferences import SourcePreferences
from dvdvideo.gui_selection import SelectionCoordinator
from dvdvideo.gui_support import ManagedProcess


@dataclass(frozen=True)
class OperationInputs:
    script_path: str
    source: str
    is_bluray: bool
    detecting: bool
    generation: int
    preferences: SourcePreferences | None
    output_path: str
    output_format: str
    output_name: str
    minimum_minutes: int
    selected: tuple[str, ...]


@dataclass(frozen=True)
class ListingHooks:
    clear_rows: Callable[[], None]
    load_rows: Callable[[str | Listing], None]
    load_stream_rows: Callable[[str, str | Listing, list[str] | None], None]
    update_stream_format: Callable[[str], None]


@dataclass(frozen=True)
class DialogHooks:
    show_disc_details: Callable[[str, str], None]
    present_m2ts_confirmation: Callable[[str], None]
    present_verification_dialog: Callable[[str, bool, str, list[str], int], None]


@dataclass(frozen=True)
class OperationUiHooks:
    log_inspect_action: Callable[[], None]
    set_busy: Callable[[bool], None]
    set_status: Callable[[str], None]
    invalidate_choosers: Callable[[], None]
    set_output_path: Callable[[str], None]


@dataclass(frozen=True)
class OperationRuntimeHooks:
    cancel_drive_scan: Callable[[], None]
    start_worker: Callable[[Callable[[], None]], bool]
    dispatch_ui: Callable[[Callable[[], object]], object]
    queue_log: Callable[[str], None]
    log: Callable[[str], None]
    exclude_device_source: Callable[[str], None]
    confirm_non_device: Callable[[str], None] = lambda _source: None
    is_known_device_source: Callable[[str], bool] = lambda _source: False


@dataclass(frozen=True)
class OperationControllerHooks:
    get_inputs: Callable[[], OperationInputs]
    listing: ListingHooks
    dialogs: DialogHooks
    ui: OperationUiHooks
    runtime: OperationRuntimeHooks


class OperationController:
    def __init__(
        self,
        lifecycle: WorkerLifecycle,
        selection: SelectionCoordinator,
        hooks: OperationControllerHooks,
    ) -> None:
        self.lifecycle = lifecycle
        self.selection = selection
        self.hooks = hooks

    def selected_for_copy(self, inputs: OperationInputs | None = None) -> list[str]:
        inputs = inputs or self.hooks.get_inputs()
        previous = inputs.preferences
        return self.selection.selection_state.selected_ids(
            previous,
            is_bluray=inputs.is_bluray,
            selected=list(inputs.selected),
        )

    def streams_for_copy(
        self, playlist: str, inputs: OperationInputs | None = None,
    ) -> list[str]:
        inputs = inputs or self.hooks.get_inputs()
        previous = inputs.preferences
        return self.selection.selection_state.selected_streams(
            previous, playlist, self.selection.playlist_streams[playlist],
        )

    def playlist_format(self, playlist: str, inputs: OperationInputs | None = None) -> str:
        inputs = inputs or self.hooks.get_inputs()
        requested = inputs.output_format or "auto"
        if requested == "auto":
            return "m2ts" if self.selection.playlist_mvc.get(playlist, False) else "mkv"
        return requested

    def command(self, inspect: bool = False) -> list[str] | None:
        inputs = self.hooks.get_inputs()
        source = inputs.source
        if not source:
            self.hooks.runtime.log("Choose a source first.")
            return None
        is_bluray = inputs.is_bluray
        selected = () if inspect else tuple(self.selected_for_copy(inputs))
        playlists: list[PlaylistChoice] = []
        if is_bluray and not inspect:
            for identifier in selected:
                output_format = self.playlist_format(identifier, inputs)
                streams = (
                    tuple(self.streams_for_copy(identifier, inputs))
                    if output_format != "m2ts" and identifier in self.selection.playlist_streams
                    else None
                )
                playlists.append(PlaylistChoice(identifier, output_format, streams))
                if streams == ():
                    break
        request = CommandInput(
            script_path=inputs.script_path,
            source=source,
            is_bluray=is_bluray,
            inspect=inspect,
            minimum_minutes=(
                inputs.minimum_minutes if is_bluray and inspect else 2
            ),
            output=inputs.output_path if not inspect else "",
            output_format=(
                inputs.output_format or "auto"
                if is_bluray and not inspect else "auto"
            ),
            selected=selected,
            playlists=tuple(playlists),
        )
        try:
            return build_command(request)
        except ValueError as error:
            self.hooks.runtime.log(str(error))
            return None

    def output_snapshot(self, command: list[str]) -> OutputSpec:
        inputs = self.hooks.get_inputs()
        selected = self.selected_for_copy(inputs)
        is_bluray = inputs.is_bluray
        return OutputSpec(
            command[-1],
            is_bluray,
            inputs.output_name.strip(),
            tuple(selected),
            tuple((playlist, self.playlist_format(playlist, inputs)) for playlist in selected)
            if is_bluray else (),
        )

    def inspect(self) -> None:
        inputs = self.hooks.get_inputs()
        if self.lifecycle.running or inputs.detecting:
            self.hooks.runtime.log("Wait for the current operation before inspecting.")
            return
        command = self.command(inspect=True)
        if command:
            requires_reinspection = self.selection.requires_reinspection
            try:
                self.hooks.listing.clear_rows()
            finally:
                self.selection.requires_reinspection = requires_reinspection
            parser = parse_playlists if inputs.is_bluray else parse_dvd_streams
            self.start(command, on_listing=self.hooks.listing.load_rows, listing_parser=parser)

    def preview_selected(self) -> None:
        inputs = self.hooks.get_inputs()
        if self.selection.requires_reinspection:
            self.hooks.runtime.log("Inspect the current disc again before using its selections.")
            return
        if self.lifecycle.running or inputs.detecting or self.lifecycle.closing:
            self.hooks.runtime.log("Wait for the current operation before previewing.")
            return
        if not inputs.source:
            self.hooks.runtime.log("Choose a source first.")
            return
        playlist = None
        if inputs.is_bluray:
            selected = self.selected_for_copy(inputs)
            if len(selected) != 1:
                self.hooks.runtime.log("Select exactly one playlist to preview.")
                return
            playlist = selected[0]
        self.start([], preview=True, preview_playlist=playlist)

    def inspect_disc_details(self) -> None:
        inputs = self.hooks.get_inputs()
        if self.selection.requires_reinspection:
            self.hooks.runtime.log("Inspect the current disc again before using its selections.")
            return
        if self.lifecycle.running or inputs.detecting or self.lifecycle.closing:
            self.hooks.runtime.log("Wait for the current operation before reading disc details.")
            return
        source = inputs.source
        if not source:
            self.hooks.runtime.log("Choose a source first.")
            return
        is_bluray = inputs.is_bluray
        playlist = None
        if is_bluray:
            selected = self.selected_for_copy(inputs)
            if len(selected) > 1:
                self.hooks.runtime.log("Select one playlist for detailed tracks, or none for a disc overview.")
                return
            playlist = selected[0] if selected else None
        command = build_disc_details_command(
            inputs.script_path, source, is_bluray=is_bluray, playlist=playlist,
        )
        self.start(
            command, lambda output: self.hooks.dialogs.show_disc_details(output, source),
        )

    def copy_selected(self) -> None:
        inputs = self.hooks.get_inputs()
        if self.selection.requires_reinspection:
            self.hooks.runtime.log("Inspect the current disc again before using its selections.")
            return
        if self.lifecycle.running or inputs.detecting or self.lifecycle.closing:
            self.hooks.runtime.log("Wait for the current operation before copying.")
            return
        if not inputs.source:
            self.hooks.runtime.log("Choose a source first.")
            return
        if inputs.is_bluray:
            selected = self.selected_for_copy(inputs)
            for playlist in selected:
                if (
                    inputs.output_format != "m2ts"
                    and playlist not in self.selection.playlist_mvc
                ):
                    command = build_bluray_streams_command(
                        inputs.script_path, inputs.source, playlist,
                    )

                    def inspected(output: Listing, playlist: str = playlist) -> None:
                        self.hooks.listing.load_stream_rows(playlist, output, None)
                        if playlist in self.selection.playlist_mvc:
                            self.copy_selected()

                    self.start(
                        command, on_listing=inspected, listing_parser=parse_bluray_streams,
                    )
                    return
            for playlist in selected:
                if self.playlist_format(playlist, inputs) == "m2ts" and playlist not in self.selection.m2ts_confirmed:
                    saved = inputs.preferences
                    if self.selection.requires_m2ts_confirmation(playlist, saved):
                        self.hooks.dialogs.present_m2ts_confirmation(playlist)
                        return
                    self.selection.m2ts_confirmed.add(playlist)
        command = self.command()
        if command:
            self.start(command, output_snapshot=self.output_snapshot(command))

    def confirm_m2ts_response(self, playlist: str, generation: int, accepted: bool) -> None:
        inputs = self.hooks.get_inputs()
        if (
            generation != inputs.generation
            or self.lifecycle.closing
            or self.lifecycle.running
        ):
            return
        if accepted:
            self.selection.m2ts_confirmed.add(playlist)
            self.copy_selected()
        else:
            self.hooks.runtime.log("M2TS copy cancelled; filtered selection retained.")

    def inspect_streams(self) -> None:
        inputs = self.hooks.get_inputs()
        if self.selection.requires_reinspection:
            self.hooks.runtime.log("Inspect the current disc again before using its selections.")
            return
        self.hooks.ui.log_inspect_action()
        if self.lifecycle.running or inputs.detecting:
            self.hooks.runtime.log("Wait for the current operation before inspecting streams.")
            return
        source = inputs.source
        selected = self.selected_for_copy(inputs)
        if not source:
            self.hooks.runtime.log("Choose a source first.")
            return
        if len(selected) != 1:
            self.hooks.runtime.log("Select exactly one playlist to inspect its streams.")
            return
        playlist = selected[0]
        saved = inputs.preferences
        previous = self.selection.begin_stream_inspection(playlist, saved)
        if self.selection.stream_playlist == playlist:
            self.hooks.listing.update_stream_format(playlist)
        command = build_bluray_streams_command(
            inputs.script_path, source, playlist,
        )
        self.start(
            command,
            on_listing=lambda output: self.hooks.listing.load_stream_rows(playlist, output, previous),
            listing_parser=parse_bluray_streams,
        )

    def show_verify_dialog(self) -> None:
        inputs = self.hooks.get_inputs()
        if self.selection.requires_reinspection:
            self.hooks.runtime.log("Inspect the current disc again before using its selections.")
            return
        if self.lifecycle.running or inputs.detecting or self.lifecycle.closing:
            self.hooks.runtime.log("Wait for the current operation before verifying a copy.")
            return
        source = inputs.source
        if not source:
            self.hooks.runtime.log("Choose the original source before verifying a copy.")
            return
        is_bluray = inputs.is_bluray
        selected = self.selected_for_copy(inputs)
        title = selected[0] if is_bluray and len(selected) == 1 else "1" if not is_bluray else ""
        streams = (
            self.streams_for_copy(title, inputs)
            if is_bluray and title in self.selection.playlist_streams
            else [] if is_bluray else selected
        )
        self.hooks.dialogs.present_verification_dialog(
            source, is_bluray, title, streams, inputs.generation,
        )

    def verification_response(
        self,
        source: str,
        is_bluray: bool,
        generation: int,
        *,
        accepted: bool,
        copy_path: str,
        title: str,
        streams_text: str,
    ) -> bool:
        inputs = self.hooks.get_inputs()
        if not accepted:
            return True
        if (
            self.lifecycle.closing or self.lifecycle.running or inputs.detecting
            or generation != inputs.generation
            or is_bluray != inputs.is_bluray
            or self.selection.requires_reinspection
        ):
            self.hooks.runtime.log("Verification not started because the source or operation changed.")
        elif not copy_path:
            self.hooks.runtime.log("Choose an existing copy to verify.")
            return False
        else:
            values = [value.strip() for value in streams_text.split(",")]
            streams = [] if values == [""] else values
            verification = VerificationSpec(
                source, Path(copy_path), is_bluray, title.strip(), tuple(streams),
            )
            self.start(
                [inputs.script_path], verification=verification,
            )
        return True

    def start(
        self,
        command: list[str],
        on_success: Callable[[str], None] | None = None,
        output_snapshot: OutputSpec | None = None,
        *,
        preview: bool = False,
        preview_playlist: str | None = None,
        verification: VerificationSpec | None = None,
        listing_parser: Callable[[str], Listing] | None = None,
        on_listing: Callable[[Listing], None] | None = None,
    ) -> None:
        inputs = self.hooks.get_inputs()
        if self.lifecycle.closing:
            return
        if inputs.detecting:
            self.hooks.runtime.log("Detecting media type; wait a moment or choose DVD/Blu-ray manually.")
            return
        if self.lifecycle.running:
            self.hooks.runtime.log("An operation is already running.")
            return
        operation = self.lifecycle.begin()
        self.hooks.runtime.cancel_drive_scan()
        self.hooks.ui.invalidate_choosers()
        generation = inputs.generation
        source = inputs.source
        is_bluray = inputs.is_bluray
        self.hooks.ui.set_busy(True)
        self.hooks.ui.set_status(
            "Verifying copy..." if verification else "Preparing preview..." if preview else
            "Validating output..." if output_snapshot else "Inspecting..." if on_success or on_listing else "Copying..."
        )
        request = OperationRequest(
            command=tuple(command),
            script_path=inputs.script_path,
            source=source,
            is_bluray=is_bluray,
            collect=on_success is not None or on_listing is not None,
            output=output_snapshot,
            preview=preview,
            preview_playlist=preview_playlist,
            verification=verification,
            listing_parser=listing_parser,
            restored_source_settings=(
                self.selection.restored_source is not None
                and self.selection.restored_source.source == source
                and (
                    self.selection.restored_source.has_saved_settings
                    or "selection" in self.selection.restored_source.edited
                )
            ),
            known_device_source=self.hooks.runtime.is_known_device_source(source),
        )

        def dispatch(action: Callable[[], object]) -> None:
            self.hooks.runtime.dispatch_ui(action)

        hooks = OperationHooks(
            log=self.hooks.runtime.log,
            queue_log=self.hooks.runtime.queue_log,
            exclude_device=lambda path: dispatch(lambda: (
                self.hooks.runtime.exclude_device_source(path)
                if self.hooks.get_inputs().generation == generation else None
            )),
            confirm_non_device=lambda path: dispatch(lambda: (
                self.hooks.runtime.confirm_non_device(path)
                if self.hooks.get_inputs().generation == generation else None
            )),
            preview_started=lambda: dispatch(lambda: self.show_preview_status(operation)),
            copy_started=lambda: dispatch(lambda: self.show_copying_status(operation)),
            output_changed=lambda path: dispatch(lambda: self.update_output_path(operation, path)),
        )

        def worker() -> None:
            result = OperationResult("Failed")
            try:
                result = execute_operation(request, operation, hooks)
            finally:
                dispatch(lambda: self.finish_run(
                    on_success if result.deliver_success else None,
                    result.output,
                    generation,
                    source,
                    is_bluray,
                    result.status,
                    result.listing,
                    output_snapshot is not None,
                    on_listing=on_listing if result.deliver_success else None,
                ))

        if not self.hooks.runtime.start_worker(worker):
            self.finish_run(status="Failed")

    def show_copying_status(self, operation: ManagedProcess) -> None:
        if (
            self.lifecycle.operation is operation
            and not self.lifecycle.closing
            and not operation.cancelled.is_set()
        ):
            self.hooks.ui.set_status("Copying...")

    def show_preview_status(self, operation: ManagedProcess) -> None:
        if (
            self.lifecycle.operation is operation
            and not self.lifecycle.closing
            and not operation.cancelled.is_set()
        ):
            self.hooks.ui.set_status("Previewing...")

    def update_output_path(self, operation: ManagedProcess, path: str) -> None:
        if self.lifecycle.operation is operation and not self.lifecycle.closing:
            self.hooks.ui.set_output_path(path)
            self.hooks.runtime.log(f"Output format changed filename to: {path}")

    def finish_run(
        self,
        on_success: Callable[[str], None] | None = None,
        output: str = "",
        generation: int | None = None,
        source: str | None = None,
        is_bluray: bool | None = None,
        status: str = "Completed",
        listing: Listing | None = None,
        completed_copy: bool = False,
        *,
        on_listing: Callable[[Listing], None] | None = None,
    ) -> None:
        inputs = self.hooks.get_inputs()
        if self.lifecycle.operation is not None and self.lifecycle.operation.cancelled.is_set():
            if status == "Completed" and completed_copy:
                self.hooks.runtime.log("Cancellation arrived after the copy completed; published output was retained.")
            elif status in ("Completed", "Verified"):
                self.hooks.runtime.log("Cancellation received after subprocess completion; ignored pending results.")
                status = "Cancelled"
            on_success = None
            on_listing = None
        self.lifecycle.finish()
        self.hooks.ui.set_busy(False)
        self.hooks.ui.set_status(status)
        if self.lifecycle.closing:
            return
        if generation is not None and (
            generation != inputs.generation
            or source != inputs.source
            or is_bluray != inputs.is_bluray
        ):
            self.hooks.runtime.log("Ignored stale operation results because the source or media mode changed.")
            return
        if status == "Verified":
            self.hooks.runtime.log(output.rstrip())
        if on_listing is not None and listing is not None:
            on_listing(listing)
        if on_success is not None:
            on_success(output)
