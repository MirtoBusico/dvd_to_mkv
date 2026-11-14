"""Optional GTK pointer diagnostics for the DVD-to-MKV GUI."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk


class ClickDiagnostics:
    def __init__(
        self,
        window: Gtk.Window,
        inspect_button: Gtk.Button,
        state: Callable[[], str],
        log: Callable[[str], None],
    ) -> None:
        self.window = window
        self.inspect_button = inspect_button
        self.state = state
        self.log = log
        controller = Gtk.GestureClick()
        controller.set_button(0)
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("pressed", self.on_pointer_event, "button-press")
        controller.connect("released", self.on_pointer_event, "button-release")
        controller.connect("cancel", self.on_gesture_cancelled)
        controller.connect("stopped", self.on_gesture_stopped)
        window.add_controller(controller)

    def log_action(self, action: str) -> None:
        positioned, bounds = self.inspect_button.compute_bounds(self.window)
        geometry = (
            f"{bounds.get_x():.0f},{bounds.get_y():.0f},"
            f"{bounds.get_width():.0f},{bounds.get_height():.0f}"
            if positioned else "unavailable"
        )
        self.log(f"[click-debug] {action}; {self.state()}, inspect-bounds={geometry}")

    def on_gesture_cancelled(self, _controller: Gtk.Gesture, _sequence: object) -> None:
        self.log_action("pointer gesture cancelled")

    def on_gesture_stopped(self, _controller: Gtk.GestureClick) -> None:
        self.log_action("pointer click tracking stopped")

    def on_pointer_event(
        self,
        _controller: Gtk.GestureClick,
        _count: int,
        x: float,
        y: float,
        action: str,
    ) -> None:
        target = self.window.pick(x, y, Gtk.PickFlags.DEFAULT)
        inspect_target = target
        while inspect_target is not None and inspect_target is not self.inspect_button:
            inspect_target = inspect_target.get_parent()
        self.log_action(
            f"{action} x={x:.0f} y={y:.0f} "
            f"target={target.get_css_name() if target is not None else 'none'} "
            f"inspect-target={inspect_target is not None}"
        )
