"""
Testprogramm fuer RTTY_Wetter_18.py  (laeuft auf normalem CPython, OHNE ESP32).

Es ersetzt die MicroPython-Module (machine, network, urequests, ssd1306)
durch Attrappen ("Stubs") und testet die reine Logik:

  A) Wetter-Parsing  (get_weather_all mit simulierter wttr.in-Antwort)
  B) Live-Abruf      (echtes wttr.in - nur falls Internet da ist)
  C) RTTY-Loopback   (Text -> Bits -> zurueckdekodiert -> vergleichen)
  D) Zeilenumbruch   (_wrap_lines: keine Zeile laenger als 69)

Aufruf:  python3 test_rtty.py
"""

import sys, types, time

# ---------------------------------------------------------------------------
# 1) MicroPython-Module durch Stubs ersetzen (VOR dem Import von RTTY_Wetter_18)
# ---------------------------------------------------------------------------

PIN_LOG = []            # zeichnet alle Pin-Schreibzugriffe auf: (pin_id, wert)

machine = types.ModuleType("machine")
class Pin:
    OUT = 1; IN = 0
    def __init__(self, id, mode=None, value=None):
        self.id = id
        self._v = 0 if value is None else value   # Startwert NICHT loggen
    def value(self, v=None):
        if v is None:
            return self._v
        self._v = v
        PIN_LOG.append((self.id, v))
class ADC:
    ATTN_11DB = 3; WIDTH_12BIT = 3
    def __init__(self, pin): self.pin = pin
    def atten(self, a): pass
    def width(self, w): pass
    def read(self): return 2048
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

ssd1306 = types.ModuleType("ssd1306")
class SSD1306_I2C:
    def __init__(self, *a, **k): pass
    def fill(self, *a): pass
    def text(self, *a): pass
    def show(self, *a): pass
ssd1306.SSD1306_I2C = SSD1306_I2C
sys.modules["ssd1306"] = ssd1306

import urllib.request
urequests = types.ModuleType("urequests")
class _Resp:
    def __init__(self, text): self.text = text
    def close(self): pass
def _get(url, **k):
    # CPython-urllib mag rohes '|' nicht -> kodieren (auf dem ESP32 nicht noetig)
    with urllib.request.urlopen(url.replace("|", "%7C"), timeout=10) as r:
        return _Resp(r.read().decode("utf-8"))
urequests.get = _get
urequests._Resp = _Resp
sys.modules["urequests"] = urequests

# ---------------------------------------------------------------------------
# 2) Jetzt das zu testende Programm importieren
# ---------------------------------------------------------------------------

import RTTY_Wetter_20 as rtty

PASS = 0; FAIL = 0
def check(name, ok, detail=""):
    global PASS, FAIL
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  -> " + detail) if detail else ""))
    if ok: PASS += 1
    else:  FAIL += 1

# ---------------------------------------------------------------------------
# ITA2-Rueckdekodierung (aus den aufgezeichneten Pin-Pegeln)
# ---------------------------------------------------------------------------

LET_REV = {v: k for k, v in rtty._BAUDOT_LETTERS.items()}
FIG_REV = {v: k for k, v in rtty._BAUDOT_FIGURES.items()}

def decode_frames(writes):
    """writes: Liste von 0/1 (nur TX-Pin), je 7 = ein Frame (Start+5Daten+Stopp)."""
    assert len(writes) % 7 == 0, f"Frame-Laenge nicht durch 7 teilbar: {len(writes)}"
    state = "LTRS"; out = []
    for i in range(0, len(writes), 7):
        start = writes[i]
        data  = writes[i+1:i+6]
        stop  = writes[i+6]
        assert start == 0, "Startbit ist nicht 0!"
        assert stop  == 1, "Stoppbit ist nicht 1!"
        code = "".join(str(b) for b in reversed(data))   # zurueck in Tabellen-Orientierung
        if   code == rtty._CODE_LTRS: state = "LTRS"; continue
        elif code == rtty._CODE_FIGS: state = "FIGS"; continue
        elif code == rtty._CODE_CR:   out.append("\r"); continue
        elif code == rtty._CODE_LF:   out.append("\n"); continue
        out.append((LET_REV if state == "LTRS" else FIG_REV).get(code, "?"))
    return "".join(out)

def sende_und_dekodiere(sender, text):
    """Sendet Text ueber den echten _send_frame-Pfad und dekodiert das Ergebnis."""
    PIN_LOG.clear()
    sender._mode = "LTRS"
    orig_sleep = time.sleep
    time.sleep = lambda *a, **k: None      # Timing ueberspringen -> schnell
    try:
        sender.send_text(text)
    finally:
        time.sleep = orig_sleep
    tx = [v for (pid, v) in PIN_LOG if pid == 17]   # nur TX-Pin 17
    return decode_frames(tx)

def erwartetes_ergebnis(sender, text):
    """Was laut Sende-Logik herauskommen muss (fuer den Vergleich)."""
    p = sender._expand(sender._expand_adc(sender._expand_shortcodes(text)))
    p = sender._wrap_lines(p)
    exp = []
    for ch in p:
        if ch == "\n":
            exp.append("\r"); exp.append("\n"); continue
        u = ch.upper()
        if u in rtty._BAUDOT_LETTERS or u in rtty._BAUDOT_FIGURES:
            exp.append(u)
    return "".join(exp)

