from __future__ import annotations

import json
import queue
import time
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import asdict
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable

from ast_bridge import (
    DEFAULT_RESOURCE_ID,
    LANGUAGE_OPTIONS,
    PERFORMANCE_PRESETS,
    SUBTITLE_MODES,
    ChannelSettings,
    Credentials,
    DeviceCatalog,
    TranslationChannel,
    get_preset,
    language_label,
)
from paths import get_app_root

ROOT = get_app_root()
CONFIG_PATH = ROOT / "config.local.json"
OUTPUT_DIR = ROOT / "output"

THEME = {
    "window": "#0B0E14",
    "header": "#121722",
    "panel": "#121722",
    "card": "#1A1D23",
    "card_alt": "#161A22",
    "card_soft": "#11161E",
    "input": "#10151D",
    "border": "#2A3140",
    "border_soft": "#222937",
    "text": "#E0E6ED",
    "muted": "#8A8D91",
    "muted_soft": "#4E5668",
    "blue": "#4A8CFF",
    "blue_soft": "#18263E",
    "green": "#41C98A",
    "green_soft": "#163126",
    "yellow": "#D7A855",
    "yellow_soft": "#362B1A",
    "red": "#D96B6B",
    "red_soft": "#3A2020",
    "white": "#FFFFFF",
    "shadow": "#000000",
}

SCENE_PRESETS: dict[str, dict] = {
    "discord_bidirectional": {
        "label": "Discord 双向同传",
        "description": "上行中文转英文，下行英文转中文，适合跨语种 Discord 语音频道与远程交流。",
        "outbound": {
            "source_language": "zh",
            "target_language": "en",
            "performance_profile": "turbo",
            "chunk_ms": 60,
            "jitter_buffer_ms": 70,
            "target_audio_rate": 16000,
            "input_gain": 1.05,
            "subtitle_mode": "bilingual",
        },
        "inbound": {
            "source_language": "en",
            "target_language": "zh",
            "performance_profile": "turbo",
            "chunk_ms": 60,
            "jitter_buffer_ms": 70,
            "target_audio_rate": 16000,
            "input_gain": 1.0,
            "subtitle_mode": "bilingual",
        },
    },
    "double_english": {
        "label": "双向都听英文",
        "description": "双方都说中文，但上下行都生成英文字幕和英文译音，适合跨境协作或演示。",
        "outbound": {
            "source_language": "zh",
            "target_language": "en",
            "performance_profile": "balanced",
            "chunk_ms": 80,
            "jitter_buffer_ms": 90,
            "target_audio_rate": 24000,
            "input_gain": 1.0,
            "subtitle_mode": "bilingual",
        },
        "inbound": {
            "source_language": "zh",
            "target_language": "en",
            "performance_profile": "balanced",
            "chunk_ms": 80,
            "jitter_buffer_ms": 90,
            "target_audio_rate": 24000,
            "input_gain": 1.0,
            "subtitle_mode": "bilingual",
        },
    },
    "caption_priority": {
        "label": "字幕优先低延迟",
        "description": "优先更快拿到原文与译文字幕，适合直播辅助、记录和会议纪要。",
        "outbound": {
            "source_language": "zh",
            "target_language": "en",
            "performance_profile": "turbo",
            "chunk_ms": 60,
            "jitter_buffer_ms": 60,
            "target_audio_rate": 16000,
            "input_gain": 1.1,
            "subtitle_mode": "bilingual",
        },
        "inbound": {
            "source_language": "en",
            "target_language": "zh",
            "performance_profile": "turbo",
            "chunk_ms": 60,
            "jitter_buffer_ms": 60,
            "target_audio_rate": 16000,
            "input_gain": 1.0,
            "subtitle_mode": "bilingual",
        },
    },
    "studio_demo": {
        "label": "演示保真模式",
        "description": "更保守的缓冲和 24kHz 输出，适合录制、演示与更稳定的听感。",
        "outbound": {
            "source_language": "zh",
            "target_language": "en",
            "performance_profile": "studio",
            "chunk_ms": 120,
            "jitter_buffer_ms": 160,
            "target_audio_rate": 24000,
            "input_gain": 1.0,
            "subtitle_mode": "bilingual",
        },
        "inbound": {
            "source_language": "en",
            "target_language": "zh",
            "performance_profile": "studio",
            "chunk_ms": 120,
            "jitter_buffer_ms": 160,
            "target_audio_rate": 24000,
            "input_gain": 1.0,
            "subtitle_mode": "bilingual",
        },
    },
}


def format_ts(timestamp: float | None) -> str:
    if not timestamp:
        return "--:--:--"
    return time.strftime("%H:%M:%S", time.localtime(timestamp))


def pick_font(families: set[str], choices: list[str], fallback: str) -> str:
    for family in choices:
        if family in families:
            return family
    return fallback


def ellipsize(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def strip_device_prefix(label: str) -> str:
    if "|" in label:
        return label.split("|", 1)[1].strip()
    return label.strip()


def build_device_display_maps(devices) -> tuple[dict[str, str], dict[str, str]]:
    labels_by_id: dict[str, str] = {}
    ids_by_label: dict[str, str] = {}
    seen: dict[str, int] = {}

    for item in devices:
        base = " ".join(item.name.split()).strip() or item.label
        if item.loopback:
            base = f"{base} · 回环"
        count = seen.get(base, 0) + 1
        seen[base] = count
        display = ellipsize(base, 32)
        label = display if count == 1 else ellipsize(f"{display} · {count}", 36)
        labels_by_id[item.device_id] = label
        ids_by_label[label] = item.device_id

    return labels_by_id, ids_by_label


def paint_dot(canvas: tk.Canvas, color: str) -> None:
    width = int(float(canvas.cget("width")))
    height = int(float(canvas.cget("height")))
    pad = 1
    canvas.delete("all")
    canvas.create_oval(pad, pad, width - pad, height - pad, fill=color, outline=color)


class Tooltip:
    def __init__(self, widget: tk.Widget, provider: Callable[[], str]):
        self.widget = widget
        self.provider = provider
        self.tipwindow: tk.Toplevel | None = None
        self.after_id: str | None = None

        self.widget.bind("<Enter>", self._schedule, add="+")
        self.widget.bind("<Leave>", self.hide, add="+")
        self.widget.bind("<ButtonPress>", self.hide, add="+")

    def _schedule(self, _event=None) -> None:
        self.hide()
        self.after_id = self.widget.after(350, self.show)

    def show(self) -> None:
        text = self.provider().strip()
        if not text or self.tipwindow is not None:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8

        self.tipwindow = tk.Toplevel(self.widget)
        self.tipwindow.wm_overrideredirect(True)
        self.tipwindow.attributes("-topmost", True)
        self.tipwindow.configure(bg=THEME["shadow"])
        self.tipwindow.geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tipwindow,
            text=text,
            bg="#0D1015",
            fg=THEME["text"],
            padx=10,
            pady=6,
            justify="left",
            font=(self.widget.master.option_get("Font", "*") or "Segoe UI", 9),
        )
        label.pack()

    def hide(self, _event=None) -> None:
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        if self.tipwindow is not None:
            self.tipwindow.destroy()
            self.tipwindow = None


