import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import random
import time
import sys
import site
import csv
import json
import wave
import tempfile
import pygame

# Optional dependencies: the app runs without them with reduced features.
try:
    import psutil  # CPU/memory debug readouts
except ImportError:
    psutil = None
try:
    from PIL import Image, ImageTk  # JPEG/BMP skins and smooth resizing
except ImportError:
    Image = ImageTk = None
try:
    from pydub import AudioSegment  # reverse playback for non-WAV formats
except ImportError:
    AudioSegment = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "grizzy_settings.json")
MAX_HISTORY = 3600  # cap in-memory history lists
MAX_LOG_LINES = 500  # cap event-log widget size

class SoundPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Grizzy")
        self.root.geometry("620x460")  # Fits within 640x480 with small border
        self.root.configure(bg='#333333')  # Softer dark gray background

        print(f"Starting script at {time.strftime('%H:%M:%S')}")
        print(f"Python executable: {sys.executable}")
        print(f"Site-packages path: {site.getsitepackages()}")

        # Set the window icon
        try:
            icon_path = os.path.join(BASE_DIR, "bear_icon.png")
            if Image:
                icon_photo = ImageTk.PhotoImage(Image.open(icon_path))
            else:
                icon_photo = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, icon_photo)
            print("Successfully set window icon")
        except Exception as e:
            print(f"Failed to set window icon: {e}")

        # Data for logging
        self.play_history = []  # (timestamp, file, cpu_usage)
        self.cpu_history = []   # (timestamp, cpu_usage)
        self.memory_history = []  # (timestamp, memory_usage)
        self.current_cpu_usage = 0

        # Set a smaller font for all widgets
        self.default_font = ("TkDefaultFont", 9)

        # Initialize pygame mixer for audio playback
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        self.sound_channel = pygame.mixer.Channel(0)  # Channel for main audio playback
        # Set default volumes to full (1.0)
        pygame.mixer.music.set_volume(1.0)
        self.sound_channel.set_volume(1.0)

        # Background image variables
        self.bg_image = None
        self.bg_photo = None
        self.bg_label = tk.Label(root, bg='#333333')
        self.bg_label.grid(row=0, column=0, rowspan=13, columnspan=6, sticky="nsew")  # Cover all rows

        # Debounce variable for resizing
        self.resize_timer = None
        self.last_resized_dimensions = (0, 0)  # Track last resized dimensions to avoid redundant updates

        # Configure grid weights for resizing
        for i in range(13):
            root.grid_rowconfigure(i, weight=1)
        for i in range(6):
            root.grid_columnconfigure(i, weight=1)

        # Folder path (row 0)
        self.folder_label = tk.Label(root, text="Folder path:", bg='#333333', fg='#E0E0E0', font=self.default_font)
        self.folder_label.grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.folder_entry = tk.Entry(root, width=38, bg='#444444', fg='#E0E0E0', insertbackground='#E0E0E0', font=self.default_font)
        self.folder_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=3)
        self.browse_button = tk.Button(root, text="Browse", command=self.browse_folder, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.browse_button.grid(row=0, column=3, padx=5, pady=3, sticky="ew")
        self.clear_button = tk.Button(root, text="Clear", command=self.clear_folder, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.clear_button.grid(row=0, column=4, padx=5, pady=3, sticky="ew")
        self.reset_button = tk.Button(root, text="Reset to Defaults", command=self.reset_to_defaults, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.reset_button.grid(row=0, column=5, padx=5, pady=3, sticky="ew")

        # Skin selector button and Scan Drive (row 1)
        self.skin_button = tk.Button(root, text="Select Skin", command=self.select_skin, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.skin_button.grid(row=1, column=0, columnspan=2, padx=5, pady=3, sticky="ew")
        self.scan_drive_button = tk.Button(root, text="Scan Drive", command=self.scan_drive, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.scan_drive_button.grid(row=1, column=5, padx=5, pady=3, sticky="ew")

        # Min delay (row 2)
        self.min_delay_label = tk.Label(root, text="Min delay (seconds):", bg='#333333', fg='#E0E0E0', font=self.default_font)
        self.min_delay_label.grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.min_delay_entry = tk.Entry(root, width=10, bg='#444444', fg='#E0E0E0', insertbackground='#E0E0E0', font=self.default_font)
        self.min_delay_entry.grid(row=2, column=1, sticky="w", padx=5, pady=3)
        self.min_delay_entry.insert(0, "1")

        # Max delay (row 3)
        self.max_delay_label = tk.Label(root, text="Max delay (seconds):", bg='#333333', fg='#E0E0E0', font=self.default_font)
        self.max_delay_label.grid(row=3, column=0, sticky="w", padx=5, pady=3)
        self.max_delay_entry = tk.Entry(root, width=10, bg='#444444', fg='#E0E0E0', insertbackground='#E0E0E0', font=self.default_font)
        self.max_delay_entry.grid(row=3, column=1, sticky="w", padx=5, pady=3)
        self.max_delay_entry.insert(0, "5")

        # Allow interrupt toggle (row 4, columns 0-1)
        self.allow_interrupt_var = tk.BooleanVar(value=True)
        self.allow_interrupt_check = tk.Checkbutton(root, text="Allow Interrupt", variable=self.allow_interrupt_var, bg='#333333', fg='#E0E0E0', selectcolor='#444444', font=self.default_font)
        self.allow_interrupt_check.grid(row=4, column=0, columnspan=2, sticky="w", padx=5, pady=3)

        # Reverse playback toggle (row 4, columns 2-3)
        self.reverse_playback_var = tk.BooleanVar(value=False)
        self.reverse_playback_check = tk.Checkbutton(root, text="Play in Reverse", variable=self.reverse_playback_var, bg='#333333', fg='#E0E0E0', selectcolor='#444444', font=self.default_font)
        self.reverse_playback_check.grid(row=4, column=2, columnspan=2, sticky="w", padx=5, pady=3)

        # MIDI selection (row 5)
        self.midi_button = tk.Button(root, text="Select MIDI", command=self.select_midi, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.midi_button.grid(row=5, column=0, columnspan=2, padx=5, pady=3, sticky="ew")
        self.stop_midi_button = tk.Button(root, text="Stop MIDI", command=self.stop_midi, state=tk.DISABLED, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.stop_midi_button.grid(row=5, column=2, padx=5, pady=3, sticky="ew")

        # Status and current sound (row 6)
        self.status_label = tk.Label(root, text="Status: Stopped", fg='#FF6347', bg='#333333', font=self.default_font)
        self.status_label.grid(row=6, column=0, columnspan=2, sticky="w", padx=5, pady=3)
        self.current_sound_label = tk.Label(root, text="Current sound: None", bg='#333333', fg='#E0E0E0', font=self.default_font)
        self.current_sound_label.grid(row=6, column=2, columnspan=3, sticky="w", padx=5, pady=3)

        # Buttons (row 7)
        self.start_button = tk.Button(root, text="Start", command=self.start_playing, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.start_button.grid(row=7, column=0, padx=5, pady=3, sticky="ew")
        self.pause_button = tk.Button(root, text="Pause", command=self.pause_playing, state=tk.DISABLED, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.pause_button.grid(row=7, column=1, padx=5, pady=3, sticky="ew")
        self.stop_button = tk.Button(root, text="Stop", command=self.stop_playing, state=tk.DISABLED, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.stop_button.grid(row=7, column=2, padx=5, pady=3, sticky="ew")
        self.instant_button = tk.Button(root, text="Instant", command=self.play_instant, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.instant_button.grid(row=7, column=3, padx=5, pady=3, sticky="ew")

        # Available audio files (rows 8-9)
        self.wav_label = tk.Label(root, text="Available Audio Files (0):", bg='#333333', fg='#E0E0E0', font=self.default_font)
        self.wav_label.grid(row=8, column=0, columnspan=5, sticky="w", padx=5, pady=3)
        self.wav_list = tk.Text(root, height=3, width=50, bg='#444444', fg='#E0E0E0', font=self.default_font)
        self.wav_list.grid(row=9, column=0, columnspan=5, padx=5, pady=3)
        self.wav_list.config(state=tk.NORMAL)
        self.wav_list.insert(tk.END, "No audio files loaded, try clicking Browse or Scan Drive.\n")
        self.wav_list.config(state=tk.DISABLED)

        # Event log (rows 10-11)
        self.log_label = tk.Label(root, text="Event Log:", bg='#333333', fg='#E0E0E0', font=self.default_font)
        self.log_label.grid(row=10, column=0, columnspan=5, sticky="w", padx=5, pady=3)
        self.log_text = tk.Text(root, height=3, width=50, bg='#444444', fg='#E0E0E0', font=self.default_font)
        self.log_text.grid(row=11, column=0, columnspan=5, padx=5, pady=3)
        self.log_text.config(state=tk.DISABLED)

        # Debug info and save button (row 12)
        self.debug_frame = tk.Frame(root, bg='#3A3A3A', bd=2, relief=tk.SUNKEN)
        self.debug_frame.grid(row=12, column=0, columnspan=5, padx=5, pady=3)
        self.time_since_label = tk.Label(self.debug_frame, text="Time since last sound: N/A", bg='#3A3A3A', fg='#E0E0E0', font=self.default_font)
        self.time_since_label.pack(pady=1)
        self.cpu_label = tk.Label(self.debug_frame, text="CPU usage: N/A", bg='#3A3A3A', fg='#E0E0E0', font=self.default_font)
        self.cpu_label.pack(pady=1)
        self.memory_label = tk.Label(self.debug_frame, text="Memory usage: N/A", bg='#3A3A3A', fg='#E0E0E0', font=self.default_font)
        self.memory_label.pack(pady=1)
        self.save_button = tk.Button(self.debug_frame, text="Save Logs", command=self.save_data, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font)
        self.save_button.pack(pady=3)

        # Playback variables
        self.wav_files = []  # Will include all supported audio formats
        self.last_play_time = None
        self.playing = False
        self.paused = False
        self.after_id_play = None
        self.after_id_update = None
        self.temp_file = None  # For reversed audio playback or format conversion
        self.scan_source = None  # To track the source of scanned files (folder or drive)
        self.midi_file = None  # To store the current MIDI file path

        # Bind resize event for background image with debouncing
        self.root.bind("<Configure>", self.resize_background)

        # Load saved settings
        self.load_settings()

        # Bind saving settings on setting changes
        self.folder_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.min_delay_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.max_delay_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.allow_interrupt_var.trace_add("write", lambda *args: self.save_settings())
        self.reverse_playback_var.trace_add("write", lambda *args: self.save_settings())

        # Bind saving settings on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Force initial background update after window is initialized
        self.root.after(100, self.update_background)

    def on_closing(self):
        self.save_settings()
        self.root.destroy()

    def load_settings(self):
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, settings.get("folder_path", ""))
            if settings.get("folder_path"):
                self.browse_folder(load_from_settings=True)
            self.min_delay_entry.delete(0, tk.END)
            self.min_delay_entry.insert(0, settings.get("min_delay", "1"))
            self.max_delay_entry.delete(0, tk.END)
            self.max_delay_entry.insert(0, settings.get("max_delay", "5"))
            self.allow_interrupt_var.set(settings.get("allow_interrupt", True))
            self.reverse_playback_var.set(settings.get("reverse_playback", False))
            print("Loaded settings from grizzy_settings.json")
        except FileNotFoundError:
            print("No settings file found, using defaults")
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        settings = {
            "folder_path": self.folder_entry.get(),
            "min_delay": self.min_delay_entry.get(),
            "max_delay": self.max_delay_entry.get(),
            "allow_interrupt": self.allow_interrupt_var.get(),
            "reverse_playback": self.reverse_playback_var.get(),
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=4)
            print("Saved settings to grizzy_settings.json")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def reset_to_defaults(self):
        if self.playing:
            self.stop_playing()
        self.folder_entry.delete(0, tk.END)
        self.wav_files = []
        self.scan_source = None
        self.update_wav_list()
        self.min_delay_entry.delete(0, tk.END)
        self.min_delay_entry.insert(0, "1")
        self.max_delay_entry.delete(0, tk.END)
        self.max_delay_entry.insert(0, "5")
        self.allow_interrupt_var.set(True)
        self.reverse_playback_var.set(False)
        self.save_settings()
        print("Settings reset to defaults")

    def select_midi(self):
        file_path = filedialog.askopenfilename(filetypes=[("MIDI files", "*.mid *.midi *.MID *.MIDI")])
        if file_path:
            try:
                if not file_path.lower().endswith(('.mid', '.midi')):
                    raise ValueError("Selected file is not a valid MIDI file (.mid or .midi).")
                self.midi_file = file_path
                pygame.mixer.music.stop()
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.set_volume(1.0)
                pygame.mixer.music.play(loops=-1)
                self.stop_midi_button.config(state=tk.NORMAL)
                print(f"Loaded MIDI file: {file_path}")
            except Exception as e:
                self.log_error(f"Failed to load MIDI file: {e}. Ensure the file is a valid MIDI file and a MIDI synthesizer is available on your system.")
                print(f"Error loading MIDI file: {e}")

    def stop_midi(self):
        pygame.mixer.music.stop()
        self.midi_file = None
        self.stop_midi_button.config(state=tk.DISABLED)
        print("Stopped MIDI playback")

    def play_sound(self, file_path):
        try:
            if self.reverse_playback_var.get():
                sound = self._load_reversed(file_path)
            else:
                # pygame loads WAV/OGG/MP3/FLAC natively - no conversion needed
                sound = pygame.mixer.Sound(file_path)
            if self.allow_interrupt_var.get():
                self.sound_channel.stop()
            self.sound_channel.set_volume(1.0)
            self.sound_channel.play(sound)
        except Exception as e:
            self.log_error(f"Failed to play sound: {e}")
            print(f"Error playing sound: {e}")

    def _load_reversed(self, file_path):
        temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd)
        try:
            if file_path.lower().endswith(".wav"):
                with wave.open(file_path, "rb") as w:
                    params = w.getparams()
                    frames = w.readframes(w.getnframes())
                frame_size = params.sampwidth * params.nchannels
                reversed_frames = b"".join(
                    frames[i:i + frame_size]
                    for i in range(len(frames) - frame_size, -1, -frame_size)
                )
                with wave.open(temp_path, "wb") as w:
                    w.setparams(params)
                    w.writeframes(reversed_frames)
            elif AudioSegment:
                AudioSegment.from_file(file_path).reverse().export(temp_path, format="wav")
            else:
                raise RuntimeError("Reversing non-WAV files requires pydub (pip install pydub audioop-lts)")
            return pygame.mixer.Sound(temp_path)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def scan_drive(self):
        self.browse_button.config(state=tk.DISABLED)
        self.clear_button.config(state=tk.DISABLED)
        self.scan_drive_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.instant_button.config(state=tk.DISABLED)

        drives = []
        if sys.platform == "win32":
            import string
            drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]

        if not drives:
            self.log_error("No drives found.")
            self._enable_buttons()
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Select Drive")
        dialog.geometry("200x100")
        dialog.configure(bg='#333333')

        tk.Label(dialog, text="Select a drive to scan:", bg='#333333', fg='#E0E0E0', font=self.default_font).pack(pady=5)
        drive_var = tk.StringVar(dialog)
        drive_var.set(drives[0] if drives else "")
        drive_menu = ttk.Combobox(dialog, textvariable=drive_var, values=drives, state="readonly", font=self.default_font)
        drive_menu.pack(pady=5)

        def on_select():
            selected_drive = drive_var.get()
            dialog.destroy()
            self._scan_drive(selected_drive)

        def on_cancel():
            dialog.destroy()
            self._enable_buttons()

        tk.Button(dialog, text="Scan", command=on_select, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font).pack(pady=5)
        tk.Button(dialog, text="Cancel", command=on_cancel, bg='#555555', fg='#FFD700', activebackground='#666666', font=self.default_font).pack(pady=5)
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        dialog.transient(self.root)
        dialog.grab_set()
        self.root.wait_window(dialog)

    def _scan_drive(self, drive):
        self.status_label.config(text="Status: Scanning...", fg="#FFA500")
        self.root.update()

        supported_formats = ('.wav', '.mp3', '.flac', '.ogg', '.aac', '.wma', '.aiff', '.m4a', '.opus', '.amr', '.ape')
        audio_files = []
        max_files = 10000

        try:
            for root_dir, _, files in os.walk(drive):
                for file in files:
                    if len(audio_files) >= max_files:
                        break
                    if file.lower().endswith(supported_formats):
                        audio_files.append(os.path.join(root_dir, file))
                if len(audio_files) >= max_files:
                    self.log_error(f"Reached file limit ({max_files}), stopped scanning.")
                    break
        except Exception as e:
            self.log_error(f"Error scanning drive {drive}: {e}")
            print(f"Error scanning drive: {e}")

        self.wav_files = audio_files
        self.scan_source = drive
        self.update_wav_list()
        self.status_label.config(text="Status: Stopped", fg="#FF6347")
        self._enable_buttons()

    def _enable_buttons(self):
        self.browse_button.config(state=tk.NORMAL)
        self.clear_button.config(state=tk.NORMAL)
        self.scan_drive_button.config(state=tk.NORMAL)
        self.start_button.config(state=tk.NORMAL)
        self.instant_button.config(state=tk.NORMAL)

    def select_skin(self):
        if not Image:
            self.log_error("Skins require Pillow (pip install pillow).")
            return
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif")])
        if file_path:
            try:
                print(f"Loading skin image: {file_path}")
                self.bg_image = Image.open(file_path)
                self.update_background()
            except Exception as e:
                self.log_error(f"Failed to load skin image: {e}")
                print(f"Error loading skin: {e}")

    def update_background(self):
        if self.bg_image:
            win_width = max(1, self.root.winfo_width())
            win_height = max(1, self.root.winfo_height())
            current_dimensions = (win_width, win_height)
            if current_dimensions != self.last_resized_dimensions:
                image = self.bg_image.resize((win_width, win_height), Image.Resampling.BILINEAR)
                self.bg_photo = ImageTk.PhotoImage(image)
                self.bg_label.configure(image=self.bg_photo)
                self.last_resized_dimensions = current_dimensions
                print(f"Background resized to {win_width}x{win_height}")

    def resize_background(self, event):
        if self.resize_timer:
            self.root.after_cancel(self.resize_timer)
        self.resize_timer = self.root.after(200, self.update_background)

    def browse_folder(self, load_from_settings=False):
        if not load_from_settings:
            folder = filedialog.askdirectory()
        else:
            folder = self.folder_entry.get()
        if folder:
            if not load_from_settings:
                self.folder_entry.delete(0, tk.END)
                self.folder_entry.insert(0, folder)
            supported_formats = ('.wav', '.mp3', '.flac', '.ogg', '.aac', '.wma', '.aiff', '.m4a', '.opus', '.amr', '.ape')
            self.wav_files = [
                os.path.join(root_dir, f)
                for root_dir, _, files in os.walk(folder)
                for f in files
                if f.lower().endswith(supported_formats)
            ]
            self.scan_source = folder
            self.update_wav_list()
            if not load_from_settings:
                self.save_settings()

    def clear_folder(self):
        if self.playing:
            self.stop_playing()
        self.folder_entry.delete(0, tk.END)
        self.wav_files = []
        self.scan_source = None
        self.update_wav_list()
        self.save_settings()

    def update_wav_list(self):
        self.wav_list.config(state=tk.NORMAL)
        self.wav_list.delete(1.0, tk.END)
        if self.wav_files:
            source = self.scan_source if self.scan_source else "Unknown Source"
            self.wav_label.config(text=f"Available Audio Files ({source}, {len(self.wav_files)} files):")
            for file in self.wav_files:
                self.wav_list.insert(tk.END, f"{os.path.basename(file)}\n")
        else:
            self.wav_label.config(text="Available Audio Files (0):")
            self.wav_list.insert(tk.END, "No audio files loaded, try clicking Browse or Scan Drive.\n")
        self.wav_list.config(state=tk.DISABLED)

    def start_playing(self):
        folder = self.folder_entry.get()
        try:
            min_delay = float(self.min_delay_entry.get())
            max_delay = float(self.max_delay_entry.get())
        except ValueError:
            self.log_error("Delays must be numbers.")
            return
        if min_delay < 0 or max_delay < 0:
            self.log_error("Delays must be non-negative.")
            return
        if min_delay > max_delay:
            self.log_error("Min delay cannot be greater than max delay.")
            return
        if not self.wav_files:
            self.log_error("No audio files loaded, try clicking Browse or Scan Drive.")
            return

        self.playing = True
        self.paused = False
        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL, text="Pause")
        self.stop_button.config(state=tk.NORMAL)
        self.instant_button.config(state=tk.NORMAL)
        self.status_label.config(text="Status: Playing", fg="#32CD32")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.play_history = []
        self.cpu_history = []
        self.memory_history = []
        self.last_play_time = None
        self.play_next()
        self.update_debug_info()

    def pause_playing(self):
        if not self.playing:
            return
        if self.paused:
            self.paused = False
            self.pause_button.config(text="Pause")
            self.status_label.config(text="Status: Playing", fg="#32CD32")
            self.sound_channel.unpause()
            self.play_next()
            self.update_debug_info()
        else:
            self.paused = True
            self.pause_button.config(text="Resume")
            self.status_label.config(text="Status: Paused", fg="#FFA500")
            if self.after_id_play:
                self.root.after_cancel(self.after_id_play)
                self.after_id_play = None
            if self.after_id_update:
                self.root.after_cancel(self.after_id_update)
                self.after_id_update = None
            self.sound_channel.pause()

    def stop_playing(self):
        self.playing = False
        self.paused = False
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="Pause")
        self.stop_button.config(state=tk.DISABLED)
        self.instant_button.config(state=tk.NORMAL)
        self.status_label.config(text="Status: Stopped", fg='#FF6347')
        if self.after_id_play:
            self.root.after_cancel(self.after_id_play)
            self.after_id_play = None
        if self.after_id_update:
            self.root.after_cancel(self.after_id_update)
            self.after_id_update = None
        self.sound_channel.stop()

    def play_instant(self):
        if not self.wav_files:
            self.log_error("No audio files loaded, try clicking Browse or Scan Drive.")
            return
        file = random.choice(self.wav_files)
        self.play_sound(file)
        current_time = time.strftime("%H:%M:%S")
        log_message = f"Instant play: {os.path.basename(file)} at {current_time}\n"
        self.play_history.append((time.time(), file, self.current_cpu_usage))
        del self.play_history[:-MAX_HISTORY]
        self.current_sound_label.config(text=f"Current sound: {os.path.basename(file)}")
        self._append_log(log_message)
        self.last_play_time = time.time()
        print(f"Instant play recorded: {file} at {current_time}, CPU usage: {self.current_cpu_usage}%")

    def play_next(self):
        if not self.playing or self.paused:
            return
        if not self.wav_files:
            self.stop_playing()
            self.log_error("No audio files loaded, playback stopped.")
            return
        file = random.choice(self.wav_files)
        self.play_sound(file)
        current_time = time.strftime("%H:%M:%S")
        log_message = f"Sound played: {os.path.basename(file)} at {current_time}\n"
        self.play_history.append((time.time(), file, self.current_cpu_usage))
        del self.play_history[:-MAX_HISTORY]
        self.current_sound_label.config(text=f"Current sound: {os.path.basename(file)}")
        self._append_log(log_message)
        self.last_play_time = time.time()
        try:
            min_delay = float(self.min_delay_entry.get())
            max_delay = float(self.max_delay_entry.get())
            if min_delay < 0 or max_delay < min_delay:
                raise ValueError
        except ValueError:
            min_delay, max_delay = 1.0, 5.0  # fall back while the user is mid-edit
        delay = random.uniform(min_delay, max_delay)
        self.after_id_play = self.root.after(int(delay * 1000), self.play_next)

    def update_debug_info(self):
        if not self.playing or self.paused:
            return
        if self.last_play_time is not None:
            time_since = time.time() - self.last_play_time
            self.time_since_label.config(text=f"Time since last sound: {time_since:.1f} seconds")
        else:
            self.time_since_label.config(text="Time since last sound: N/A")
        if psutil:
            cpu_usage = psutil.cpu_percent(interval=None)
            self.current_cpu_usage = cpu_usage
            memory_usage = psutil.virtual_memory().percent
            self.cpu_history.append((time.time(), cpu_usage))
            self.memory_history.append((time.time(), memory_usage))
            del self.cpu_history[:-MAX_HISTORY]
            del self.memory_history[:-MAX_HISTORY]
            self.cpu_label.config(text=f"CPU usage: {cpu_usage}%")
            self.memory_label.config(text=f"Memory usage: {memory_usage}%")
        else:
            self.cpu_label.config(text="CPU usage: N/A (psutil not installed)")
            self.memory_label.config(text="Memory usage: N/A (psutil not installed)")
        self.after_id_update = self.root.after(2000, self.update_debug_info)

    def _append_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message)
        line_count = int(self.log_text.index('end-1c').split('.')[0])
        if line_count > MAX_LOG_LINES:
            self.log_text.delete("1.0", f"{line_count - MAX_LOG_LINES + 1}.0")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def log_error(self, message):
        current_time = time.strftime("%H:%M:%S")
        log_message = f"Error: {message} at {current_time}\n"
        self._append_log(log_message)
        messagebox.showerror("Error", message)

    def save_data(self):
        if not self.play_history:
            messagebox.showinfo("Info", "No data to save.")
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = f"wav_player_logs_{timestamp}.csv"
        with open(log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Event", "CPU Usage (%)", "Memory Usage (%)"])
            play_dict = {t: f for t, f, _ in self.play_history}
            cpu_dict = {t: v for t, v in self.cpu_history}
            memory_dict = {t: v for t, v in self.memory_history}
            all_times = sorted(set(play_dict.keys()) | set(cpu_dict.keys()) | set(memory_dict.keys()))
            for t in all_times:
                event = play_dict.get(t, "")
                cpu = cpu_dict.get(t, "")
                memory = memory_dict.get(t, "")
                writer.writerow([time.strftime("%H:%M:%S", time.localtime(t)), event, cpu, memory])
        messagebox.showinfo("Success", f"Saved logs as {log_file}")

if __name__ == "__main__":
    print(f"Starting script at {time.strftime('%H:%M:%S')}")
    print(f"Python executable: {sys.executable}")
    print(f"Site-packages path: {site.getsitepackages()}")
    root = tk.Tk()
    app = SoundPlayerApp(root)
    root.mainloop()