# ===========================================================================
# TEST A – Wetter-Parsing mit simulierter Antwort
# ===========================================================================
print("\nTEST A: Wetter-Parsing (simulierte wttr.in-Antwort)")
canned = "+18°C|+16°C|83%|1013hPa|↗12km/h|Partly cloudy|06:12:00|21:34:00|🌒"
rtty.urequests.get = lambda url, **k: rtty.urequests._Resp(canned)
w = rtty.get_weather_all()
check("9 Felder vorhanden", len(w) == 9, str(list(w.keys())))
check("TEMP korrekt geparst", w.get("TEMP") == "+18°C", repr(w.get("TEMP")))
check("WIND korrekt geparst", w.get("WIND") == "↗12km/h", repr(w.get("WIND")))
check("WETTER korrekt geparst", w.get("WETTER") == "Partly cloudy", repr(w.get("WETTER")))
check("MOND korrekt geparst", w.get("MOND") == "🌒", repr(w.get("MOND")))
check("keine RICHTUNG mehr (Dusk-Bug behoben)", "RICHTUNG" not in w)
check("Datensatz gilt als gueltig", rtty.is_valid(w) is True)

# Kaputte Antwort (zu wenig Felder) -> muss ungueltig sein
rtty.urequests.get = lambda url, **k: rtty.urequests._Resp("nur|drei|felder")
w_bad = rtty.get_weather_all()
check("Fehlformat wird erkannt (ungueltig)", rtty.is_valid(w_bad) is False, str(w_bad.get("TEMP")))

# "Unknown location" -> ungueltig
check("'Unknown location' ist ungueltig", rtty.is_value_valid("Unknown location: xyz") is False)

# ===========================================================================
# TEST B – Live-Abruf (nur falls Internet verfuegbar)
# ===========================================================================
print("\nTEST B: Live-Abruf von wttr.in (best effort)")
rtty.urequests.get = _get     # echten HTTP-Getter zuruecksetzen
try:
    w_live = rtty.get_weather_all()
    if rtty.is_valid(w_live):
        check("Live-Wetter abgerufen", True, f"TEMP={w_live.get('TEMP')}, WETTER={w_live.get('WETTER')}")
    else:
        print("  [SKIP] Antwort ungueltig (evtl. wttr.in gedrosselt) ->", w_live.get("TEMP"))
except Exception as e:
    print(f"  [SKIP] Kein Internet im Testcontainer ({e})")

# ===========================================================================
# TEST C – RTTY-Loopback (Kodierung Text -> Bits -> Text)
# ===========================================================================
print("\nTEST C: RTTY/ITA2-Loopback (echtes _send_frame)")
sender = rtty.T68dSender(tx_pin=17, adc_pins=[32, 33, 34])
for probe in ["HALLO WELT 123",
              "TEMP +18°C, WIND 12KM/H ÄÖÜ",
              "RYRYRY 55 73 AR SK"]:
    got = sende_und_dekodiere(sender, probe)
    exp = erwartetes_ergebnis(sender, probe)
    check(f"Loopback {probe!r}", got == exp, f"dekodiert={got!r}")

# ===========================================================================
# TEST D – Zeilenumbruch
# ===========================================================================
print("\nTEST D: Zeilenumbruch _wrap_lines (max. 69 Zeichen)")
lang = ("WETTER KUENZELSAU " * 12).strip()
wrapped = sender._wrap_lines(lang)
zeilen = wrapped.split("\n")
check("keine Zeile laenger als 69", all(len(z) <= rtty.T68D_LINE_LENGTH for z in zeilen),
      "max=" + str(max(len(z) for z in zeilen)))
check("kein Wort verloren", wrapped.replace("\n", " ").split() == lang.split())

# ===========================================================================
# TEST E – Zeit aus den Wetterdaten (HTTP-Date-Header -> MEZ/MESZ)
# ===========================================================================
print("\nTEST E: Zeit-Sync (HTTP-Date-Header parsen + Sommerzeit)")
check("HTTP-Date UTC geparst",
      rtty._parse_http_date("Wed, 09 Jul 2026 15:26:11 GMT") == (2026, 7, 9, 15, 26, 11))
check("Juli = Sommerzeit (MESZ)",  rtty._ist_sommerzeit(2026, 7, 9, 15) is True)
check("Januar = Winterzeit (MEZ)", rtty._ist_sommerzeit(2026, 1, 9, 15) is False)
check("letzter Sonntag Maerz ist Sonntag",
      rtty._wochentag_so0(2026, 3, rtty._letzter_sonntag(2026, 3)) == 0)
check("letzter Sonntag Oktober ist Sonntag",
      rtty._wochentag_so0(2026, 10, rtty._letzter_sonntag(2026, 10)) == 0)
check("Stundenaddition mit Tageswechsel",
      rtty._stunden_addieren(2026, 7, 9, 23, 26, 11, 2) == (2026, 7, 10, 1, 26, 11))

def _lokalzeit(hdr):
    y, mon, d, hh, mm, ss = rtty._parse_http_date(hdr)
    off = 2 if rtty._ist_sommerzeit(y, mon, d, hh) else 1
    return rtty._stunden_addieren(y, mon, d, hh, mm, ss, off)
check("UTC->MESZ (Sommer, +2h)", _lokalzeit("Wed, 09 Jul 2026 15:26:11 GMT") == (2026, 7, 9, 17, 26, 11))
check("UTC->MEZ (Winter, +1h)",  _lokalzeit("Fri, 09 Jan 2026 15:26:11 GMT") == (2026, 1, 9, 16, 26, 11))

# ---------------------------------------------------------------------------
print(f"\n===== ERGEBNIS: {PASS} bestanden, {FAIL} fehlgeschlagen =====")
sys.exit(1 if FAIL else 0)