class DevicePickerDialog:
    def __init__(self, parent: tk.Widget, title: str, values: list[str], current_value: str, fonts: dict[str, str]):
        self.values = values
        self.current_value = current_value
        self.fonts = fonts
        self.filtered_values = list(values)
        self.result: str | None = None

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent.winfo_toplevel())
        self.win.configure(bg=THEME["window"])
        self.win.geometry("760x560")
        self.win.minsize(680, 520)
        self.win.grab_set()

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self._refresh_list())

        shell = tk.Frame(self.win, bg=THEME["window"])
        shell.pack(fill="both", expand=True, padx=18, pady=18)

        card = tk.Frame(shell, bg=THEME["card"], highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(3, weight=1)

        tk.Label(card, text=title, fg=THEME["text"], bg=THEME["card"], font=(fonts["title"], 16)).grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 6)
        )
        tk.Label(
            card,
            text="搜索设备名称后回车或双击即可切换。输入与输出会分别应用到当前通道。",
            fg=THEME["muted"],
            bg=THEME["card"],
            font=(fonts["body"], 10),
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 12))

        ttk.Entry(card, textvariable=self.search_var, style="Dark.TEntry").grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12), ipady=6)

        list_wrap = tk.Frame(card, bg=THEME["card"])
        list_wrap.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 12))
        list_wrap.grid_columnconfigure(0, weight=1)
        list_wrap.grid_rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_wrap,
            activestyle="none",
            bg=THEME["input"],
            fg=THEME["text"],
            selectbackground=THEME["blue_soft"],
            selectforeground=THEME["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            font=(fonts["body"], 11),
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.listbox.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.bind("<Double-Button-1>", lambda _event: self._confirm())
        self.listbox.bind("<Return>", lambda _event: self._confirm())

        self.count_var = tk.StringVar(value="0 个设备")
        tk.Label(card, textvariable=self.count_var, fg=THEME["muted"], bg=THEME["card"], font=(fonts["body"], 10)).grid(
            row=4, column=0, sticky="w", padx=18, pady=(0, 12)
        )

        actions = tk.Frame(card, bg=THEME["card"])
        actions.grid(row=5, column=0, sticky="e", padx=18, pady=(0, 18))
        ttk.Button(actions, text="取消", style="Ghost.TButton", command=self._cancel).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="应用选择", style="Accent.TButton", command=self._confirm).pack(side="left")

        self._refresh_list()
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)

    def _refresh_list(self) -> None:
        query = self.search_var.get().strip().lower()
        if query:
            self.filtered_values = [item for item in self.values if query in item.lower()]
        else:
            self.filtered_values = list(self.values)

        self.listbox.delete(0, tk.END)
        for item in self.filtered_values:
            self.listbox.insert(tk.END, item)

        self.count_var.set(f"{len(self.filtered_values)} 个设备")
        if not self.filtered_values:
            return

        selected_index = 0
        if self.current_value in self.filtered_values:
            selected_index = self.filtered_values.index(self.current_value)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(selected_index)
        self.listbox.see(selected_index)

    def _confirm(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        self.result = self.filtered_values[selection[0]]
        self.win.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.win.destroy()

    def show(self) -> str | None:
        self.win.wait_window()
        return self.result


class TranscriptPane:
    def __init__(self, parent: tk.Widget, title: str, lane_text: str, accent: str, accent_soft: str, fonts: dict[str, str]):
        self.accent = accent
        self.fonts = fonts

        self.frame = tk.Frame(parent, bg=THEME["card"], highlightthickness=1, highlightbackground=THEME["border"])
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(2, weight=1)

        self.current_source_var = tk.StringVar(value="等待原文…")
        self.current_target_var = tk.StringVar(value="等待译文…")
        self.meta_var = tk.StringVar(value="首字 -- ms · 译文 -- ms · 译音 -- ms")

        header = tk.Frame(self.frame, bg=THEME["card"])
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)

        title_wrap = tk.Frame(header, bg=THEME["card"])
        title_wrap.grid(row=0, column=0, sticky="w")
        title_dot = tk.Canvas(title_wrap, width=10, height=10, bg=THEME["card"], highlightthickness=0)
        title_dot.pack(side="left", padx=(0, 8))
        paint_dot(title_dot, accent)
        tk.Label(title_wrap, text=title, fg=THEME["text"], bg=THEME["card"], font=(fonts["title"], 15)).pack(side="left")
        tk.Label(header, textvariable=self.meta_var, fg=THEME["muted"], bg=THEME["card"], font=(fonts["body"], 10)).grid(row=0, column=1, sticky="e")
        tk.Label(header, text=lane_text, fg=THEME["muted"], bg=THEME["card"], font=(fonts["body"], 10)).grid(row=1, column=0, sticky="w", pady=(6, 0))

        live = tk.Frame(self.frame, bg=THEME["card_soft"])
        live.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        live.grid_columnconfigure(0, weight=1)

        tk.Label(live, text="Source", fg=THEME["muted"], bg=THEME["card_soft"], font=(fonts["body"], 10)).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        self.source_label = tk.Label(
            live,
            textvariable=self.current_source_var,
            fg="#8A8D91",
            bg=THEME["card_soft"],
            justify="left",
            anchor="w",
            wraplength=540,
            font=(fonts["body"], 14),
        )
        self.source_label.grid(row=1, column=0, sticky="ew", padx=16)
        tk.Label(live, text="Translation", fg=accent, bg=THEME["card_soft"], font=(fonts["body"], 10)).grid(row=2, column=0, sticky="w", padx=16, pady=(12, 4))
        self.target_label = tk.Label(
            live,
            textvariable=self.current_target_var,
            fg=THEME["text"],
            bg=THEME["card_soft"],
            justify="left",
            anchor="w",
            wraplength=540,
            font=(fonts["title"], 18, "bold"),
        )
        self.target_label.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))

        history_wrap = tk.Frame(self.frame, bg=THEME["card"])
        history_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        history_wrap.grid_columnconfigure(0, weight=1)
        history_wrap.grid_rowconfigure(0, weight=1)

        self.history = ScrolledText(
            history_wrap,
            wrap="word",
            relief="flat",
            borderwidth=0,
            bg=THEME["input"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            font=(fonts["body"], 12),
            padx=18,
            pady=18,
        )
        self.history.grid(row=0, column=0, sticky="nsew")
        self.history.configure(state="disabled")
        self.history.tag_configure("stamp", foreground=THEME["muted_soft"], font=(fonts["body"], 10))
        self.history.tag_configure("source_text", foreground="#8A8D91", font=(fonts["body"], 14))
        self.history.tag_configure("target_text", foreground=THEME["text"], font=(fonts["title"], 18, "bold"))
        self.history.tag_configure("spacer", spacing1=2, spacing3=10)
        self.frame.bind("<Configure>", self._sync_wraplength)

    def _sync_wraplength(self, _event=None) -> None:
        wrap = max(self.frame.winfo_width() - 80, 320)
        self.source_label.configure(wraplength=wrap)
        self.target_label.configure(wraplength=wrap)

    def clear(self) -> None:
        self.current_source_var.set("等待原文…")
        self.current_target_var.set("等待译文…")
        self.meta_var.set("首字 -- ms · 译文 -- ms · 译音 -- ms")
        self.history.configure(state="normal")
        self.history.delete("1.0", tk.END)
        self.history.configure(state="disabled")

    def update_partial(self, source: str | None = None, target: str | None = None) -> None:
        if source:
            self.current_source_var.set(source)
        if target:
            self.current_target_var.set(target)

    def append_final(self, kind: str, text: str, timestamp: str) -> None:
        tag = "source_text" if kind == "source" else "target_text"
        prefix = "Source" if kind == "source" else "Translation"
        self.history.configure(state="normal")
        self.history.insert(tk.END, f"{prefix}  [{timestamp}]\n", ("stamp",))
        self.history.insert(tk.END, f"{text}\n\n", (tag, "spacer"))
        self.history.configure(state="disabled")
        self.history.after_idle(lambda: self.history.see(tk.END))

    def update_stats(self, stats: dict) -> None:
        self.meta_var.set(
            " · ".join(
                [
                    f"首字 {stats.get('first_source_latency_ms', '--')} ms",
                    f"译文 {stats.get('first_translation_latency_ms', '--')} ms",
                    f"译音 {stats.get('first_audio_latency_ms', '--')} ms",
                ]
            )
        )


class RouteDiagnosticsCard:
    def __init__(self, parent: tk.Widget, title: str, accent: str, fonts: dict[str, str]):
        self.accent = accent
        self.fonts = fonts
        self.state_var = tk.StringVar(value="Idle")
        self.route_var = tk.StringVar(value="Input → AST → Output")
        self.alert_active = False
        self.signal_kind = "idle"

        self.frame = tk.Frame(parent, bg=THEME["card"], highlightthickness=1, highlightbackground=THEME["border"])
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(2, weight=1)

        header = tk.Frame(self.frame, bg=THEME["card"])
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        header.grid_columnconfigure(0, weight=1)
        tk.Label(header, text=title, fg=THEME["text"], bg=THEME["card"], font=(fonts["title"], 14)).grid(row=0, column=0, sticky="w")
        self.state_badge = tk.Label(header, textvariable=self.state_var, fg=THEME["green"], bg=THEME["card_soft"], padx=10, pady=3, font=(fonts["body"], 9))
        self.state_badge.grid(row=0, column=1, sticky="e")
        tk.Label(header, text="Route & Diagnostics", fg=THEME["muted"], bg=THEME["card"], font=(fonts["body"], 10)).grid(row=1, column=0, sticky="w", pady=(6, 0))

        diag_strip = tk.Frame(self.frame, bg=THEME["card"])
        diag_strip.grid(row=1, column=0, sticky="ew", padx=16)
        self.diag_dots: dict[str, tk.Canvas] = {}
        for index, (key, label) in enumerate((("input", "Input"), ("engine", "AST"), ("output", "Output"), ("signal", "Signal"))):
            item = tk.Frame(diag_strip, bg=THEME["card"])
            item.grid(row=0, column=index, sticky="w", padx=(0, 12))
            dot = tk.Canvas(item, width=8, height=8, bg=THEME["card"], highlightthickness=0)
            dot.pack(side="left", padx=(0, 6))
            paint_dot(dot, THEME["muted_soft"])
            tk.Label(item, text=label, fg=THEME["muted"], bg=THEME["card"], font=(fonts["body"], 9)).pack(side="left")
            self.diag_dots[key] = dot

        route_box = tk.Frame(self.frame, bg=THEME["card_soft"])
        route_box.grid(row=2, column=0, sticky="nsew", padx=16, pady=(12, 16))
        route_box.grid_columnconfigure(0, weight=1)
        route_box.grid_rowconfigure(1, weight=1)
        tk.Label(route_box, text="Route Status", fg=THEME["text"], bg=THEME["card_soft"], font=(fonts["title"], 12)).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 10))
        self.route_canvas = tk.Canvas(route_box, bg=THEME["card_soft"], highlightthickness=0, height=110)
        self.route_canvas.grid(row=1, column=0, sticky="nsew", padx=12)
        self.route_canvas.bind("<Configure>", lambda _event: self._redraw())
        tk.Label(route_box, textvariable=self.route_var, fg=THEME["muted"], bg=THEME["card_soft"], font=(fonts["body"], 10)).grid(row=2, column=0, sticky="w", padx=16, pady=(8, 14))

        self.input_active = False
        self.engine_active = False
        self.output_active = False
        self._redraw()

    def _node_color(self, active: bool) -> str:
        return THEME["green"] if active else THEME["muted_soft"]

    def _signal_color(self) -> str:
        if self.signal_kind == "error":
            return THEME["red"]
        if self.signal_kind == "warning":
            return THEME["yellow"]
        if self.signal_kind == "ok":
            return THEME["green"]
        return THEME["muted_soft"]

    def _redraw(self) -> None:
        canvas = self.route_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 240)
        height = max(canvas.winfo_height(), 100)
        y = height * 0.55
        x1 = 48
        x2 = width / 2
        x3 = width - 48

        line_left = THEME["green"] if self.input_active and self.engine_active else THEME["border"]
        line_right = THEME["green"] if self.engine_active and self.output_active else THEME["border"]

        canvas.create_line(x1 + 18, y, x2 - 36, y, fill=line_left, width=2)
        canvas.create_line(x2 + 36, y, x3 - 18, y, fill=line_right, width=2)
        canvas.create_oval(x1 - 6, y - 6, x1 + 6, y + 6, fill=self._node_color(self.input_active), outline="")
        canvas.create_oval(x3 - 6, y - 6, x3 + 6, y + 6, fill=self._node_color(self.output_active), outline="")
        canvas.create_rectangle(x2 - 28, y - 18, x2 + 28, y + 18, fill="#21314F", outline="#355EAA")
        canvas.create_text(x1, y - 24, text="Input", fill=THEME["text"], font=(self.fonts["body"], 11))
        canvas.create_text(x2, y, text="AST", fill=THEME["text"], font=(self.fonts["title"], 11))
        canvas.create_text(x3, y - 24, text="Output", fill=THEME["text"], font=(self.fonts["body"], 11))

    def set_route(self, source_label: str, target_label: str) -> None:
        self.route_var.set(f"{source_label} → {target_label}")

    def set_state(self, *, input_active: bool, engine_active: bool, output_active: bool, signal_kind: str) -> None:
        self.input_active = input_active
        self.engine_active = engine_active
        self.output_active = output_active
        self.signal_kind = signal_kind

        paint_dot(self.diag_dots["input"], self._node_color(input_active))
        paint_dot(self.diag_dots["engine"], self._node_color(engine_active))
        paint_dot(self.diag_dots["output"], self._node_color(output_active))
        paint_dot(self.diag_dots["signal"], self._signal_color())

        if signal_kind == "error":
            self.state_var.set("Error")
            self.state_badge.configure(fg=THEME["red"])
        elif engine_active:
            self.state_var.set("Active")
            self.state_badge.configure(fg=THEME["green"])
        else:
            self.state_var.set("Idle")
            self.state_badge.configure(fg=THEME["muted"])
        self._redraw()

    def set_alert_pulse(self, active: bool, phase: bool) -> None:
        self.alert_active = active
        if active:
            border = THEME["red"] if phase else "#5A3030"
        else:
            border = THEME["border"]
        self.frame.configure(highlightbackground=border, highlightcolor=border)


