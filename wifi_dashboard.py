"""
WiFi Human Detection - Graphical Dashboard (Tkinter)
Real-time signal graph with detection status
"""

import subprocess
import re
import time
import threading
import statistics
from collections import deque
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import platform

try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("Install matplotlib: pip install matplotlib")


# ─── WiFi scanner ────────────────────────────────────────────────────────────

def get_rssi_linux():
    """Return RSSI (dBm-equivalent) or None"""
    # Strategy 1 – nmcli terse
    try:
        r = subprocess.run(
            ['nmcli', '--terse', '--fields', 'SSID,SIGNAL', 'dev', 'wifi', 'list'],
            capture_output=True, text=True, timeout=4)
        best = 0
        for line in r.stdout.strip().split('\n'):
            if ':' in line:
                *_, sig = line.split(':')
                if sig.strip().isdigit():
                    best = max(best, int(sig.strip()))
        if best:
            return int(-100 + best * 0.7)   # convert % → dBm approx
    except Exception:
        pass

    # Strategy 2 – /proc/net/wireless
    try:
        with open('/proc/net/wireless') as f:
            for line in f.readlines()[2:]:
                parts = line.split()
                if len(parts) >= 4:
                    return int(float(parts[3].rstrip('.')))
    except Exception:
        pass

    # Strategy 3 – iwconfig
    try:
        r = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=4)
        m = re.search(r'Signal level=(-?\d+)', r.stdout)
        if m:
            return int(m.group(1))
    except Exception:
        pass

    return None


# ─── Dashboard ───────────────────────────────────────────────────────────────

