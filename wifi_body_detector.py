"""
WiFi + Camera Body Detection System
- Live camera feed
- WiFi signal drives body skeleton/heat overlay
- Face is anonymised (blurred / replaced with skeleton)
- Real-time detection status
"""

import subprocess
import re
import time
import threading
import statistics
import math
import random
from collections import deque
from datetime import datetime

import tkinter as tk
from tkinter import ttk

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

from PIL import Image, ImageTk
HAS_PIL = True  # will fail at import if missing


# ─── WiFi scanner ─────────────────────────────────────────────────────────────

def get_rssi():
    """Return RSSI (dBm-approx) or None"""
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
            return int(-100 + best * 0.7)
    except Exception:
        pass
    try:
        with open('/proc/net/wireless') as f:
            for line in f.readlines()[2:]:
                parts = line.split()
                if len(parts) >= 4:
                    return int(float(parts[3].rstrip('.')))
    except Exception:
        pass
    try:
        r = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=4)
        m = re.search(r'Signal level=(-?\d+)', r.stdout)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


# ─── Body skeleton overlay ────────────────────────────────────────────────────

# Keypoint indices (simplified COCO-style)
KP = {
    'nose': 0, 'neck': 1,
    'r_shoulder': 2, 'r_elbow': 3, 'r_wrist': 4,
    'l_shoulder': 5, 'l_elbow': 6, 'l_wrist': 7,
    'r_hip': 8, 'r_knee': 9, 'r_ankle': 10,
    'l_hip': 11, 'l_knee': 12, 'l_ankle': 13,
}

SKELETON = [
    ('neck',      'r_shoulder'), ('neck',      'l_shoulder'),
    ('r_shoulder','r_elbow'),    ('r_elbow',   'r_wrist'),
    ('l_shoulder','l_elbow'),    ('l_elbow',   'l_wrist'),
    ('neck',      'r_hip'),      ('neck',      'l_hip'),
    ('r_hip',     'l_hip'),
    ('r_hip',     'r_knee'),     ('r_knee',    'r_ankle'),
    ('l_hip',     'l_knee'),     ('l_knee',    'l_ankle'),
    ('nose',      'neck'),
]

def build_skeleton_points(cx, cy, scale=1.0, sway=0.0):
    """Build a dict of (x,y) keypoints centred at (cx,cy)"""
    s = scale
    sw = sway * 8   # horizontal sway when movement detected
    pts = {
        'nose':       (cx + sw * 0.3,      cy - int(110*s)),
        'neck':       (cx + sw * 0.2,      cy - int(80*s)),
        'r_shoulder': (cx - int(45*s),     cy - int(55*s)),
        'r_elbow':    (cx - int(70*s) + sw,cy + int(0*s)),
        'r_wrist':    (cx - int(80*s) + sw*1.5, cy + int(55*s)),
        'l_shoulder': (cx + int(45*s),     cy - int(55*s)),
        'l_elbow':    (cx + int(70*s) + sw,cy + int(0*s)),
        'l_wrist':    (cx + int(80*s) + sw*1.5, cy + int(55*s)),
        'r_hip':      (cx - int(28*s),     cy + int(55*s)),
        'r_knee':     (cx - int(32*s) + sw*0.5, cy + int(120*s)),
        'r_ankle':    (cx - int(30*s) + sw*0.3, cy + int(185*s)),
        'l_hip':      (cx + int(28*s),     cy + int(55*s)),
        'l_knee':     (cx + int(32*s) + sw*0.5, cy + int(120*s)),
        'l_ankle':    (cx + int(30*s) + sw*0.3, cy + int(185*s)),
    }
    return {k: (int(x), int(y)) for k, (x, y) in pts.items()}


