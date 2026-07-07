"""Global push-to-talk: hold a modifier key to record, release to transcribe."""

from collections.abc import Callable

from pynput import keyboard

KEY_MAP = {
    "alt_r": keyboard.Key.alt_r,
    "alt_l": keyboard.Key.alt_l,
    "cmd_r": keyboard.Key.cmd_r,
    "ctrl_r": keyboard.Key.ctrl_r,
    "f13": keyboard.Key.f13,
}


class PushToTalk:
    def __init__(self, key_name: str, on_start: Callable[[], None], on_stop: Callable[[], None]):
        if key_name not in KEY_MAP:
            raise ValueError(f"Unsupported hotkey {key_name!r}; choose from {sorted(KEY_MAP)}")
        self.key = KEY_MAP[key_name]
        self.on_start = on_start
        self.on_stop = on_stop
        self._held = False
        self._listener: keyboard.Listener | None = None

    # callbacks are wrapped: an exception escaping into pynput kills the
    # listener thread silently, permanently deafening the hotkey
    def _on_press(self, key) -> None:
        try:
            if key == self.key and not self._held:
                self._held = True
                self.on_start()
        except Exception as e:
            print(f"hotkey press handler error: {e}")

    def _on_release(self, key) -> None:
        try:
            if key == self.key and self._held:
                self._held = False
                self.on_stop()
        except Exception as e:
            print(f"hotkey release handler error: {e}")

    @property
    def alive(self) -> bool:
        return self._listener is not None and self._listener.is_alive()

    def reset_held(self) -> None:
        """Clear stuck held-state after a missed release event (macOS
        occasionally drops the modifier flagsChanged event)."""
        self._held = False

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
