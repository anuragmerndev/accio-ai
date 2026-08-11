"""Global push-to-talk: hold a modifier key to record, release to transcribe."""

from collections.abc import Callable

from pynput import keyboard

KEY_MAP = {
    "alt_r": keyboard.Key.alt_r,
    "alt_l": keyboard.Key.alt_l,
    "cmd_r": keyboard.Key.cmd_r,
    "ctrl_r": keyboard.Key.ctrl_r,
    "shift_r": keyboard.Key.shift_r,
    "shift_l": keyboard.Key.shift_l,
    "f13": keyboard.Key.f13,
}


class PushToTalk:
    def __init__(self, key_name: str, on_start: Callable[[], None], on_stop: Callable[[], None]):
        # comma-separated list → hold ANY of them (e.g. right option on the
        # laptop, right shift on an external keyboard)
        names = [n.strip() for n in key_name.split(",") if n.strip()]
        bad = [n for n in names if n not in KEY_MAP]
        if bad:
            raise ValueError(f"Unsupported hotkey {bad}; choose from {sorted(KEY_MAP)}")
        self.keys = {KEY_MAP[n] for n in names}
        self.on_start = on_start
        self.on_stop = on_stop
        self._held_key = None  # which key started the current hold
        self._listener: keyboard.Listener | None = None

    # callbacks are wrapped: an exception escaping into pynput kills the
    # listener thread silently, permanently deafening the hotkey
    def _on_press(self, key) -> None:
        try:
            if key in self.keys and self._held_key is None:
                self._held_key = key
                self.on_start()
        except Exception as e:
            print(f"hotkey press handler error: {e}")

    def _on_release(self, key) -> None:
        try:
            if key == self._held_key:
                self._held_key = None
                self.on_stop()
        except Exception as e:
            print(f"hotkey release handler error: {e}")

    @property
    def alive(self) -> bool:
        return self._listener is not None and self._listener.is_alive()

    def reset_held(self) -> None:
        """Clear stuck held-state after a missed release event (macOS
        occasionally drops the modifier flagsChanged event)."""
        self._held_key = None

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
