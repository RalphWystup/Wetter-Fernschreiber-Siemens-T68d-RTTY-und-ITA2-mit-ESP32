"""
Fernschreiber- & OLED-Emulator fuer RTTY_Wetter_18.py
=====================================================

Bildet auf einem normalen PC nach:
  * den Fernschreiber T58d  (Zeichen erscheinen "getippt", im 50-Baud-Takt)
  * das OLED-Display        (Status: WLAN / Datum / Uhr / Laufschrift)
  * die Motor-/Freigabe-Lampe

...und verwendet dabei ECHTE Wetterdaten von wttr.in.

Der Clou: Es werden die *echten* Funktionen aus RTTY_Wetter_18.py benutzt
(ITA2-Kodierung, Wetterabruf, Komplett-/Aenderungsdruck). Nur die
MicroPython-Hardware (machine/network/urequests/ssd1306) wird durch
Emulation ersetzt.

Start (grafisch):   python3 fernschreiber_emulator.py
Start (Terminal):   python3 fernschreiber_emulator.py --selftest
"""

import sys, types, time, threading, queue

# ---------------------------------------------------------------------------
# 0) Ereigniskanal (thread-sicher) zwischen "Hardware" und Anzeige
# ---------------------------------------------------------------------------
EVENTS = queue.Queue()      # ("char", s) | ("oled", [zeilen]) | ("motor", 0/1)
STOP   = threading.Event()

MOTOR_PIN = 16

# ---------------------------------------------------------------------------
# 1) MicroPython-Module durch Emulation ersetzen  (VOR dem Import von rtty!)
# ---------------------------------------------------------------------------
machine = types.ModuleType("machine")
class Pin:
    OUT = 1; IN = 0
    def __init__(self, id, mode=None, value=None):
        self.id = id
        self._v = 0 if value is None else value
    def value(self, v=None):
        if v is None:
            return self._v
        self._v = v
        if self.id == MOTOR_PIN:
            EVENTS.put(("motor", v))
class ADC:
    ATTN_11DB = 3; WIDTH_12BIT = 3
    def __init__(self, pin): self.pin = pin
    def atten(self, a): pass
    def width(self, w): pass
    def read(self): return 2048          # ~1.65 V Dummy
class I2C:
    def __init__(self, *a, **k): pass
machine.Pin = Pin; machine.ADC = ADC; machine.I2C = I2C
sys.modules["machine"] = machine

network = types.ModuleType("network")
class WLAN:
    STA_IF = 0
    def __init__(self, *a): pass
    def active(self, *a): pass
    def isconnected(self): return True
    def connect(self, *a): pass
    def ifconfig(self): return ("<IP-des-ESP32>", "<Netzmaske>", "<IP-des-Routers>", "<IP-des-Namensdienstes>")
network.WLAN = WLAN; network.STA_IF = 0
sys.modules["network"] = network

import urllib.request
urequests = types.ModuleType("urequests")
class _Resp:
    def __init__(self, text): self.text = text
    def close(self): pass
def _get(url, **k):
    with urllib.request.urlopen(url.replace("|", "%7C"), timeout=10) as r:
        return _Resp(r.read().decode("utf-8"))
urequests.get = _get
sys.modules["urequests"] = urequests

