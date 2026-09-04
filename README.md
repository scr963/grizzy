# Grizzy 🐻

A little desktop app that plays random sounds from a folder (or a whole drive) at random intervals. Pick a folder of audio files, set a min/max delay, hit Start, and let it surprise you.

## Features

- Plays a random file from your library on a random delay between your min/max
- **Browse** a folder (subfolders included) or **Scan Drive** to find every audio file on a disk
- Instant-play button, pause/resume, reverse playback
- Optional looping MIDI background track
- Custom background skins (any image)
- Live CPU/memory debug readout and CSV log export
- Settings persist between runs

## Install

Requires Python 3.10+ with tkinter (included in the standard python.org installer).

```
pip install -r requirements.txt
python grizzy.py
```

Only `pygame-ce` is strictly required — the other entries in `requirements.txt` are optional:

| Package | What you lose without it |
|---|---|
| `psutil` | CPU/memory readouts in the debug panel |
| `pillow` | Background skins and icon scaling |
| `pydub` + `audioop-lts` | Reverse playback for non-WAV formats |

WAV, OGG, MP3, and FLAC play natively. Other formats (AAC, WMA, M4A, …) need ffmpeg on your PATH.

## Building a standalone .exe

```
pip install pyinstaller
pyinstaller --onefile --windowed --name Grizzy grizzy.py
```

The binary lands in `dist/Grizzy.exe` and runs without Python installed. Builds are per-platform: run the same command on macOS or Linux to get a native binary there.
