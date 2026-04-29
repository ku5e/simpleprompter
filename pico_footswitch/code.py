import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
import board
import digitalio
import time

# ── Keyboard HID ──────────────────────────────────────────────────────────────
kbd = Keyboard(usb_hid.devices)

# ── Buttons ───────────────────────────────────────────────────────────────────
# Wire each button between the GPIO pin and GND.
# Internal pull-up means pin reads LOW when button is pressed.
#
#   FORWARD  button → GP14 and GND
#   BACKWARD button → GP15 and GND

btn_forward  = digitalio.DigitalInOut(board.GP14)
btn_backward = digitalio.DigitalInOut(board.GP15)

for btn in (btn_forward, btn_backward):
    btn.direction = digitalio.Direction.INPUT
    btn.pull      = digitalio.Pull.UP

# ── State ─────────────────────────────────────────────────────────────────────
fwd_held = False
bwd_held = False

DEBOUNCE_S = 0.02   # 20 ms — fast enough to feel instant, slow enough to be clean

# ── Main loop ─────────────────────────────────────────────────────────────────
while True:
    fwd_pressed = not btn_forward.value    # LOW = pressed
    bwd_pressed = not btn_backward.value

    # Forward — Page Down
    if fwd_pressed and not fwd_held:
        kbd.press(Keycode.PAGE_DOWN)
        fwd_held = True
    elif not fwd_pressed and fwd_held:
        kbd.release(Keycode.PAGE_DOWN)
        fwd_held = False

    # Backward — Page Up
    if bwd_pressed and not bwd_held:
        kbd.press(Keycode.PAGE_UP)
        bwd_held = True
    elif not bwd_pressed and bwd_held:
        kbd.release(Keycode.PAGE_UP)
        bwd_held = False

    time.sleep(DEBOUNCE_S)