class ChannelCard:
    def __init__(
        self,
        parent: tk.Widget,
        *,
        title: str,
        lane_text: str,
        accent: str,
        accent_soft: str,
        fonts: dict[str, str],
        on_pick_input: Callable[[], None],
        on_pick_output: Callable[[], None],
        on_config_change: Callable[[], None],
    ):
        self.accent = accent
        self.accent_soft = accent_soft
        self.fonts = fonts
        self.on_pick_input = on_pick_input
        self.on_pick_output = on_pick_output
        self.on_config_change = on_config_change
        self.is_running = False
        self.alert_active = False
        self.signal_kind = "idle"

        self.input_device_var = tk.StringVar()
        self.output_device_var = tk.StringVar()
        self.source_language_var = tk.StringVar(value="中文")
        self.target_language_var = tk.StringVar(value="英语")
        self.speaker_id_var = tk.StringVar()
        self.performance_profile_var = tk.StringVar(value="Turbo")
        self.chunk_ms_var = tk.IntVar(value=60)
        self.jitter_buffer_ms_var = tk.IntVar(value=70)
        self.target_audio_rate_var = tk.IntVar(value=16000)
        self.input_gain_var = tk.DoubleVar(value=1.0)
        self.subtitle_mode_var = tk.StringVar(value="双语滚动")
        self.status_var = tk.StringVar(value="待命")
        self.signal_var = tk.StringVar(value="待命")
        self.latency_var = tk.StringVar(value="原文 -- ms · 译文 -- ms · 译音 -- ms")
        self.detail_hint_var = tk.StringVar(value="等待设备与语种配置")
        self.live_source_var = tk.StringVar(value="等待输入语音…")
        self.live_target_var = tk.StringVar(value="译文会在这里优先显示…")
        self.input_display_var = tk.StringVar(value="未选择输入设备")
        self.output_display_var = tk.StringVar(value="未选择输出设备")
        self.input_route_var = tk.StringVar(value="未选输入")
        self.output_route_var = tk.StringVar(value="未选输出")
        self.engine_route_var = tk.StringVar(value="中文 → 英语")

        self._input_full = "未选择输入设备"
        self._output_full = "未选择输出设备"
        self._input_route_full = "未选输入"
        self._output_route_full = "未选输出"
        self._engine_route_full = "中文 → 英语"
        self._editable: list[tuple[tk.Widget, str]] = []
        self.route_panel: RouteDiagnosticsCard | None = None

        self.frame = tk.Frame(parent, bg=THEME["card"], highlightthickness=1, highlightbackground=THEME["border"])
        self.frame.grid_columnconfigure(0, weight=1)

        header = tk.Frame(self.frame, bg=THEME["card"])
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        header.grid_columnconfigure(0, weight=1)

        title_wrap = tk.Frame(header, bg=THEME["card"])
        title_wrap.grid(row=0, column=0, sticky="w")
        self.title_dot = tk.Canvas(title_wrap, width=10, height=10, bg=THEME["card"], highlightthickness=0)
        self.title_dot.pack(side="left", padx=(0, 8))
        paint_dot(self.title_dot, accent)
        tk.Label(title_wrap, text=title, fg=THEME["text"], bg=THEME["card"], font=(fonts["title"], 16)).pack(side="left")
        tk.Label(header, text=lane_text, fg=THEME["muted"], bg=THEME["card"], font=(fonts["body"], 10)).grid(row=1, column=0, sticky="w", pady=(6, 0))

        status_wrap = tk.Frame(header, bg=THEME["card"])
        status_wrap.grid(row=0, column=1, rowspan=2, sticky="e")
        self.signal_dot = tk.Canvas(status_wrap, width=10, height=10, bg=THEME["card"], highlightthickness=0)
        self.signal_dot.pack(side="left", padx=(0, 6))
        paint_dot(self.signal_dot, THEME["muted_soft"])
        self.signal_badge = tk.Label(status_wrap, textvariable=self.signal_var, fg=THEME["muted"], bg=THEME["card"], font=(fonts["body"], 10))
        self.signal_badge.pack(side="left", padx=(0, 12))
        self.meter = tk.Canvas(status_wrap, width=64, height=16, bg=THEME["card"], highlightthickness=0)
        self.meter.pack(side="left")
        self._draw_meter(0)

        self.detail_frame = tk.Frame(self.frame, bg=THEME["card"])
        self.detail_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.detail_frame.grid_columnconfigure(0, weight=1)
        self.detail_frame.grid_columnconfigure(1, weight=1)

        self.input_combo = self._device_field(self.detail_frame, "输入设备", self.input_device_var, 0, 0)
        self.output_combo = self._device_field(self.detail_frame, "输出设备", self.output_device_var, 0, 1)
        self.source_combo = self._combo_field(self.detail_frame, "源语言", self.source_language_var, 1, 0, [label for label, _ in LANGUAGE_OPTIONS])
        self.target_combo = self._combo_field(self.detail_frame, "目标语言", self.target_language_var, 1, 1, [label for label, _ in LANGUAGE_OPTIONS])
        self.profile_combo = self._combo_field(self.detail_frame, "性能档位", self.performance_profile_var, 2, 0, [preset.label for preset in PERFORMANCE_PRESETS.values()])
        self.subtitle_combo = self._combo_field(self.detail_frame, "字幕模式", self.subtitle_mode_var, 2, 1, [label for label, _ in SUBTITLE_MODES])

        advanced = tk.Frame(self.detail_frame, bg=THEME["card"])
        advanced.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        for col in range(4):
            advanced.grid_columnconfigure(col, weight=1)
        self.chunk_spin = self._mini_spin(advanced, "分包", self.chunk_ms_var, 0, 0, 40, 160, 10, "ms")
        self.buffer_spin = self._mini_spin(advanced, "缓冲", self.jitter_buffer_ms_var, 0, 1, 40, 320, 10, "ms")
        self.rate_combo = self._mini_combo(advanced, "采样率", self.target_audio_rate_var, 0, 2, [16000, 24000])
        self.gain_spin = self._mini_spin(advanced, "增益", self.input_gain_var, 0, 3, 0.5, 2.0, 0.05, "")

        speaker_wrap = tk.Frame(self.detail_frame, bg=THEME["card"])
        speaker_wrap.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        speaker_wrap.grid_columnconfigure(0, weight=1)
        tk.Label(speaker_wrap, text="音色 ID", fg=THEME["muted"], bg=THEME["card"], font=(fonts["body"], 9)).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.speaker_entry = ttk.Entry(speaker_wrap, textvariable=self.speaker_id_var, style="Dark.TEntry")
        self.speaker_entry.grid(row=1, column=0, sticky="ew", ipady=5)
        self._editable.append((self.speaker_entry, "normal"))

        preview = tk.Frame(self.detail_frame, bg=THEME["card_soft"])
        preview.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        preview.grid_columnconfigure(0, weight=1)
        tk.Label(preview, textvariable=self.detail_hint_var, fg=THEME["muted"], bg=THEME["card_soft"], font=(fonts["body"], 9)).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        tk.Label(preview, textvariable=self.live_source_var, fg="#8A8D91", bg=THEME["card_soft"], anchor="w", justify="left", wraplength=520, font=(fonts["body"], 11)).grid(row=1, column=0, sticky="ew", padx=12)
        tk.Label(preview, textvariable=self.live_target_var, fg=THEME["text"], bg=THEME["card_soft"], anchor="w", justify="left", wraplength=520, font=(fonts["title"], 14, "bold")).grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 10))

        footer = tk.Frame(self.frame, bg=THEME["card"])
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)
        tk.Label(footer, textvariable=self.latency_var, fg=THEME["muted"], bg=THEME["card"], font=(fonts["body"], 10)).grid(row=0, column=0, sticky="w")

        for var in (
            self.input_device_var,
            self.output_device_var,
            self.source_language_var,
            self.target_language_var,
            self.performance_profile_var,
            self.subtitle_mode_var,
        ):
            var.trace_add("write", self._handle_value_change)
        self._refresh_device_views()

    def attach_route_panel(self, panel: RouteDiagnosticsCard) -> None:
        self.route_panel = panel
        self._sync_route_panel()

    def _draw_meter(self, active_count: int) -> None:
        self.meter.delete("all")
        for index in range(10):
            x0 = 2 + index * 6
            y0 = 14 - min(index, 6)
            x1 = x0 + 3
            y1 = 15
            color = self.accent if index < active_count else THEME["border"]
            self.meter.create_rectangle(x0, y0, x1, y1, fill=color, outline=color)

    def _paint_dot(self, canvas: tk.Canvas, color: str) -> None:
        paint_dot(canvas, color)

    def _handle_value_change(self, *_args) -> None:
        self._refresh_device_views()
        if callable(self.on_config_change):
            self.on_config_change()

    def _device_field(self, parent: tk.Widget, label: str, value_var: tk.StringVar, row: int, column: int):
        wrap = tk.Frame(parent, bg=THEME["card"])
        wrap.grid(row=row, column=column, sticky="ew", padx=(0, 8) if column == 0 else (8, 0), pady=(0, 12))
        wrap.grid_columnconfigure(0, weight=1)
        tk.Label(wrap, text=label, fg=THEME["muted"], bg=THEME["card"], font=(self.fonts["body"], 10)).grid(row=0, column=0, sticky="w", pady=(0, 6))
        combo = ttk.Combobox(wrap, textvariable=value_var, state="readonly", style="Device.TCombobox", width=24)
        combo.grid(row=1, column=0, sticky="ew", ipady=6)
        combo.bind("<<ComboboxSelected>>", self._handle_value_change)
        combo.bind("<Button-1>", lambda _event, widget=combo: self._open_dropdown(widget), add="+")
        Tooltip(combo, lambda var=value_var: var.get())
        self._editable.append((combo, "readonly"))
        return combo

    def _open_dropdown(self, combo: ttk.Combobox) -> None:
        self.frame.after_idle(lambda: combo.event_generate("<Down>"))

    def _combo_field(self, parent: tk.Widget, label: str, variable, row: int, column: int, values: list[str]):
        wrap = tk.Frame(parent, bg=THEME["card"])
        wrap.grid(row=row, column=column, sticky="ew", padx=(0, 8) if column == 0 else (8, 0), pady=(0, 12))
        wrap.grid_columnconfigure(0, weight=1)
        tk.Label(wrap, text=label, fg=THEME["muted"], bg=THEME["card"], font=(self.fonts["body"], 10)).grid(row=0, column=0, sticky="w", pady=(0, 6))
        combo = ttk.Combobox(wrap, textvariable=variable, values=values, state="readonly", style="Dark.TCombobox")
        combo.grid(row=1, column=0, sticky="ew", ipady=6)
        self._editable.append((combo, "readonly"))
        return combo

    def _mini_combo(self, parent: tk.Widget, label: str, variable, row: int, column: int, values: list[int]):
        wrap = tk.Frame(parent, bg=THEME["card"])
        wrap.grid(row=row, column=column, sticky="ew", padx=(0, 6), pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        tk.Label(wrap, text=label, fg=THEME["muted"], bg=THEME["card"], font=(self.fonts["body"], 9)).grid(row=0, column=0, sticky="w", pady=(0, 5))
        combo = ttk.Combobox(wrap, textvariable=variable, values=values, state="readonly", style="Dark.TCombobox")
        combo.grid(row=1, column=0, sticky="ew", ipady=3)
        self._editable.append((combo, "readonly"))
        return combo

    def _mini_spin(self, parent: tk.Widget, label: str, variable, row: int, column: int, start, end, step, suffix: str):
        wrap = tk.Frame(parent, bg=THEME["card"])
        wrap.grid(row=row, column=column, sticky="ew", padx=(0, 6), pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        tk.Label(wrap, text=label, fg=THEME["muted"], bg=THEME["card"], font=(self.fonts["body"], 9)).grid(row=0, column=0, sticky="w", pady=(0, 5))
        line = tk.Frame(wrap, bg=THEME["card"])
        line.grid(row=1, column=0, sticky="ew")
        line.grid_columnconfigure(0, weight=1)
        spin = ttk.Spinbox(line, from_=start, to=end, increment=step, textvariable=variable, style="Dark.TSpinbox")
        spin.grid(row=0, column=0, sticky="ew", ipady=3)
        if suffix:
            tk.Label(line, text=suffix, fg=THEME["muted"], bg=THEME["card"], font=(self.fonts["body"], 9)).grid(row=0, column=1, sticky="w", padx=(6, 0))
        self._editable.append((spin, "normal"))
        return spin

    def _sync_route_panel(self) -> None:
        if self.route_panel is None:
            return
        self.route_panel.set_route(self.source_language_var.get().strip() or "Source", self.target_language_var.get().strip() or "Target")

    def _refresh_device_views(self) -> None:
        input_full = self.input_device_var.get().strip() or "未选择输入设备"
        output_full = self.output_device_var.get().strip() or "未选择输出设备"
        source = self.source_language_var.get().strip() or "未设定"
        target = self.target_language_var.get().strip() or "未设定"

        self._input_full = input_full
        self._output_full = output_full
        self._input_route_full = strip_device_prefix(input_full)
        self._output_route_full = strip_device_prefix(output_full)
        self._engine_route_full = f"{source} → {target}"

        self.input_display_var.set(ellipsize(self._input_full, 28))
        self.output_display_var.set(ellipsize(self._output_full, 28))
        self.input_route_var.set(ellipsize(self._input_route_full, 18))
        self.output_route_var.set(ellipsize(self._output_route_full, 18))
        self.engine_route_var.set(ellipsize(self._engine_route_full, 18))
        self._sync_route_panel()

    def set_controls_enabled(self, enabled: bool) -> None:
        for widget, normal_state in self._editable:
            widget.configure(state=normal_state if enabled else "disabled")

    def set_running_mode(self, running: bool) -> None:
        self.is_running = running
        self.set_controls_enabled(not running)
        self._draw_meter(6 if running else 0)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.detail_hint_var.set(text)

    def update_preview(self, *, source: str | None = None, target: str | None = None) -> None:
        if source:
            self.live_source_var.set(source)
        if target:
            self.live_target_var.set(target)

    def update_stats(self, stats: dict) -> None:
        self.latency_var.set(
            " · ".join(
                [
                    f"原文 {stats.get('first_source_latency_ms', '--')} ms",
                    f"译文 {stats.get('first_translation_latency_ms', '--')} ms",
                    f"译音 {stats.get('first_audio_latency_ms', '--')} ms",
                ]
            )
        )
        self.detail_hint_var.set(f"chunks {stats.get('sent_chunks', 0)}   tts {stats.get('tts_chunks', 0)}   logid {stats.get('log_id') or '--'}")
        if stats.get("last_source_text"):
            self.live_source_var.set(stats["last_source_text"])
        if stats.get("last_target_text"):
            self.live_target_var.set(stats["last_target_text"])

    def set_signal_state(self, kind: str, message: str) -> None:
        self.signal_kind = kind
        palette = {
            "idle": THEME["muted_soft"],
            "ok": THEME["green"],
            "warning": THEME["yellow"],
            "error": THEME["red"],
        }
        color = palette.get(kind, THEME["muted_soft"])
        self._paint_dot(self.signal_dot, color)
        self.signal_badge.configure(fg=THEME["text"] if kind in {"ok", "error"} else THEME["muted"], bg=THEME["card"])
        self.signal_var.set(message)
        self._draw_meter(8 if kind == "ok" else 4 if kind == "warning" else 1 if kind == "error" else 0)

    def set_alert_pulse(self, active: bool, phase: bool) -> None:
        self.alert_active = active
        if active:
            border = THEME["red"] if phase else "#6A2323"
        else:
            border = THEME["border"]
        self.frame.configure(highlightbackground=border, highlightcolor=border)

    def apply_profile(self, profile_key: str) -> None:
        preset = get_preset(profile_key)
        self.performance_profile_var.set(preset.label)
        self.chunk_ms_var.set(preset.chunk_ms)
        self.jitter_buffer_ms_var.set(preset.jitter_buffer_ms)
        self.target_audio_rate_var.set(preset.target_audio_rate)
        self.input_gain_var.set(preset.input_gain)

    def profile_key(self) -> str:
        for key, preset in PERFORMANCE_PRESETS.items():
            if preset.label == self.performance_profile_var.get():
                return key
        return "balanced"

    def subtitle_mode_key(self) -> str:
        for label, code in SUBTITLE_MODES:
            if label == self.subtitle_mode_var.get():
                return code
        return "bilingual"

    def serialize_ui(self, input_ids_by_label: dict[str, str], output_ids_by_label: dict[str, str]) -> dict:
        return {
            "capture_device_id": input_ids_by_label.get(self.input_device_var.get().strip(), ""),
            "playback_device_id": output_ids_by_label.get(self.output_device_var.get().strip(), ""),
            "source_language": self._language_code(self.source_language_var.get().strip()),
            "target_language": self._language_code(self.target_language_var.get().strip()),
            "speaker_id": self.speaker_id_var.get().strip(),
            "performance_profile": self.profile_key(),
            "chunk_ms": int(self.chunk_ms_var.get()),
            "jitter_buffer_ms": int(self.jitter_buffer_ms_var.get()),
            "target_audio_rate": int(self.target_audio_rate_var.get()),
            "input_gain": float(self.input_gain_var.get()),
            "subtitle_mode": self.subtitle_mode_key(),
        }

    def apply_config(self, config: dict, input_labels_by_id: dict[str, str], output_labels_by_id: dict[str, str]) -> None:
        if config.get("capture_device_id"):
            self.input_device_var.set(input_labels_by_id.get(config["capture_device_id"], self.input_device_var.get()))
        if config.get("playback_device_id"):
            self.output_device_var.set(output_labels_by_id.get(config["playback_device_id"], self.output_device_var.get()))
        if config.get("source_language"):
            self.source_language_var.set(language_label(config["source_language"]))
        if config.get("target_language"):
            self.target_language_var.set(language_label(config["target_language"]))
        self.speaker_id_var.set(config.get("speaker_id", ""))
        if config.get("performance_profile"):
            self.apply_profile(config["performance_profile"])
        if config.get("chunk_ms"):
            self.chunk_ms_var.set(config["chunk_ms"])
        if config.get("jitter_buffer_ms"):
            self.jitter_buffer_ms_var.set(config["jitter_buffer_ms"])
        if config.get("target_audio_rate"):
            self.target_audio_rate_var.set(config["target_audio_rate"])
        if config.get("input_gain") is not None:
            self.input_gain_var.set(config["input_gain"])
        if config.get("subtitle_mode"):
            for label, code in SUBTITLE_MODES:
                if code == config["subtitle_mode"]:
                    self.subtitle_mode_var.set(label)
                    break
        self._refresh_device_views()

    def to_settings(self, channel_id: str, display_name: str, input_ids_by_label: dict[str, str], output_ids_by_label: dict[str, str]) -> ChannelSettings:
        return ChannelSettings(
            channel_id=channel_id,
            display_name=display_name,
            capture_device_id=input_ids_by_label[self.input_device_var.get().strip()],
            playback_device_id=output_ids_by_label[self.output_device_var.get().strip()],
            source_language=self._language_code(self.source_language_var.get().strip()),
            target_language=self._language_code(self.target_language_var.get().strip()),
            speaker_id=self.speaker_id_var.get().strip(),
            performance_profile=self.profile_key(),
            chunk_ms=int(self.chunk_ms_var.get()),
            jitter_buffer_ms=int(self.jitter_buffer_ms_var.get()),
            target_audio_rate=int(self.target_audio_rate_var.get()),
            input_gain=float(self.input_gain_var.get()),
            subtitle_mode=self.subtitle_mode_key(),
            max_queue_chunks=get_preset(self.profile_key()).max_queue_chunks,
        )

    @staticmethod
    def _language_code(label: str) -> str:
        for option_label, code in LANGUAGE_OPTIONS:
            if option_label == label:
                return code
        return label


class NovaInterpApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("NOVA INTERP")

        width = max(root.winfo_screenwidth() - 120, 1280)
        height = max(root.winfo_screenheight() - 140, 860)
        self.root.geometry(f"{width}x{height}+40+20")
        self.root.minsize(1320, 860)
        self.root.configure(bg=THEME["window"])

        self.fonts = self._configure_fonts()
        self._configure_styles()

        self.catalog = DeviceCatalog()
        self.event_queue: queue.Queue[dict] = queue.Queue()
        self.channels: dict[str, TranslationChannel] = {}
        self.stats_by_channel: dict[str, dict] = {"outbound": {}, "inbound": {}}
        self.transcripts: dict[str, list[dict]] = {"outbound": [], "inbound": []}
        self.channel_settings_cache: dict[str, dict] = {}
        self.runtime_log_lines: list[str] = []
        self.channel_alerts: dict[str, bool] = {"outbound": False, "inbound": False}
        self.alert_phase = False
        self.controls_locked = False
        self.suspend_config_events = True

        self.input_labels_by_id: dict[str, str] = {}
        self.output_labels_by_id: dict[str, str] = {}
        self.input_ids_by_label: dict[str, str] = {}
        self.output_ids_by_label: dict[str, str] = {}

        self.app_key_var = tk.StringVar()
        self.access_key_var = tk.StringVar()
        self.secret_key_var = tk.StringVar()
        self.resource_id_var = tk.StringVar(value=DEFAULT_RESOURCE_ID)
        self.scene_var = tk.StringVar(value=SCENE_PRESETS["discord_bidirectional"]["label"])
        self.global_status_var = tk.StringVar(value="待命")
        self.global_hint_var = tk.StringVar(value="准备就绪，配置设备后即可开始双向同传。")
        self.drawer_open = False
        self.settings_open = False
        self.transcript_open = False

        self.outbound_card: ChannelCard | None = None
        self.inbound_card: ChannelCard | None = None
        self.outbound_transcript: TranscriptPane | None = None
        self.inbound_transcript: TranscriptPane | None = None

        self._build_layout()
        self.refresh_devices()
        if not self._load_config():
            self._apply_scene_by_label(self.scene_var.get(), preserve_devices=True)
        self.suspend_config_events = False
        self._set_controls_locked(False)
        self.outbound_card.set_signal_state("idle", "待命")
        self.inbound_card.set_signal_state("idle", "待命")
        self._refresh_global_state()

        self.root.after(80, self._maximize_window)
        self.root.after(120, self._set_initial_split)
        self.root.after(120, self._drain_events)
        self.root.after(350, self._pulse_alerts)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Escape>", self._handle_escape)
        self.root.bind("<Control-comma>", lambda _event: self.toggle_drawer())
        self.root.bind("<Control-t>", lambda _event: self.toggle_transcript_dock())
        self.root.bind("<Control-Return>", lambda _event: self._quick_toggle_channels())

    def _configure_fonts(self) -> dict[str, str]:
        families = set(tkfont.families(self.root))
        display = pick_font(families, ["Segoe UI Semibold", "Bahnschrift SemiBold", "Segoe UI"], "Segoe UI")
        title = pick_font(families, ["Microsoft YaHei UI", "Microsoft YaHei UI Light", "Segoe UI"], "Segoe UI")
        body = pick_font(families, ["Microsoft YaHei UI", "Microsoft YaHei UI Light", "Segoe UI"], "Segoe UI")
        mono = pick_font(families, ["Consolas", "Courier New"], "Courier New")

        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family=body, size=10)
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family=body, size=10)
        fixed_font = tkfont.nametofont("TkFixedFont")
        fixed_font.configure(family=mono, size=10)
        self.root.option_add("*Font", default_font)

        return {"display": display, "title": title, "body": body, "mono": mono}

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(
            "Ghost.TButton",
            background=THEME["card_alt"],
            foreground=THEME["text"],
            bordercolor=THEME["border"],
            lightcolor=THEME["border"],
            darkcolor=THEME["border"],
            relief="flat",
            padding=(10, 6),
            font=(self.fonts["body"], 10),
        )
        style.map("Ghost.TButton", background=[("active", "#232935"), ("disabled", THEME["card_soft"])], foreground=[("disabled", THEME["muted"])])

        style.configure(
            "Accent.TButton",
            background=THEME["blue"],
            foreground=THEME["white"],
            bordercolor=THEME["blue"],
            lightcolor=THEME["blue"],
            darkcolor=THEME["blue"],
            relief="flat",
            padding=(12, 7),
            font=(self.fonts["body"], 10),
        )
        style.map("Accent.TButton", background=[("active", "#6AA1FF"), ("disabled", "#304266")], foreground=[("disabled", "#BFD0ED")])

        style.configure(
            "Danger.TButton",
            background="#5A2B33",
            foreground=THEME["white"],
            bordercolor="#6C333D",
            lightcolor="#6C333D",
            darkcolor="#6C333D",
            relief="flat",
            padding=(12, 7),
            font=(self.fonts["body"], 10),
        )
        style.map("Danger.TButton", background=[("active", "#74414A"), ("disabled", "#3C2A2E")], foreground=[("disabled", "#C7B2B7")])

        style.configure(
            "Dark.TEntry",
            fieldbackground=THEME["input"],
            foreground=THEME["text"],
            bordercolor=THEME["border"],
            lightcolor=THEME["border"],
            darkcolor=THEME["border"],
            insertcolor=THEME["text"],
            padding=8,
        )

        style.configure(
            "Dark.TCombobox",
            fieldbackground=THEME["input"],
            background=THEME["input"],
            foreground=THEME["text"],
            bordercolor=THEME["border"],
            lightcolor=THEME["border"],
            darkcolor=THEME["border"],
            arrowcolor=THEME["muted"],
            padding=7,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", THEME["input"]), ("disabled", THEME["card_soft"])],
            background=[("readonly", THEME["input"]), ("disabled", THEME["card_soft"])],
            foreground=[("readonly", THEME["text"]), ("disabled", THEME["muted"])],
        )

        style.configure(
            "Device.TCombobox",
            fieldbackground=THEME["input"],
            background=THEME["input"],
            foreground=THEME["text"],
            bordercolor=THEME["border"],
            lightcolor=THEME["border"],
            darkcolor=THEME["border"],
            arrowcolor=THEME["muted"],
            padding=7,
            relief="flat",
        )
        style.map(
            "Device.TCombobox",
            fieldbackground=[("readonly", THEME["input"]), ("disabled", THEME["card_soft"])],
            background=[("readonly", THEME["input"]), ("disabled", THEME["card_soft"])],
            foreground=[("readonly", THEME["text"]), ("disabled", THEME["muted"])],
        )

        style.configure(
            "Dark.TSpinbox",
            fieldbackground=THEME["input"],
            foreground=THEME["text"],
            bordercolor=THEME["border"],
            lightcolor=THEME["border"],
            darkcolor=THEME["border"],
            arrowsize=12,
            padding=6,
        )

        style.configure("Blue.Horizontal.TProgressbar", troughcolor=THEME["card_soft"], bordercolor=THEME["card_soft"], background=THEME["blue"], lightcolor=THEME["blue"], darkcolor=THEME["blue"])
        style.configure("Green.Horizontal.TProgressbar", troughcolor=THEME["card_soft"], bordercolor=THEME["card_soft"], background=THEME["green"], lightcolor=THEME["green"], darkcolor=THEME["green"])

    def _build_layout(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self.header_bar = tk.Frame(self.root, bg=THEME["header"], highlightthickness=1, highlightbackground=THEME["border_soft"])
        self.header_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        self.header_bar.grid_columnconfigure(0, weight=1)

        self.content = tk.Frame(self.root, bg=THEME["window"])
        self.content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=2)
        self.content.grid_rowconfigure(1, weight=3)

        self._build_header()

        self.controls_section = tk.Frame(self.content, bg=THEME["window"])
        self.controls_section.grid(row=0, column=0, sticky="nsew")
        self.controls_section.grid_columnconfigure(0, weight=4)
        self.controls_section.grid_columnconfigure(1, weight=3)
        self.controls_section.grid_columnconfigure(2, weight=4)
        self.controls_section.grid_columnconfigure(3, weight=3)
        self.controls_section.grid_rowconfigure(0, weight=1)

        self.outbound_card = ChannelCard(
            self.controls_section,
            title="Channel A",
            lane_text="我说 → 对方听",
            accent=THEME["blue"],
            accent_soft=THEME["blue_soft"],
            fonts=self.fonts,
            on_pick_input=lambda: self._pick_device("outbound", "input"),
            on_pick_output=lambda: self._pick_device("outbound", "output"),
            on_config_change=self._on_config_changed,
        )
        self.outbound_card.frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.outbound_route_panel = RouteDiagnosticsCard(self.controls_section, "线路状态", THEME["blue"], self.fonts)
        self.outbound_route_panel.frame.grid(row=0, column=1, sticky="nsew", padx=(8, 8))
        self.outbound_card.attach_route_panel(self.outbound_route_panel)

        self.inbound_card = ChannelCard(
            self.controls_section,
            title="Channel B",
            lane_text="对方说 → 我听",
            accent=THEME["green"],
            accent_soft=THEME["green_soft"],
            fonts=self.fonts,
            on_pick_input=lambda: self._pick_device("inbound", "input"),
            on_pick_output=lambda: self._pick_device("inbound", "output"),
            on_config_change=self._on_config_changed,
        )
        self.inbound_card.frame.grid(row=0, column=2, sticky="nsew", padx=(8, 8))

        self.inbound_route_panel = RouteDiagnosticsCard(self.controls_section, "线路状态", THEME["green"], self.fonts)
        self.inbound_route_panel.frame.grid(row=0, column=3, sticky="nsew", padx=(8, 0))
        self.inbound_card.attach_route_panel(self.inbound_route_panel)

        self.transcript_section = tk.Frame(self.content, bg=THEME["window"])
        self.transcript_section.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        self.transcript_section.grid_columnconfigure(0, weight=1)
        self.transcript_section.grid_rowconfigure(1, weight=1)

        transcript_shell = tk.Frame(self.transcript_section, bg=THEME["card"], highlightthickness=1, highlightbackground=THEME["border"])
        transcript_shell.grid(row=0, column=0, sticky="nsew")
        transcript_shell.grid_columnconfigure(0, weight=1)
        transcript_shell.grid_rowconfigure(1, weight=1)

        transcript_head = tk.Frame(transcript_shell, bg=THEME["card"])
        transcript_head.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 12))
        transcript_head.grid_columnconfigure(0, weight=1)
        tk.Label(transcript_head, text="双向实时翻译", fg=THEME["text"], bg=THEME["card"], font=(self.fonts["title"], 16)).grid(row=0, column=0, sticky="w")
        tk.Label(
            transcript_head,
            text="Source 使用 #8A8D91，Translation 使用 #E0E6ED，高亮加粗并自动滚动。",
            fg=THEME["muted"],
            bg=THEME["card"],
            font=(self.fonts["body"], 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        transcript_grid = tk.Frame(transcript_shell, bg=THEME["card"])
        transcript_grid.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        transcript_grid.grid_columnconfigure(0, weight=1)
        transcript_grid.grid_columnconfigure(1, weight=1)
        transcript_grid.grid_rowconfigure(0, weight=1)

        self.outbound_transcript = TranscriptPane(
            transcript_grid,
            title="通道 A 实时翻译",
            lane_text="我的语音 → 对方听到的译文",
            accent=THEME["blue"],
            accent_soft=THEME["blue_soft"],
            fonts=self.fonts,
        )
        self.inbound_transcript = TranscriptPane(
            transcript_grid,
            title="通道 B 实时翻译",
            lane_text="对方语音 → 我听到的译文",
            accent=THEME["green"],
            accent_soft=THEME["green_soft"],
            fonts=self.fonts,
        )
        self.outbound_transcript.frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.inbound_transcript.frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._build_drawer()
        self.transcript_open = True

    def _build_header(self) -> None:
        bar = self.header_bar
        bar.grid_columnconfigure(0, weight=1)

        brand = tk.Frame(bar, bg=THEME["header"])
        brand.grid(row=0, column=0, sticky="w", padx=12, pady=12)
        tk.Label(brand, text="NOVA INTERP", fg=THEME["text"], bg=THEME["header"], font=(self.fonts["display"], 20)).pack(anchor="w")
        tk.Label(
            brand,
            textvariable=self.global_hint_var,
            fg=THEME["muted"],
            bg=THEME["header"],
            font=(self.fonts["body"], 10),
        ).pack(anchor="w", pady=(2, 0))
        badge_row = tk.Frame(brand, bg=THEME["header"])
        badge_row.pack(anchor="w", pady=(8, 0))
        tk.Label(badge_row, text="Dual Channel", fg="#9EC1FF", bg=THEME["blue_soft"], padx=8, pady=3, font=(self.fonts["body"], 9)).pack(side="left", padx=(0, 6))
        tk.Label(badge_row, text="Low Latency", fg="#88E0B6", bg=THEME["green_soft"], padx=8, pady=3, font=(self.fonts["body"], 9)).pack(side="left")

        control = tk.Frame(bar, bg=THEME["header"])
        control.grid(row=0, column=1, sticky="e", padx=12, pady=12)

        scene_block = tk.Frame(control, bg=THEME["header"])
        scene_block.pack(side="left", padx=(0, 12))
        tk.Label(scene_block, text="场景模板", fg=THEME["muted"], bg=THEME["header"], font=(self.fonts["body"], 9)).pack(anchor="w")
        self.scene_combo = ttk.Combobox(
            scene_block,
            textvariable=self.scene_var,
            values=[scene["label"] for scene in SCENE_PRESETS.values()],
            state="readonly",
            style="Dark.TCombobox",
            width=18,
        )
        self.scene_combo.pack(anchor="w", pady=(4, 0))
        self.scene_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_scene_by_label(self.scene_var.get(), preserve_devices=True))

        status_wrap = tk.Frame(control, bg=THEME["header"])
        status_wrap.pack(side="left", padx=(0, 10))
        self.status_dot = tk.Canvas(status_wrap, width=10, height=10, bg=THEME["header"], highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 6))
        paint_dot(self.status_dot, THEME["muted_soft"])
        self.status_badge = tk.Label(status_wrap, textvariable=self.global_status_var, fg=THEME["muted"], bg=THEME["header"], font=(self.fonts["body"], 10))
        self.status_badge.pack(side="left")

        self.export_button = ttk.Button(control, text="导出", style="Ghost.TButton", command=self.export_session)
        self.export_button.pack(side="left", padx=(0, 8))
        self.refresh_button = ttk.Button(control, text="刷新设备", style="Ghost.TButton", command=self.refresh_devices)
        self.refresh_button.pack(side="left", padx=(0, 8))
        self.settings_button = ttk.Button(control, text="⚙", style="Ghost.TButton", command=self.toggle_settings_drawer, width=3)
        self.settings_button.pack(side="left", padx=(0, 8))
        self.start_button = ttk.Button(control, text="启动", style="Accent.TButton", command=self.start_channels)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(control, text="停止", style="Danger.TButton", command=self.stop_channels)
        self.stop_button.pack(side="left")

    def _build_drawer(self) -> None:
        self.drawer = tk.Frame(self.root, bg=THEME["panel"], highlightthickness=1, highlightbackground=THEME["border"])

        header = tk.Frame(self.drawer, bg=THEME["panel"])
        header.pack(fill="x", padx=18, pady=(18, 12))
        tk.Label(header, text="引擎凭证", fg=THEME["text"], bg=THEME["panel"], font=(self.fonts["title"], 16)).pack(side="left")
        ttk.Button(header, text="×", style="Ghost.TButton", command=self.hide_settings_drawer, width=3).pack(side="right")

        body = tk.Frame(self.drawer, bg=THEME["panel"])
        body.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        body.grid_columnconfigure(0, weight=1)

        self._drawer_field(body, "APP ID", self.app_key_var, 0)
        self._drawer_field(body, "Access Token", self.access_key_var, 1)
        self._drawer_field(body, "Secret Key", self.secret_key_var, 2)
        self._drawer_field(body, "Resource ID", self.resource_id_var, 3)

        tk.Label(
            body,
            text="凭证默认隐藏，避免占据主界面。运行时这些输入会自动锁定，只保留查看。",
            fg=THEME["muted"],
            bg=THEME["panel"],
            wraplength=320,
            justify="left",
            font=(self.fonts["body"], 10),
        ).grid(row=8, column=0, sticky="w", pady=(8, 16))

        self.drawer_save_button = ttk.Button(body, text="保存配置", style="Accent.TButton", command=self._save_config)
        self.drawer_save_button.grid(row=9, column=0, sticky="ew", pady=(0, 8))

    def _drawer_field(self, parent: tk.Widget, label: str, variable: tk.StringVar, row: int) -> None:
        tk.Label(parent, text=label, fg=THEME["muted"], bg=THEME["panel"], font=(self.fonts["body"], 10)).grid(row=row * 2, column=0, sticky="w", pady=(0 if row == 0 else 10, 6))
        entry = ttk.Entry(parent, textvariable=variable, style="Dark.TEntry")
        entry.grid(row=row * 2 + 1, column=0, sticky="ew", ipady=6)
        setattr(self, f"drawer_entry_{row}", entry)

    def _maximize_window(self) -> None:
        try:
            self.root.state("zoomed")
        except tk.TclError:
            pass

    def _set_initial_split(self) -> None:
        return

    def _draw_main_signal(self, mode: str) -> None:
        return

    def _handle_backdrop_click(self, _event=None) -> None:
        self._handle_escape()

    def _handle_escape(self, _event=None) -> None:
        if self.settings_open:
            self.hide_settings_drawer()
        elif not self.transcript_open:
            self.show_transcript_dock()

    def _quick_toggle_channels(self) -> None:
        if any(self._channel_running(channel_id) for channel_id in ("outbound", "inbound")):
            self.stop_channels()
        else:
            self.start_channels()

    def toggle_drawer(self) -> None:
        self.toggle_settings_drawer()

    def show_drawer(self) -> None:
        self.show_settings_drawer()

    def hide_drawer(self) -> None:
        self.hide_settings_drawer()

    def toggle_transcript_dock(self) -> None:
        if self.transcript_open:
            self.hide_transcript_dock()
        else:
            self.show_transcript_dock()

    def show_transcript_dock(self) -> None:
        self.transcript_section.grid()
        self.transcript_open = True

    def hide_transcript_dock(self) -> None:
        self.transcript_section.grid_remove()
        self.transcript_open = False

    def toggle_settings_drawer(self) -> None:
        if self.settings_open:
            self.hide_settings_drawer()
        else:
            self.show_settings_drawer()

    def show_settings_drawer(self) -> None:
        self.drawer.update_idletasks()
        height = max(self.drawer.winfo_reqheight(), 320)
        self.drawer.place(relx=0.988, y=86, anchor="ne", width=360, height=height)
        self.drawer.lift()
        self.drawer_open = True
        self.settings_open = True

    def hide_settings_drawer(self) -> None:
        self.drawer.place_forget()
        self.drawer_open = False
        self.settings_open = False

    def _card(self, channel_id: str) -> ChannelCard:
        return self.outbound_card if channel_id == "outbound" else self.inbound_card

    def _route_panel(self, channel_id: str) -> RouteDiagnosticsCard:
        return self.outbound_route_panel if channel_id == "outbound" else self.inbound_route_panel

    def _transcript(self, channel_id: str) -> TranscriptPane:
        return self.outbound_transcript if channel_id == "outbound" else self.inbound_transcript

    def _refresh_route_panel(self, channel_id: str) -> None:
        card = self._card(channel_id)
        panel = self._route_panel(channel_id)
        stats = self.stats_by_channel.get(channel_id, {})
        session_state = stats.get("session_state", "idle")
        panel.set_route(card.source_language_var.get().strip() or "Source", card.target_language_var.get().strip() or "Target")
        panel.set_state(
            input_active=bool(card.input_device_var.get().strip()),
            engine_active=session_state in {"starting", "running"},
            output_active=bool(card.output_device_var.get().strip()),
            signal_kind=card.signal_kind,
        )

    def _refresh_route_panels(self) -> None:
        for channel_id in ("outbound", "inbound"):
            self._refresh_route_panel(channel_id)

    def _set_controls_locked(self, locked: bool) -> None:
        self.controls_locked = locked
        self.scene_combo.configure(state="disabled" if locked else "readonly")
        self.refresh_button.configure(state="disabled" if locked else "normal")
        self.start_button.configure(state="disabled" if locked else "normal")
        self.stop_button.configure(state="normal" if locked else "disabled")
        self.settings_button.configure(state="normal")

        for widget in (
            self.drawer_entry_0,
            self.drawer_entry_1,
            self.drawer_entry_2,
            self.drawer_entry_3,
        ):
            widget.configure(state="disabled" if locked else "normal")
        self.drawer_save_button.configure(state="disabled" if locked else "normal")

        self.outbound_card.set_running_mode(locked)
        self.inbound_card.set_running_mode(locked)
        self._refresh_route_panels()

    def _pick_device(self, channel_id: str, kind: str) -> None:
        card = self._card(channel_id)
        values = list(self.input_ids_by_label.keys()) if kind == "input" else list(self.output_ids_by_label.keys())
        current = card.input_device_var.get().strip() if kind == "input" else card.output_device_var.get().strip()
        title = "选择输入设备" if kind == "input" else "选择输出设备"
        if not values:
            messagebox.showerror("没有可选设备", "当前没有可选音频设备，请先刷新。")
            return

        dialog = DevicePickerDialog(self.root, title, values, current, self.fonts)
        selected = dialog.show()
        if not selected:
            return

        if kind == "input":
            card.input_device_var.set(selected)
        else:
            card.output_device_var.set(selected)
        self._on_config_changed()

    def _on_config_changed(self) -> None:
        if self.suspend_config_events:
            return
        self._refresh_route_panels()
        if self.input_ids_by_label and self.output_ids_by_label and not self.controls_locked:
            try:
                self._save_config()
            except Exception:
                pass

    def refresh_devices(self) -> None:
        previous_suspend = self.suspend_config_events
        self.suspend_config_events = True
        previous = {
            "outbound_input": self.outbound_card.input_device_var.get().strip(),
            "outbound_output": self.outbound_card.output_device_var.get().strip(),
            "inbound_input": self.inbound_card.input_device_var.get().strip(),
            "inbound_output": self.inbound_card.output_device_var.get().strip(),
        }

        self.catalog.refresh()
        microphones = self.catalog.microphone_options()
        speakers = self.catalog.speaker_options()
        self.input_labels_by_id, self.input_ids_by_label = build_device_display_maps(microphones)
        self.output_labels_by_id, self.output_ids_by_label = build_device_display_maps(speakers)

        input_labels = list(self.input_ids_by_label.keys())
        output_labels = list(self.output_ids_by_label.keys())
        self.outbound_card.input_combo.configure(values=input_labels)
        self.outbound_card.output_combo.configure(values=output_labels)
        self.inbound_card.input_combo.configure(values=input_labels)
        self.inbound_card.output_combo.configure(values=output_labels)

        self._restore_or_default(
            self.outbound_card.input_device_var,
            previous["outbound_input"],
            input_labels,
            self.catalog.default_microphone_id(),
            self.input_labels_by_id,
        )
        self._restore_or_default(
            self.outbound_card.output_device_var,
            previous["outbound_output"],
            output_labels,
            self.catalog.default_speaker_id(),
            self.output_labels_by_id,
        )
        self._restore_or_default(
            self.inbound_card.input_device_var,
            previous["inbound_input"],
            input_labels,
            self.catalog.default_loopback_id(),
            self.input_labels_by_id,
        )
        self._restore_or_default(
            self.inbound_card.output_device_var,
            previous["inbound_output"],
            output_labels,
            self.catalog.default_speaker_id(),
            self.output_labels_by_id,
        )

        self.global_hint_var.set(f"已刷新设备：输入 {len(self.input_ids_by_label)} 个，输出 {len(self.output_ids_by_label)} 个。")
        self.log("info", self.global_hint_var.get())
        self.suspend_config_events = previous_suspend
        self._refresh_route_panels()

    def _restore_or_default(
        self,
        variable: tk.StringVar,
        previous_label: str,
        available_labels: list[str],
        default_device_id: str,
        labels_by_id: dict[str, str],
    ) -> None:
        if previous_label and previous_label in available_labels:
            variable.set(previous_label)
            return
        if default_device_id:
            variable.set(labels_by_id.get(default_device_id, ""))
            return
        if available_labels:
            variable.set(available_labels[0])

    def _scene_id_from_label(self, label: str) -> str:
        for scene_id, scene in SCENE_PRESETS.items():
            if scene["label"] == label:
                return scene_id
        normalized = label.lower()
        if "discord" in normalized:
            return "discord_bidirectional"
        if "studio" in normalized or "保真" in label:
            return "studio_demo"
        if "字幕" in label or "caption" in normalized:
            return "caption_priority"
        if "英文" in label or "english" in normalized:
            return "double_english"
        return "discord_bidirectional"

    def _apply_scene_by_label(self, label: str, preserve_devices: bool = True) -> None:
        if self.controls_locked:
            return
        previous_suspend = self.suspend_config_events
        self.suspend_config_events = True
        scene = SCENE_PRESETS[self._scene_id_from_label(label)]
        self.scene_var.set(scene["label"])

        for card, key in ((self.outbound_card, "outbound"), (self.inbound_card, "inbound")):
            existing_input = card.input_device_var.get()
            existing_output = card.output_device_var.get()
            config = scene[key]
            card.source_language_var.set(language_label(config["source_language"]))
            card.target_language_var.set(language_label(config["target_language"]))
            card.speaker_id_var.set(config.get("speaker_id", ""))
            card.apply_profile(config["performance_profile"])
            card.chunk_ms_var.set(config["chunk_ms"])
            card.jitter_buffer_ms_var.set(config["jitter_buffer_ms"])
            card.target_audio_rate_var.set(config["target_audio_rate"])
            card.input_gain_var.set(config["input_gain"])
            for mode_label, mode_key in SUBTITLE_MODES:
                if mode_key == config["subtitle_mode"]:
                    card.subtitle_mode_var.set(mode_label)
                    break
            if preserve_devices:
                card.input_device_var.set(existing_input)
                card.output_device_var.set(existing_output)

        self.global_hint_var.set(scene["description"])
        self.log("info", f"已套用场景：{scene['label']}")
        self.suspend_config_events = previous_suspend
        self._refresh_route_panels()
        self._save_config()

    def _build_channel_settings(self, channel_id: str, display_name: str, card: ChannelCard) -> ChannelSettings | None:
        input_label = card.input_device_var.get().strip()
        output_label = card.output_device_var.get().strip()
        if not input_label or not output_label:
            messagebox.showerror("缺少设备", f"{display_name} 需要同时选择输入设备和输出设备。")
            return None
        if input_label not in self.input_ids_by_label or output_label not in self.output_ids_by_label:
            messagebox.showerror("设备无效", f"{display_name} 的设备选择无效，请先刷新设备。")
            return None
        return card.to_settings(channel_id, display_name, self.input_ids_by_label, self.output_ids_by_label)

    def start_channels(self) -> None:
        if self.channels and any(channel.is_running for channel in self.channels.values()):
            messagebox.showinfo("正在运行", "双通道已经启动。")
            return

        app_key = self.app_key_var.get().strip()
        access_key = self.access_key_var.get().strip()
        resource_id = self.resource_id_var.get().strip() or DEFAULT_RESOURCE_ID
        if not app_key or not access_key:
            messagebox.showerror("缺少凭证", "请先在右上角设置中填入 APP ID 和 Access Token。")
            return

        outbound_settings = self._build_channel_settings("outbound", "通道 A", self.outbound_card)
        inbound_settings = self._build_channel_settings("inbound", "通道 B", self.inbound_card)
        if outbound_settings is None or inbound_settings is None:
            return

        self.stop_channels()
        self._save_config()
        self.transcripts = {"outbound": [], "inbound": []}
        self.stats_by_channel = {"outbound": {}, "inbound": {}}
        self.channel_settings_cache = {
            "outbound": asdict(outbound_settings),
            "inbound": asdict(inbound_settings),
        }

        credentials = Credentials(app_key=app_key, access_key=access_key, resource_id=resource_id)
        self.channels = {
            "outbound": TranslationChannel(self.catalog, outbound_settings, credentials, self.event_queue.put),
            "inbound": TranslationChannel(self.catalog, inbound_settings, credentials, self.event_queue.put),
        }

        for channel_id in ("outbound", "inbound"):
            self._card(channel_id).set_status("启动中")
            self._card(channel_id).set_signal_state("warning", "连接中")
            self._transcript(channel_id).clear()

        for channel in self.channels.values():
            channel.start()

        self._set_controls_locked(True)
        self._refresh_global_state()
        self.log("info", "双引擎已启动")
        self._refresh_route_panels()

    def stop_channels(self) -> None:
        for channel in self.channels.values():
            channel.stop()
        for channel in self.channels.values():
            channel.join(timeout=2.0)
        self.channels = {}
        self._set_controls_locked(False)
        for card in (self.outbound_card, self.inbound_card):
            card.set_status("已停止")
            card.set_signal_state("idle", "待命")
            card.set_alert_pulse(False, False)
        self.channel_alerts = {"outbound": False, "inbound": False}
        self._refresh_global_state()
        self._refresh_route_panels()

    def export_session(self) -> None:
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        json_path = OUTPUT_DIR / f"session-{timestamp}.json"
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "scene": self.scene_var.get(),
            "channels": {
                "outbound": {
                    "settings": self.channel_settings_cache.get("outbound", self.outbound_card.serialize_ui(self.input_ids_by_label, self.output_ids_by_label)),
                    "stats": self.stats_by_channel.get("outbound", {}),
                    "transcript": self.transcripts.get("outbound", []),
                },
                "inbound": {
                    "settings": self.channel_settings_cache.get("inbound", self.inbound_card.serialize_ui(self.input_ids_by_label, self.output_ids_by_label)),
                    "stats": self.stats_by_channel.get("inbound", {}),
                    "transcript": self.transcripts.get("inbound", []),
                },
            },
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.global_hint_var.set(f"已导出会话：{json_path.name}")
        self.log("info", self.global_hint_var.get())

    def _load_config(self) -> bool:
        if not CONFIG_PATH.exists():
            return False
        previous_suspend = self.suspend_config_events
        self.suspend_config_events = True
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            self.log("warn", f"读取配置失败：{exc}")
            self.suspend_config_events = previous_suspend
            return False

        self.app_key_var.set(data.get("app_key", ""))
        self.access_key_var.set(data.get("access_key", ""))
        self.secret_key_var.set(data.get("secret_key", ""))
        self.resource_id_var.set(data.get("resource_id", DEFAULT_RESOURCE_ID))

        selected_scene = data.get("selected_scene", "")
        if selected_scene:
            self.scene_var.set(SCENE_PRESETS[self._scene_id_from_label(selected_scene)]["label"])
            self.global_hint_var.set(SCENE_PRESETS[self._scene_id_from_label(selected_scene)]["description"])

        channels = data.get("channels", {})
        self.outbound_card.apply_config(channels.get("outbound", {}), self.input_labels_by_id, self.output_labels_by_id)
        self.inbound_card.apply_config(channels.get("inbound", {}), self.input_labels_by_id, self.output_labels_by_id)
        self.suspend_config_events = previous_suspend
        self._refresh_route_panels()
        self.log("info", "已加载本地配置")
        return True

    def _save_config(self) -> None:
        data = {
            "app_key": self.app_key_var.get().strip(),
            "access_key": self.access_key_var.get().strip(),
            "secret_key": self.secret_key_var.get().strip(),
            "resource_id": self.resource_id_var.get().strip() or DEFAULT_RESOURCE_ID,
            "selected_scene": self.scene_var.get(),
            "channels": {
                "outbound": self.outbound_card.serialize_ui(self.input_ids_by_label, self.output_ids_by_label),
                "inbound": self.inbound_card.serialize_ui(self.input_ids_by_label, self.output_ids_by_label),
            },
        }
        CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log("info", "配置已保存")

    def _channel_running(self, channel_id: str) -> bool:
        channel = self.channels.get(channel_id)
        return channel.is_running if channel is not None else False

    def _refresh_global_state(self) -> None:
        errors = any(self.channel_alerts.values()) or any(self.stats_by_channel[ch].get("last_error") for ch in ("outbound", "inbound"))
        running = any(self._channel_running(ch) for ch in ("outbound", "inbound"))

        if errors:
            self.global_status_var.set("异常")
            paint_dot(self.status_dot, THEME["red"])
            self.status_badge.configure(fg=THEME["red"], bg=THEME["header"])
            self._draw_main_signal("error")
        elif running:
            self.global_status_var.set("运行中")
            paint_dot(self.status_dot, THEME["green"])
            self.status_badge.configure(fg=THEME["text"], bg=THEME["header"])
            self._draw_main_signal("running")
        else:
            self.global_status_var.set("待命")
            paint_dot(self.status_dot, THEME["muted_soft"])
            self.status_badge.configure(fg=THEME["muted"], bg=THEME["header"])
            self._draw_main_signal("idle")

        latency_candidates = [
            value
            for channel_id in ("outbound", "inbound")
            for value in (
                self.stats_by_channel[channel_id].get("first_translation_latency_ms"),
                self.stats_by_channel[channel_id].get("first_audio_latency_ms"),
            )
            if isinstance(value, (int, float))
        ]
        if running and latency_candidates:
            self.global_hint_var.set(f"当前延迟区间 {min(latency_candidates):.1f} ms - {max(latency_candidates):.1f} ms")
        elif running:
            self.global_hint_var.set("正在等待字幕与译音回流…")

    def _refresh_channel_health(self, channel_id: str) -> None:
        card = self._card(channel_id)
        stats = self.stats_by_channel.get(channel_id, {})
        state = stats.get("session_state", "idle")
        last_status = stats.get("last_status", "")
        last_error = stats.get("last_error", "")
        session_sec = float(stats.get("session_sec", 0) or 0)
        sent_chunks = int(stats.get("sent_chunks", 0) or 0)
        has_text = bool(stats.get("source_partials") or stats.get("source_sentences") or stats.get("translation_partials") or stats.get("translation_sentences"))

        alert = False
        if last_error or "异常" in card.status_var.get() or "失败" in card.status_var.get() or "找不到" in card.status_var.get():
            card.set_signal_state("error", "通道异常")
            alert = True
        elif state == "starting":
            card.set_signal_state("warning", "连接中")
        elif state == "running":
            if sent_chunks == 0 and session_sec >= 4:
                card.set_signal_state("error", "无输入信号")
                alert = True
            elif "静音" in last_status:
                card.set_signal_state("warning", "静音 / 等待说话")
            elif has_text:
                card.set_signal_state("ok", "翻译中")
            else:
                card.set_signal_state("warning", "等待语音输入")
        else:
            card.set_signal_state("idle", "待命")

        self.channel_alerts[channel_id] = alert
        self._refresh_route_panel(channel_id)

    def _drain_events(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            self._apply_event(event)

        self._refresh_global_state()
        self.root.after(120, self._drain_events)

    def _apply_event(self, event: dict) -> None:
        channel_id = event["channel"]
        card = self._card(channel_id)
        transcript = self._transcript(channel_id)
        kind = event["kind"]
        text = event["text"]
        stamp = format_ts(event.get("timestamp"))

        if kind == "status":
            card.set_status(text)
            self.log("info", f"{channel_id} | {text}")
            self._refresh_channel_health(channel_id)
            return

        if kind == "error":
            card.set_status(text)
            self.stats_by_channel[channel_id]["last_error"] = text
            self.log("error", f"{channel_id} | {text}")
            self._refresh_channel_health(channel_id)
            return

        if kind == "stats":
            stats = event.get("stats", {})
            self.stats_by_channel[channel_id] = stats
            card.update_stats(stats)
            transcript.update_stats(stats)
            self._refresh_channel_health(channel_id)
            return

        if kind == "source_partial":
            card.update_preview(source=text)
            transcript.update_partial(source=text)
            return

        if kind == "target_partial":
            card.update_preview(target=text)
            transcript.update_partial(target=text)
            return

        if kind == "source_final":
            card.update_preview(source=text)
            transcript.update_partial(source=text)
            transcript.append_final("source", text, stamp)
            self.transcripts[channel_id].append({"time": stamp, "kind": "source", "text": text})
            return

        if kind == "target_final":
            card.update_preview(target=text)
            transcript.update_partial(target=text)
            transcript.append_final("target", text, stamp)
            self.transcripts[channel_id].append({"time": stamp, "kind": "target", "text": text})

    def _pulse_alerts(self) -> None:
        self.alert_phase = not self.alert_phase
        self.outbound_card.set_alert_pulse(self.channel_alerts["outbound"], self.alert_phase)
        self.inbound_card.set_alert_pulse(self.channel_alerts["inbound"], self.alert_phase)
        self.outbound_route_panel.set_alert_pulse(self.channel_alerts["outbound"], self.alert_phase)
        self.inbound_route_panel.set_alert_pulse(self.channel_alerts["inbound"], self.alert_phase)
        self.root.after(350, self._pulse_alerts)

    def log(self, level: str, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.runtime_log_lines.append(f"{stamp} [{level.upper()}] {message}")
        self.runtime_log_lines = self.runtime_log_lines[-40:]

    def on_close(self) -> None:
        self.stop_channels()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    NovaInterpApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
