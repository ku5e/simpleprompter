# SimplePrompter

A clean, keyboard-driven teleprompter with a built-in markdown editor. Part of the [Anchor](https://github.com/ku5e) project.

![Python](https://img.shields.io/badge/python-3.8+-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)

---

## What it does

- Full markdown text editor built in — write your script, then run it without switching apps
- Mirror mode activates automatically when you start the prompter, disables when you stop
- Foot switch support via a DIY Raspberry Pi Pico (hold to scroll, release to stop)
- Colored in-line cue markers for pause, beat, applause, reactions, and video rolls
- Adjustable scroll speed and font size without leaving the prompter

---

## Install

```bash
pip install pygame pyperclip
python teleprompter.py
```

Requires Python 3.8+. Works on Windows and macOS.

---

## Controls

### Edit mode
| Key | Action |
|---|---|
| Type | Edit script |
| Ctrl+O | Open .txt or .md file |
| Ctrl+V | Paste from clipboard |
| Ctrl+A | Select all |
| Ctrl+Alt+Enter | Start prompter |
| Ctrl+Q | Quit |
| + / - | Font size |
| Mouse wheel | Scroll |
| Click | Position cursor |

### Run mode (mirrored)
| Key | Action |
|---|---|
| Hold Page Down | Scroll forward |
| Hold Page Up | Scroll backward |
| Up / Down arrows | Speed adjust |
| Mouse wheel | Speed adjust |
| + / - | Font size |
| R | Reset to top |
| ESC | Return to edit mode |

---

## Markdown support

SimplePrompter renders standard markdown in both edit and run modes.

```
# Section Title
## Subsection

Regular script text goes here. Use **bold** for emphasis or *italic* for softer emphasis.

---
```

### Teleprompter cue markers

Type these anywhere in your script. They render in color so you can spot them at a glance.

| Marker | Color |
|---|---|
| `[pause]` | Red |
| `[beat]` | Blue |
| `[applause]` | Green |
| `[hold for reaction]` | Cyan |
| `[roll video]` | Magenta |

---

## DIY foot switch (Raspberry Pi Pico)

Wire two momentary buttons between GPIO pins and GND, then flash the CircuitPython script in `pico_footswitch/code.py`.

**Wiring:**
```
GP14 — [Forward button] — GND
GP15 — [Backward button] — GND
```

**Setup:**
1. Flash CircuitPython onto the Pico from [circuitpython.org](https://circuitpython.org)
2. Copy the `adafruit_hid` library folder from the [Adafruit bundle](https://circuitpython.org/libraries) into the Pico's `lib/` directory
3. Copy `pico_footswitch/code.py` to the Pico as `code.py`

The Pico shows up as a standard USB keyboard — no drivers, plug and go on Windows and macOS.

---

## Part of Anchor

SimplePrompter is the second tool in the [Anchor](https://github.com/ku5e) project — open source focus and productivity tools built around how people actually work.

The first tool is [Razor](https://github.com/ku5e/razor), a focused work session timer.

---

## License

MIT — free to use, modify, and distribute.

---

## Support

If SimplePrompter saved you money on a commercial teleprompter or helped you ship a video, consider [sponsoring on GitHub](https://github.com/sponsors/ku5e).