class WiFiDashboard:
    WINDOW   = 60          # number of readings to show
    THRESHOLD = 5          # dBm change → movement
    INTERVAL  = 1500       # ms between readings

    COLORS = {
        'bg':        '#0f0f1a',
        'panel':     '#1a1a2e',
        'border':    '#2a2a4a',
        'accent':    '#7c6af7',
        'green':     '#22d3a5',
        'red':       '#f75c6a',
        'amber':     '#f7b731',
        'text':      '#e0e0f5',
        'muted':     '#6b6b9a',
        'line':      '#7c6af7',
        'baseline':  '#2a2a4a',
    }

    def __init__(self, root):
        self.root = root
        self.root.title("WiFi Human Detector — Live Dashboard")
        self.root.configure(bg=self.COLORS['bg'])
        self.root.geometry("900x620")
        self.root.resizable(True, True)

        self.rssi_data   = deque([None] * self.WINDOW, maxlen=self.WINDOW)
        self.time_labels = deque([''] * self.WINDOW,  maxlen=self.WINDOW)
        self.baseline    = None
        self.detections  = 0
        self.running     = True
        self._build_ui()
        self._schedule_update()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        C = self.COLORS

        # ── top bar ──
        top = tk.Frame(self.root, bg=C['bg'], pady=8)
        top.pack(fill='x', padx=16)

        tk.Label(top, text="📡  WiFi Human Detection", font=('Helvetica', 16, 'bold'),
                 fg=C['accent'], bg=C['bg']).pack(side='left')

        self.status_dot = tk.Label(top, text="●", font=('Helvetica', 18),
                                   fg=C['muted'], bg=C['bg'])
        self.status_dot.pack(side='right', padx=(0, 4))
        self.status_lbl = tk.Label(top, text="Calibrating…",
                                   font=('Helvetica', 12, 'bold'),
                                   fg=C['muted'], bg=C['bg'])
        self.status_lbl.pack(side='right', padx=(0, 8))

        # ── metric cards ──
        cards_frame = tk.Frame(self.root, bg=C['bg'])
        cards_frame.pack(fill='x', padx=16, pady=(0, 8))
        for i in range(4):
            cards_frame.columnconfigure(i, weight=1)

        self.card_rssi    = self._card(cards_frame, "Current RSSI", "— dBm", 0)
        self.card_change  = self._card(cards_frame, "Signal Change", "0 dBm",  1)
        self.card_det     = self._card(cards_frame, "Detections",   "0",       2)
        self.card_time    = self._card(cards_frame, "Last Detection","—",      3)

        # ── chart ──
        chart_frame = tk.Frame(self.root, bg=C['panel'],
                               highlightbackground=C['border'], highlightthickness=1)
        chart_frame.pack(fill='both', expand=True, padx=16, pady=(0, 8))

        self.fig = Figure(figsize=(8, 3.2), facecolor=C['panel'])
        self.ax  = self.fig.add_subplot(111)
        self._style_axes()

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        # ── log ──
        log_frame = tk.Frame(self.root, bg=C['bg'])
        log_frame.pack(fill='x', padx=16, pady=(0, 12))

        tk.Label(log_frame, text="Event log", font=('Helvetica', 10),
                 fg=C['muted'], bg=C['bg']).pack(anchor='w')

        self.log_text = tk.Text(log_frame, height=4, bg=C['panel'], fg=C['text'],
                                font=('Courier', 10), bd=0, relief='flat',
                                state='disabled', wrap='word',
                                highlightbackground=C['border'], highlightthickness=1)
        self.log_text.pack(fill='x')

        # tag colours
        self.log_text.tag_config('detect', foreground=C['green'])
        self.log_text.tag_config('clear',  foreground=C['muted'])
        self.log_text.tag_config('error',  foreground=C['amber'])

    def _card(self, parent, label, value, col):
        C = self.COLORS
        f = tk.Frame(parent, bg=C['panel'],
                     highlightbackground=C['border'], highlightthickness=1)
        f.grid(row=0, column=col, sticky='ew', padx=4, pady=2, ipadx=10, ipady=8)
        tk.Label(f, text=label, font=('Helvetica', 9), fg=C['muted'], bg=C['panel']).pack()
        v = tk.Label(f, text=value, font=('Helvetica', 18, 'bold'),
                     fg=C['text'], bg=C['panel'])
        v.pack()
        return v

    def _style_axes(self):
        C = self.COLORS
        ax = self.ax
        ax.set_facecolor(C['panel'])
        self.fig.patch.set_facecolor(C['panel'])
        for spine in ax.spines.values():
            spine.set_color(C['border'])
        ax.tick_params(colors=C['muted'], labelsize=8)
        ax.set_ylabel("Signal (dBm)", color=C['muted'], fontsize=9)
        ax.set_xlabel("Time", color=C['muted'], fontsize=9)
        ax.grid(color=C['baseline'], linestyle='--', linewidth=0.5, alpha=0.5)
        ax.set_xlim(0, self.WINDOW - 1)

    # ── update cycle ─────────────────────────────────────────────────────────

    def _schedule_update(self):
        if self.running:
            threading.Thread(target=self._fetch_and_update, daemon=True).start()

    def _fetch_and_update(self):
        rssi = get_rssi_linux()
        self.root.after(0, self._apply_update, rssi)

    def _apply_update(self, rssi):
        ts = datetime.now().strftime('%H:%M:%S')
        self.rssi_data.append(rssi)
        self.time_labels.append(ts)

        valid = [v for v in self.rssi_data if v is not None]

        if rssi is None:
            self._log(f"[{ts}] No signal", 'error')
            self.card_rssi.config(text="— dBm")
        else:
            self.card_rssi.config(text=f"{rssi} dBm")

            # baseline = mean of first 10 valid readings
            if self.baseline is None and len(valid) >= 10:
                self.baseline = statistics.mean(valid[-10:])
                self._log(f"[{ts}] Baseline set: {self.baseline:.1f} dBm", 'clear')

            if len(valid) >= 3:
                change = abs(valid[-1] - valid[-2]) if len(valid) >= 2 else 0
                self.card_change.config(text=f"{change:.1f} dBm")

                if change > self.THRESHOLD:
                    self.detections += 1
                    self.card_det.config(text=str(self.detections))
                    self.card_time.config(text=ts)
                    self._set_status("HUMAN DETECTED", detected=True)
                    self._log(f"[{ts}] 🟢 Human detected! Δ={change:.1f} dBm", 'detect')
                else:
                    self._set_status("No movement", detected=False)

        self._redraw_chart(valid)

        if self.running:
            self.root.after(self.INTERVAL, self._schedule_update)

    def _set_status(self, text, detected):
        C = self.COLORS
        color = C['green'] if detected else C['muted']
        self.status_lbl.config(text=text, fg=color)
        self.status_dot.config(fg=color)

    def _redraw_chart(self, valid):
        C = self.COLORS
        ax = self.ax
        ax.cla()
        self._style_axes()

        xs = list(range(self.WINDOW))
        ys = list(self.rssi_data)

        # filled area under the signal line
        clean_xs, clean_ys = [], []
        for x, y in zip(xs, ys):
            if y is not None:
                clean_xs.append(x)
                clean_ys.append(y)

        if len(clean_ys) >= 2:
            ax.fill_between(clean_xs, clean_ys, min(clean_ys) - 5,
                            alpha=0.15, color=C['line'])
            ax.plot(clean_xs, clean_ys, color=C['line'], linewidth=2, zorder=3)
            ax.scatter([clean_xs[-1]], [clean_ys[-1]],
                       color=C['accent'], s=50, zorder=4)

            # baseline reference
            if self.baseline:
                ax.axhline(self.baseline, color=C['amber'], linewidth=0.8,
                           linestyle=':', alpha=0.7, label='Baseline')

            # highlight detected points
            all_rssi = list(self.rssi_data)
            for i in range(1, len(all_rssi)):
                if all_rssi[i] is not None and all_rssi[i-1] is not None:
                    if abs(all_rssi[i] - all_rssi[i-1]) > self.THRESHOLD:
                        ax.axvspan(i - 0.5, i + 0.5, color=C['green'], alpha=0.15)

        # x-axis: show only a few tick labels
        step = max(1, self.WINDOW // 8)
        tick_idx = list(range(0, self.WINDOW, step))
        labels_list = list(self.time_labels)
        ax.set_xticks(tick_idx)
        ax.set_xticklabels([labels_list[i] for i in tick_idx],
                            rotation=30, ha='right', fontsize=7)
        ax.set_xlim(0, self.WINDOW - 1)

        if clean_ys:
            pad = max(5, (max(clean_ys) - min(clean_ys)) * 0.3 + 3)
            ax.set_ylim(min(clean_ys) - pad, max(clean_ys) + pad)

        self.canvas.draw()

    def _log(self, msg, tag='clear'):
        self.log_text.config(state='normal')
        self.log_text.insert('end', msg + '\n', tag)
        self.log_text.see('end')
        # keep only last 200 lines
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 200:
            self.log_text.delete('1.0', f'{lines - 200}.0')
        self.log_text.config(state='disabled')

    def on_close(self):
        self.running = False
        self.root.destroy()


# ─── entry point ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not HAS_MPL:
        print("Please install matplotlib first:\n  pip install matplotlib")
    else:
        root = tk.Tk()
        app = WiFiDashboard(root)
        root.protocol("WM_DELETE_WINDOW", app.on_close)
        root.mainloop()