def draw_skeleton_overlay(frame, detected, signal_strength, change, sway=0.0, alpha=0.85):
    """
    Draw full skeleton + heat aura on top of the camera frame.
    frame: BGR numpy array (modified in-place)
    detected: bool
    signal_strength: 0-100 normalised
    """
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2 - 20
    scale = h / 480.0

    overlay = frame.copy()

    # ── 1. anonymise face region ──────────────────────────────────────────────
    face_r = int(38 * scale)
    nose_y = cy - int(110 * scale)
    # strong gaussian blur to anonymise
    face_x1 = max(0, cx - face_r - 10)
    face_x2 = min(w, cx + face_r + 10)
    face_y1 = max(0, nose_y - face_r - 10)
    face_y2 = min(h, nose_y + face_r + 20)
    face_roi = frame[face_y1:face_y2, face_x1:face_x2]
    if face_roi.size > 0:
        blurred = cv2.GaussianBlur(face_roi, (55, 55), 30)
        frame[face_y1:face_y2, face_x1:face_x2] = blurred

    # ── 2. WiFi heat aura ─────────────────────────────────────────────────────
    aura_radius = int((60 + signal_strength * 1.2) * scale)
    aura_alpha  = 0.18 + (change / 30.0) * 0.3
    aura_alpha  = min(aura_alpha, 0.55)
    aura_color  = (0, 255, 140) if detected else (80, 140, 255)

    # radial gradient aura via concentric circles
    for r in range(aura_radius, 0, -max(1, aura_radius // 12)):
        a = aura_alpha * (1 - r / aura_radius) * 0.6
        cv2.circle(overlay, (cx, cy - int(20 * scale)), r, aura_color, -1)
    cv2.addWeighted(overlay, aura_alpha, frame, 1 - aura_alpha, 0, frame)

    overlay = frame.copy()

    # ── 3. skeleton ───────────────────────────────────────────────────────────
    pts = build_skeleton_points(cx, cy, scale, sway)

    bone_color    = (0, 255, 140) if detected else (60, 160, 255)
    joint_color   = (255, 255, 255)
    bone_thickness = max(2, int(3 * scale))
    joint_radius   = max(4, int(6 * scale))

    # bones
    for a, b in SKELETON:
        if a in pts and b in pts:
            cv2.line(overlay, pts[a], pts[b], bone_color, bone_thickness, cv2.LINE_AA)

    # glow effect: draw thick transparent line underneath
    glow = frame.copy()
    for a, b in SKELETON:
        if a in pts and b in pts:
            cv2.line(glow, pts[a], pts[b], bone_color, bone_thickness * 4, cv2.LINE_AA)
    cv2.addWeighted(glow, 0.25, overlay, 0.75, 0, overlay)

    # joints
    for name, (px, py) in pts.items():
        cv2.circle(overlay, (px, py), joint_radius, joint_color, -1, cv2.LINE_AA)
        cv2.circle(overlay, (px, py), joint_radius + 2, bone_color, 1, cv2.LINE_AA)

    # ── 4. WiFi scan-line effect ──────────────────────────────────────────────
    if detected:
        scan_y = int((time.time() * 120) % h)
        cv2.line(overlay, (0, scan_y), (w, scan_y), (0, 255, 140), 1)

    # ── 5. HUD elements ───────────────────────────────────────────────────────
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs   = 0.5 * scale

    status_txt   = "HUMAN DETECTED" if detected else "SCANNING..."
    status_color = (0, 255, 140) if detected else (80, 160, 255)
    cv2.putText(overlay, status_txt, (12, 28), font, fs * 1.1, status_color, 2, cv2.LINE_AA)

    rssi_txt = f"RSSI: {signal_strength:.0f}%  dChange: {change:.1f}"
    cv2.putText(overlay, rssi_txt, (12, int(h - 12)), font, fs * 0.85,
                (180, 180, 180), 1, cv2.LINE_AA)

    # corner brackets (HUD aesthetic)
    br_sz, br_t = 18, 2
    for (bx, by), dx, dy in [
        ((5,5),    1,  1), ((w-5,5),  -1,  1),
        ((5,h-5),  1, -1), ((w-5,h-5),-1, -1)
    ]:
        cv2.line(overlay,(bx,by),(bx+dx*br_sz,by),    status_color, br_t)
        cv2.line(overlay,(bx,by),(bx,by+dy*br_sz),    status_color, br_t)

    frame[:] = overlay


# ─── Main App ─────────────────────────────────────────────────────────────────

class WiFiBodyApp:
    WIN   = 40
    THOLD = 4

    C = {
        'bg':     '#0a0a14',
        'panel':  '#12121f',
        'border': '#1e1e38',
        'accent': '#00ff8c',
        'blue':   '#3c8cff',
        'text':   '#d0d0f0',
        'muted':  '#555577',
    }

    def __init__(self, root):
        self.root     = root
        self.root.title("WiFi Body Detector")
        self.root.configure(bg=self.C['bg'])
        self.root.geometry("1100x700")

        self.rssi_data  = deque([None] * self.WIN, maxlen=self.WIN)
        self.baseline   = None
        self.detections = 0
        self.detected   = False
        self.change     = 0.0
        self.sway       = 0.0
        self.signal_pct = 50.0
        self.running    = True

        self.cap = None
        self._open_camera()
        self._build_ui()
        self._wifi_thread()
        self._loop()

    def _open_camera(self):
        if not HAS_CV2:
            return
        for idx in range(4):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap = cap
                print(f"Camera opened on index {idx}")
                return
        print("No camera found — skeleton will render on a dark background.")

    def _build_ui(self):
        C = self.C

        # ── left: camera + skeleton ──────────────────────────────────────────
        left = tk.Frame(self.root, bg=C['bg'])
        left.pack(side='left', fill='both', expand=True, padx=(12, 6), pady=12)

        tk.Label(left, text="BODY SCAN", font=('Courier', 11, 'bold'),
                 fg=C['accent'], bg=C['bg']).pack(anchor='w', pady=(0, 4))

        self.cam_label = tk.Label(left, bg='black',
                                  highlightbackground=C['accent'], highlightthickness=1)
        self.cam_label.pack(fill='both', expand=True)

        # ── right: signal graph + stats ──────────────────────────────────────
        right = tk.Frame(self.root, bg=C['bg'], width=340)
        right.pack(side='right', fill='y', padx=(6, 12), pady=12)
        right.pack_propagate(False)

        tk.Label(right, text="WiFi Signal Monitor",
                 font=('Courier', 11, 'bold'), fg=C['blue'], bg=C['bg']
                 ).pack(anchor='w', pady=(0, 8))

        # stat cards
        cards = tk.Frame(right, bg=C['bg'])
        cards.pack(fill='x', pady=(0, 10))
        for i in range(2): cards.columnconfigure(i, weight=1)

        self.lbl_rssi = self._card(cards, "RSSI", "— dBm", 0, 0)
        self.lbl_chg  = self._card(cards, "Change", "0 dBm",  1, 0)
        self.lbl_det  = self._card(cards, "Detections", "0",   0, 1)
        self.lbl_time = self._card(cards, "Last seen",  "—",   1, 1)

        # signal chart
        self.fig = Figure(figsize=(3.2, 2.6), facecolor=C['panel'])
        self.ax  = self.fig.add_subplot(111)
        self._style_ax()
        chart_frame = tk.Frame(right, bg=C['panel'],
                               highlightbackground=C['border'], highlightthickness=1)
        chart_frame.pack(fill='x', pady=(0, 10))
        self.mpl_canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.mpl_canvas.get_tk_widget().pack(fill='x')

        # detection status bar
        self.status_bar = tk.Label(right, text="● SCANNING",
                                   font=('Courier', 13, 'bold'),
                                   fg=C['blue'], bg=C['panel'],
                                   highlightbackground=C['border'], highlightthickness=1,
                                   pady=8)
        self.status_bar.pack(fill='x', pady=(0, 10))

        # log
        tk.Label(right, text="Event log", font=('Courier', 9),
                 fg=C['muted'], bg=C['bg']).pack(anchor='w')
        self.log = tk.Text(right, height=8, bg=C['panel'], fg=C['text'],
                           font=('Courier', 9), bd=0, relief='flat',
                           state='disabled', wrap='word',
                           highlightbackground=C['border'], highlightthickness=1)
        self.log.pack(fill='both', expand=True)
        self.log.tag_config('det',  foreground=C['accent'])
        self.log.tag_config('base', foreground='#f7b731')
        self.log.tag_config('info', foreground=C['muted'])

    def _card(self, parent, label, val, col, row):
        C = self.C
        f = tk.Frame(parent, bg=C['panel'],
                     highlightbackground=C['border'], highlightthickness=1)
        f.grid(row=row, column=col, sticky='ew', padx=3, pady=3, ipadx=6, ipady=5)
        tk.Label(f, text=label, font=('Courier', 8), fg=C['muted'], bg=C['panel']).pack()
        v = tk.Label(f, text=val, font=('Courier', 14, 'bold'), fg=C['text'], bg=C['panel'])
        v.pack()
        return v

    def _style_ax(self):
        C = self.C
        self.ax.set_facecolor(C['panel'])
        self.fig.patch.set_facecolor(C['panel'])
        for sp in self.ax.spines.values():
            sp.set_color(C['border'])
        self.ax.tick_params(colors=C['muted'], labelsize=7)
        self.ax.grid(color=C['border'], linestyle='--', linewidth=0.4)
        self.ax.set_xlim(0, self.WIN - 1)

    # ── WiFi polling (background thread) ─────────────────────────────────────

    def _wifi_thread(self):
        def _poll():
            while self.running:
                rssi = get_rssi()
                self.root.after(0, self._on_rssi, rssi)
                time.sleep(1.5)
        threading.Thread(target=_poll, daemon=True).start()

    def _on_rssi(self, rssi):
        C   = self.C
        ts  = datetime.now().strftime('%H:%M:%S')
        self.rssi_data.append(rssi)
        valid = [v for v in self.rssi_data if v is not None]

        if rssi is None:
            self._log(f"[{ts}] No signal", 'info')
            return

        self.signal_pct = max(0, min(100, (rssi + 100) / 0.7))
        self.lbl_rssi.config(text=f"{rssi} dBm")

        if self.baseline is None and len(valid) >= 10:
            self.baseline = statistics.mean(valid[-10:])
            self._log(f"[{ts}] Baseline: {self.baseline:.1f} dBm", 'base')

        if len(valid) >= 2:
            self.change = abs(valid[-1] - valid[-2])
            self.lbl_chg.config(text=f"{self.change:.1f} dBm")

            if self.change > self.THOLD:
                self.detected = True
                self.sway = random.uniform(-1, 1)
                self.detections += 1
                self.lbl_det.config(text=str(self.detections))
                self.lbl_time.config(text=ts)
                self.status_bar.config(text="● HUMAN DETECTED", fg=C['accent'])
                self._log(f"[{ts}] Human detected! Δ={self.change:.1f}", 'det')
            else:
                self.detected = False
                self.sway *= 0.85  # decay sway
                self.status_bar.config(text="● SCANNING", fg=C['blue'])

        self._redraw_chart(valid)

    def _redraw_chart(self, valid):
        C  = self.C
        ax = self.ax
        ax.cla()
        self._style_ax()

        xs = list(range(self.WIN))
        ys = list(self.rssi_data)
        cxs = [x for x, y in zip(xs, ys) if y is not None]
        cys = [y for y in ys if y is not None]

        if len(cys) >= 2:
            color = C['accent'] if self.detected else C['blue']
            ax.fill_between(cxs, cys, min(cys) - 3, alpha=0.12, color=color)
            ax.plot(cxs, cys, color=color, linewidth=1.5)
            ax.scatter([cxs[-1]], [cys[-1]], color=color, s=30, zorder=5)
            if self.baseline:
                ax.axhline(self.baseline, color='#f7b731', lw=0.7,
                           linestyle=':', alpha=0.6)
            pad = max(3, (max(cys)-min(cys))*0.4 + 2)
            ax.set_ylim(min(cys)-pad, max(cys)+pad)

        ax.set_xlim(0, self.WIN - 1)
        self.mpl_canvas.draw()

    def _log(self, msg, tag='info'):
        self.log.config(state='normal')
        self.log.insert('end', msg + '\n', tag)
        self.log.see('end')
        lines = int(self.log.index('end-1c').split('.')[0])
        if lines > 100:
            self.log.delete('1.0', f'{lines-100}.0')
        self.log.config(state='disabled')

    # ── Camera loop ───────────────────────────────────────────────────────────

    def _loop(self):
        if not self.running:
            return

        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)   # mirror
                draw_skeleton_overlay(
                    frame,
                    detected=self.detected,
                    signal_strength=self.signal_pct,
                    change=self.change,
                    sway=self.sway,
                )
                rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img   = Image.fromarray(rgb)
                imgtk = ImageTk.PhotoImage(image=img)
                self.cam_label.imgtk = imgtk
                self.cam_label.config(image=imgtk)
        else:
            # No camera — draw skeleton on a dark canvas
            h, w = 480, 640
            canvas_frame = np.zeros((h, w, 3), dtype=np.uint8)
            draw_skeleton_overlay(
                canvas_frame,
                detected=self.detected,
                signal_strength=self.signal_pct,
                change=self.change,
                sway=self.sway,
            )
            rgb   = cv2.cvtColor(canvas_frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.cam_label.imgtk = imgtk
            self.cam_label.config(image=imgtk)

        self.root.after(33, self._loop)   # ~30 fps

    def on_close(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.root.destroy()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    missing = []
    if not HAS_CV2:  missing.append("opencv-python")
    if not HAS_MPL:  missing.append("matplotlib")
    try:
        from PIL import Image, ImageTk
    except ImportError:
        missing.append("Pillow")

    if missing:
        print("Install missing packages first:")
        print(f"  pip install {' '.join(missing)}")
    else:
        root = tk.Tk()
        app  = WiFiBodyApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_close)
        root.mainloop()
