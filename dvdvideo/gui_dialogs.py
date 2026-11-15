# @copyright: 2026 libertypo
# @license: GNU GPL-3

"""GTK dialogs for disc details and verification."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # type: ignore[reportMissingModuleSource]

from dvdvideo.gui_widgets import ResponseWindow, add_field_label, add_path_row


def create_disc_details(
    parent: Gtk.Window, source: str, text: str, on_close: Callable[[Gtk.Window], bool],
) -> Gtk.Window:
    dialog = Gtk.Window(title="Disc Details", transient_for=parent, destroy_with_parent=True)
    dialog.set_default_size(700, 560)
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    root.set_margin_top(12)
    root.set_margin_bottom(12)
    root.set_margin_start(12)
    root.set_margin_end(12)
    root.append(Gtk.Label(label=source, xalign=0, selectable=True, wrap=True))
    view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
    view.get_buffer().set_text(text)
    scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
    scroll.set_child(view)
    root.append(scroll)
    close = Gtk.Button(label="Close", halign=Gtk.Align.END)

    def close_clicked(_button: Gtk.Button) -> None:
        dialog.close()

    close.connect("clicked", close_clicked)
    root.append(close)
    dialog.set_child(root)
    dialog.connect("close-request", on_close)
    return dialog


class VerificationDialog(ResponseWindow):
    def __init__(
        self, parent: Gtk.Window, *, bluray: bool, title: str, streams: list[str],
        choose_copy: Callable[[Gtk.Entry], None],
    ) -> None:
        super().__init__(title="Verify Existing Copy", transient_for=parent)
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Verify", Gtk.ResponseType.OK, default=True)
        content = self.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.append(Gtk.Label(
            label="Compare an existing copy with the selected source. "
                  "This rereads the source and needs temporary disk space.",
            wrap=True, xalign=0,
        ))
        title_row = Gtk.Box(spacing=8)
        self.title_entry = Gtk.Entry(text=title, hexpand=True)
        self.title_entry.set_activates_default(True)
        add_field_label(title_row, "_Playlist" if bluray else "_DVD title", self.title_entry)
        title_row.append(self.title_entry)
        content.append(title_row)
        stream_row = Gtk.Box(spacing=8)
        self.stream_entry = Gtk.Entry(text=", ".join(streams), hexpand=True)
        self.stream_entry.set_activates_default(True)
        add_field_label(stream_row, "_Stream IDs", self.stream_entry)
        stream_row.append(self.stream_entry)
        content.append(stream_row)
        content.append(Gtk.Label(
            label="Enter the original stream indexes (DVD) or PIDs (Blu-ray) in copy order, "
                  "separated by commas. Leave empty for original M2TS.",
            wrap=True, xalign=0,
        ))
        self.copy_entry = add_path_row(content, "Copy", "Choose existing MKV or M2TS", lambda *_: (
            choose_copy(self.copy_entry)
        ))
        saved_streams = self.stream_entry.get_text()
        m2ts_selected = False

        def copy_changed(_entry: Gtk.Entry) -> None:
            nonlocal saved_streams, m2ts_selected
            is_m2ts = bluray and Path(self.copy_entry.get_text()).suffix.lower() == ".m2ts"
            if is_m2ts != m2ts_selected:
                if is_m2ts:
                    saved_streams = self.stream_entry.get_text()
                    self.stream_entry.set_text("")
                else:
                    self.stream_entry.set_text(saved_streams)
                self.stream_entry.set_sensitive(not is_m2ts)
                m2ts_selected = is_m2ts

        self.copy_entry.connect("changed", copy_changed)
