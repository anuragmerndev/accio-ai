"""Text insertion, Wispr-style: save clipboard, set text, synthesize Cmd+V, restore."""

import time

import Quartz
from AppKit import NSPasteboard, NSPasteboardTypeString

V_KEYCODE = 9  # kVK_ANSI_V


def _press_cmd_v() -> None:
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    down = Quartz.CGEventCreateKeyboardEvent(source, V_KEYCODE, True)
    up = Quartz.CGEventCreateKeyboardEvent(source, V_KEYCODE, False)
    Quartz.CGEventSetFlags(down, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventSetFlags(up, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)


def paste_text(text: str, restore_delay: float = 0.3) -> None:
    pb = NSPasteboard.generalPasteboard()
    previous = pb.stringForType_(NSPasteboardTypeString)
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
    time.sleep(0.05)  # let the pasteboard settle before the paste keystroke
    _press_cmd_v()
    time.sleep(restore_delay)  # target app must read the clipboard before restore
    if previous is not None:
        pb.clearContents()
        pb.setString_forType_(previous, NSPasteboardTypeString)


def copy_only(text: str) -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