# ---- OLED-Emulation: sammelt text()-Aufrufe, rendert bei show() ein 16x8-Raster
class EmuDisplay:
    COLS = 16; ROWS = 8
    def __init__(self, *a, **k): self._draws = []
    def fill(self, c): self._draws = []
    def text(self, s, x, y, *a): self._draws.append((x, y, str(s)))
    def show(self):
        grid = [[" "] * self.COLS for _ in range(self.ROWS)]
        for (x, y, s) in self._draws:
            row = min(y // 8, self.ROWS - 1); col = x // 8
            for i, ch in enumerate(s):
                c = col + i
                if 0 <= c < self.COLS:
                    grid[row][c] = ch
        EVENTS.put(("oled", ["".join(r) for r in grid]))
ssd1306 = types.ModuleType("ssd1306")
ssd1306.SSD1306_I2C = EmuDisplay
sys.modules["ssd1306"] = ssd1306

# ---------------------------------------------------------------------------
# 2) Das echte Programm importieren (nutzt jetzt unsere Emulation)
# ---------------------------------------------------------------------------
import RTTY_Wetter_20 as rtty

# ---------------------------------------------------------------------------
# 3) Emulierter Sender: nutzt die ECHTE Kodier-Pipeline, gibt aber Zeichen
#    an die Anzeige aus (mit 50-Baud-Timing, beschleunigbar via SPEED).
# ---------------------------------------------------------------------------
class EmuSender(rtty.T68dSender):
    SPEED = 4.0     # 1.0 = echtes 50 Baud; groesser = schneller

    def _char_time(self):
        # ~7,5 Bit pro Zeichen (Start + 5 Daten + 1,5 Stopp)
        return (self.BIT_TIME * 7.5) / EmuSender.SPEED

    def _send_char(self, ch):
        u = ch.upper()
        if u in rtty._BAUDOT_LETTERS or u in rtty._BAUDOT_FIGURES:
            time.sleep(self._char_time())
            EVENTS.put(("char", u))

    def send_crlf(self):
        time.sleep(self._char_time())
        EVENTS.put(("char", "\n"))

    def _send_frame(self, bits):
        # wird von print_header direkt aufgerufen (CR/LF/LTRS)
        time.sleep(self._char_time())
        if bits == rtty._CODE_LF:
            EVENTS.put(("char", "\n"))

    def sync(self, duration=0.5):
        time.sleep(min(duration, 0.2))

# ---------------------------------------------------------------------------
# 4) Stations-Ablauf – spiegelt main() aus RTTY_Wetter_18, aber emulatorfreundlich
# ---------------------------------------------------------------------------
DEMO_INTERVAL = 20        # s: so oft echtes Wetter holen (Demo)
DEMO_KOMPLETT = 6 * 3600  # s: Komplett-Intervall (wie Original)

def run_station(once=False):
    oled = EmuDisplay()
    oled.fill(0)
    oled.text("T58d Wetterstat.", 0, 0)
    oled.text("Verbinde WLAN...", 0, 16)
    oled.show()
    time.sleep(0.5)

    sender = EmuSender(tx_pin=17, adc_pins=[32, 33, 34])
    sender.sync(1.0)

    prev = None
    letzter_komplett = None
    letzter_abruf = None

    while not STOP.is_set():
        jetzt = time.time()
        rtty.oled_status(oled, True, None)

        if letzter_abruf is not None and (jetzt - letzter_abruf) < DEMO_INTERVAL:
            time.sleep(1); continue
        letzter_abruf = jetzt

        w = rtty.get_weather_all()
        if not rtty.is_valid(w):
            print("[EMU] Datensatz ungueltig – kein Druck")
            time.sleep(1); continue

        if prev is None:
            rtty.oled_status(oled, True, "Komplettdruck")
            rtty.send_komplett(sender, w)
            rtty.oled_status(oled, True, None)
            prev = {k: v for k, v in w.items() if rtty.is_value_valid(v)}
            letzter_komplett = jetzt
            if once:
                return
        else:
            geaendert, changed = rtty.has_changed(w, prev)
            if letzter_komplett is None or (jetzt - letzter_komplett) >= DEMO_KOMPLETT:
                rtty.oled_status(oled, True, "Komplettdruck")
                rtty.send_komplett(sender, w)
                letzter_komplett = jetzt
            elif geaendert:
                rtty.oled_status(oled, True, ", ".join(changed))
                rtty.send_aenderung(sender, w, changed)
            for k, v in w.items():
                if rtty.is_value_valid(v):
                    prev[k] = v
        time.sleep(1)

def force_print():
    """Manuell einen Komplettdruck mit aktuellem Wetter ausloesen (GUI-Knopf)."""
    def job():
        sender = EmuSender(tx_pin=17, adc_pins=[32, 33, 34])
        w = rtty.get_weather_all()
        if rtty.is_valid(w):
            rtty.send_komplett(sender, w)
        else:
            EVENTS.put(("char", "\n[KEIN GUELTIGES WETTER]\n"))
    threading.Thread(target=job, daemon=True).start()

# ---------------------------------------------------------------------------
# 5a) Terminal-Selbsttest (ohne Grafik) – prueft die ganze Kette
# ---------------------------------------------------------------------------
def selftest():
    print("=== Fernschreiber-Emulator: Terminal-Selbsttest ===")
    print("(echtes Wetter, EIN Komplettdruck, dann Ende)\n")
    EmuSender.SPEED = 12.0

    def consumer():
        while not STOP.is_set():
            try:
                kind, payload = EVENTS.get(timeout=0.2)
            except queue.Empty:
                continue
            if kind == "char":
                sys.stdout.write(payload); sys.stdout.flush()
            elif kind == "motor":
                sys.stdout.write(f"\n[MOTOR {'AN' if payload else 'AUS'}]\n"); sys.stdout.flush()
            # "oled" wird im Terminal-Test nicht dargestellt
    t = threading.Thread(target=consumer, daemon=True)
    t.start()
    run_station(once=True)
    time.sleep(0.5)
    STOP.set()
    print("\n\n=== Selbsttest fertig ===")

# ---------------------------------------------------------------------------
# 5b) Grafische Oberflaeche (tkinter): OLED + Papierstreifen + Motorlampe
# ---------------------------------------------------------------------------
def gui():
    import tkinter as tk
    from tkinter import font as tkfont

    root = tk.Tk()
    root.title("T58d Fernschreiber-Emulator")
    root.configure(bg="#2b2b2b")

    # --- Kopf: OLED + Motorlampe ---
    top = tk.Frame(root, bg="#2b2b2b"); top.pack(fill="x", padx=10, pady=8)

    oled_cv = tk.Canvas(top, width=260, height=140, bg="#04120a",
                        highlightthickness=2, highlightbackground="#111")
    oled_cv.pack(side="left")
    oled_font = tkfont.Font(family="Courier", size=12, weight="bold")
    oled_items = []

    lamp_frame = tk.Frame(top, bg="#2b2b2b"); lamp_frame.pack(side="left", padx=20)
    tk.Label(lamp_frame, text="MOTOR / FREIGABE", bg="#2b2b2b", fg="#ddd").pack()
    lamp_cv = tk.Canvas(lamp_frame, width=60, height=60, bg="#2b2b2b", highlightthickness=0)
    lamp_cv.pack()
    lamp = lamp_cv.create_oval(8, 8, 52, 52, fill="#3a0000", outline="#555", width=2)

    # --- Mitte: Papierstreifen ---
    paper_font = tkfont.Font(family="Courier", size=12)
    paper = tk.Text(root, width=72, height=22, bg="#f4edcf", fg="#2b2b2b",
                    insertbackground="#f4edcf", font=paper_font, wrap="none",
                    padx=8, pady=6)
    paper.pack(padx=10, pady=6, fill="both", expand=True)

    # --- Fuss: Bedienung ---
    bottom = tk.Frame(root, bg="#2b2b2b"); bottom.pack(fill="x", padx=10, pady=8)
    status = tk.Label(bottom, text="Bereit.", bg="#2b2b2b", fg="#9fd")
    status.pack(side="right")

    started = {"on": False}
    def start():
        if started["on"]:
            return
        started["on"] = True
        status.config(text="Läuft – echtes Wetter wird geholt ...")
        threading.Thread(target=run_station, daemon=True).start()

    def set_speed(mult):
        EmuSender.SPEED = mult
        status.config(text=f"Tempo: {mult:g}x (1x = echtes 50 Baud)")

    tk.Button(bottom, text="Start", command=start).pack(side="left")
    tk.Button(bottom, text="Jetzt drucken", command=force_print).pack(side="left", padx=4)
    tk.Button(bottom, text="1x", command=lambda: set_speed(1)).pack(side="left")
    tk.Button(bottom, text="4x", command=lambda: set_speed(4)).pack(side="left")
    tk.Button(bottom, text="10x", command=lambda: set_speed(10)).pack(side="left")
    def beenden():
        STOP.set(); root.destroy()
    tk.Button(bottom, text="Beenden", command=beenden).pack(side="left", padx=4)

    def draw_oled(lines):
        for it in oled_items:
            oled_cv.delete(it)
        oled_items.clear()
        for r, line in enumerate(lines):
            it = oled_cv.create_text(6, 4 + r * 16, anchor="nw", text=line,
                                     fill="#38e08a", font=oled_font)
            oled_items.append(it)

    def pump():
        try:
            while True:
                kind, payload = EVENTS.get_nowait()
                if kind == "char":
                    paper.insert("end", payload)
                    paper.see("end")
                elif kind == "oled":
                    draw_oled(payload)
                elif kind == "motor":
                    lamp_cv.itemconfig(lamp, fill="#28d248" if payload else "#3a0000")
        except queue.Empty:
            pass
        root.after(15, pump)

    root.after(15, pump)
    root.protocol("WM_DELETE_WINDOW", beenden)
    root.mainloop()

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        try:
            gui()
        except Exception as e:
            print(f"[Grafik nicht verfuegbar: {e}]")
            print("Starte stattdessen den Terminal-Selbsttest ...\n")
            STOP.clear()
            selftest()
