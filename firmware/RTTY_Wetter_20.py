# =====================================================================
#  RTTY_Wetter_20.py  –  Wetter-Fernschreiber (T58d) auf ESP32/MicroPython
# =====================================================================
#  Fortlaufende Nummerierung. NEU in V20 ggue. V19:
#    - UHRZEIT AUS DEN WETTERDATEN: Datum+Zeit werden aus dem HTTP-
#      "Date"-Header der wttr.in-Antwort gelesen (UTC) und auf deutsche
#      Zeit (MEZ/MESZ mit automatischer Sommerzeit) umgerechnet; damit
#      wird die ESP32-Uhr gestellt. KEIN NTP noetig.
#      -> Datum/Uhrzeit im Ausdruck und auf dem OLED sind korrekt.
#
#  Uebernommen aus V19 (Aenderungen ggue. V18):
#    - wttr.in: EIN kombinierter Request statt 10 (schont den Dienst)
#    - Socket wird IMMER geschlossen (try/finally) -> kein Leck im Dauerlauf
#    - Antwortformat/Gueltigkeit strenger geprueft (Fehlerseiten nicht drucken)
#    - Ort ASCII "Kuenzelsau" (kein Umlaut in der URL)
#    - Zeilenumbruch (_wrap_lines) Off-by-one behoben
#    - OLED-Uhr laeuft jede Sekunde, Wetter nur alle ABFRAGE_INTERVALL
#    - Druck-Schalter IMMER_DRUCKEN (nur bei Aenderung / immer)
#    - BUGFIX Windrichtung: "%d" ist wttr.in "Dusk", NICHT die Richtung
#      (die steckt in "%w"); Feld RICHTUNG entfernt.
#
#  Pins (ESP32-WROOM): Motor/Freigabe=16, TX(RTTY)=17,
#    OLED I2C SDA=21 / SCL=22, ADC=32/33/34.
# =====================================================================

import network
import time
import urequests

# Rohes Socket nur fuer den HTTP-Date-Header (Zeit-Sync). Auf dem PC
# (Emulator/Test) existiert usocket nicht -> dann bleibt socket = None.
try:
    import usocket as socket
except ImportError:
    socket = None
from machine import Pin, ADC, I2C
import ssd1306

# ---------------------------------------------------------------------------
# GLOBAL für Laufschrift
# ---------------------------------------------------------------------------

scroll_pos = 0

def oled_status(oled, wlan_ok, drucktext):
    global scroll_pos
    oled.fill(0)

    # Zeile 1: WLAN
    if wlan_ok:
        oled.text("WLAN OK", 0, 0)
    else:
        oled.text("KEIN WLAN", 0, 0)

    # Zeile 2: Datum
    now = time.localtime()
    datum = f"{now[2]:02d}.{now[1]:02d}.{now[0]}"
    oled.text(datum, 0, 16)

    # Zeile 3: Uhrzeit
    uhr = f"{now[3]:02d}:{now[4]:02d}:{now[5]:02d}"
    oled.text(uhr, 0, 26)

    # Zeile 4: Laufschrift oder BEREIT
    if drucktext:
        text = drucktext + "   "
        oled.text(text[scroll_pos:scroll_pos+16], 0, 40)
        scroll_pos = (scroll_pos + 1) % len(text)
    else:
        scroll_pos = 0
        oled.text("BEREIT", 0, 40)

    oled.show()


# ---------------------------------------------------------------------------
# WLAN EINSTELLEN
# ---------------------------------------------------------------------------

WLAN_NAME = "<WLAN-Name>"   # WLAN-Name und -Passwort eintragen
WLAN_WORT = "xxxxxxxx"

Freigabe = 16
motor = Pin(Freigabe, Pin.OUT)
motor.value(0)  # Motor zunächst AUS

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Verbinde mit WLAN...")
        wlan.connect(WLAN_NAME, WLAN_WORT)

        for _ in range(50):
            if wlan.isconnected():
                break
            time.sleep(0.2)

    if wlan.isconnected():
        print("WLAN verbunden:", wlan.ifconfig())
    else:
        raise RuntimeError("Keine WLAN-Verbindung")

    return wlan


# ---------------------------------------------------------------------------
# ZEIT AUS DEN WETTERDATEN (HTTP-"Date"-Header von wttr.in, UTC -> MEZ/MESZ)
# ---------------------------------------------------------------------------

_MONATE = {"Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6,
           "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12}

def _tage_im_monat(y, m):
    if m == 2:
        schalt = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
        return 29 if schalt else 28
    return (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[m - 1]

def _wochentag_so0(y, m, d):
    # Zellers Kongruenz -> 0=Sonntag .. 6=Samstag (reine Arithmetik)
    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    if m < 3:
        y -= 1
    return (y + y // 4 - y // 100 + y // 400 + t[m - 1] + d) % 7

def _letzter_sonntag(y, m):
    d = _tage_im_monat(y, m)
    while _wochentag_so0(y, m, d) != 0:
        d -= 1
    return d

def _ist_sommerzeit(y, mon, d, hh_utc):
    # EU-Regel: MESZ von letztem So im Maerz 01:00 UTC bis letztem So im Okt 01:00 UTC
    start = _letzter_sonntag(y, 3)
    ende  = _letzter_sonntag(y, 10)
    nach_start = (mon > 3) or (mon == 3 and (d > start or (d == start and hh_utc >= 1)))
    vor_ende   = (mon < 10) or (mon == 10 and (d < ende or (d == ende and hh_utc < 1)))
    return nach_start and vor_ende

def _stunden_addieren(y, mon, d, hh, mm, ss, off):
    # off = +1 (MEZ) oder +2 (MESZ); Datum sauber ueberrollen
    hh += off
    while hh >= 24:
        hh -= 24
        d += 1
        if d > _tage_im_monat(y, mon):
            d = 1
            mon += 1
            if mon > 12:
                mon = 1
                y += 1
    return (y, mon, d, hh, mm, ss)

def _parse_http_date(s):
    # Beispiel: "Wed, 09 Jul 2026 15:26:11 GMT"  -> (Y, M, D, hh, mm, ss) in UTC
    try:
        p = s.split()
        d   = int(p[1])
        mon = _MONATE[p[2]]
        y   = int(p[3])
        hh, mm, ss = [int(x) for x in p[4].split(":")]
        return (y, mon, d, hh, mm, ss)
    except Exception:
        return None

def _http_date_header(host="wttr.in", path="/"):
    if socket is None:
        return None
    s = socket.socket()
    data = b""
    try:
        s.settimeout(10)
        ai = socket.getaddrinfo(host, 80)[0][-1]
        s.connect(ai)
        req = ("GET %s HTTP/1.0\r\nHost: %s\r\n"
               "User-Agent: curl\r\nConnection: close\r\n\r\n" % (path, host))
        s.send(req.encode())
        while b"\r\n\r\n" not in data and len(data) < 1500:
            chunk = s.recv(128)
            if not chunk:
                break
            data += chunk
    except Exception as e:
        print("Zeit-Header Fehler:", e)
        return None
    finally:
        try:
            s.close()
        except Exception:
            pass
    for line in data.split(b"\r\n"):
        if line[:5].lower() == b"date:":
            try:
                return line[5:].strip().decode()
            except Exception:
                return None
    return None

def sync_time_from_weather():
    """Holt Datum/Uhrzeit aus dem wttr.in HTTP-Date-Header und stellt die RTC.
    Rueckgabe True bei Erfolg."""
    hdr = _http_date_header()
    if not hdr:
        return False
    utc = _parse_http_date(hdr)
    if not utc:
        return False
    y, mon, d, hh, mm, ss = utc
    off = 2 if _ist_sommerzeit(y, mon, d, hh) else 1
    ly, lmon, ld, lhh, lmm, lss = _stunden_addieren(y, mon, d, hh, mm, ss, off)
    try:
        from machine import RTC
        # (Jahr, Monat, Tag, Wochentag, Std, Min, Sek, Subsek)
        RTC().datetime((ly, lmon, ld, 0, lhh, lmm, lss, 0))
        return True
    except Exception as e:
        print("RTC stellen fehlgeschlagen:", e)
        return False


# ---------------------------------------------------------------------------
# ITA2-Code-Tabellen (UNVERÄNDERT)
# ---------------------------------------------------------------------------

_BAUDOT_LETTERS = {
    'A':'00011','B':'11001','C':'01110','D':'01001','E':'00001',
    'F':'01101','G':'11010','H':'10100','I':'00110','J':'01011',
    'K':'01111','L':'10010','M':'11100','N':'01100','O':'11000',
    'P':'10110','Q':'10111','R':'01010','S':'00101','T':'10000',
    'U':'00111','V':'11110','W':'10011','X':'11101','Y':'10101',
    'Z':'10001',' ':'00100'
}

_BAUDOT_FIGURES = {
    '3':'00001','-':'00011',"'" :'00101','8':'00110','7':'00111',
    '$':'01001','4':'01010','\a':'01011',',':'01100','!':'01101',
    ':':'01110','(':'01111','5':'10000','+':'10001',')':'10010',
    '2':'10011','#':'10100','6':'10101','0':'10110','1':'10111',
    '9':'11000','?':'11001','&':'11010','.':'11100','/':'11101',
    ';':'11110',' ':'00100'
}

TRANSLITERATION = {
    'Ä':'AE','Ö':'OE','Ü':'UE','ä':'ae','ö':'oe','ü':'ue','ß':'ss',
    'À':'A','Á':'A','Â':'A','Ã':'A','È':'E','É':'E','Ê':'E','Ë':'E',
    'Ì':'I','Í':'I','Î':'I','Ï':'I','Ò':'O','Ó':'O','Ô':'O','Õ':'O',
    'Ù':'U','Ú':'U','Û':'U','Ç':'C','Ñ':'N',
    'à':'a','á':'a','â':'a','ã':'a','è':'e','é':'e','ê':'e','ë':'e',
    'ì':'i','í':'i','î':'i','ï':'i','ò':'o','ó':'o','ô':'o','õ':'o',
    'ù':'u','ú':'u','û':'u','ç':'c','ñ':'n',
    '–':'-','—':'-','…':'...','°':' GRAD ','@':'(AT)','%':' PROZ ',
    '*':'X','=':'-','<':'(','>':')','[':'(',']':')','{':'(','}':')',
    '_':'-','^':"'",'~':'-','\\':'/','|':'/','\t':'    ','\n':'\r\n'
}

_CODE_LTRS = '11111'
_CODE_FIGS = '11011'
_CODE_CR   = '01000'
_CODE_LF   = '00010'

T68D_LINE_LENGTH = 69

# 6 Stunden in Sekunden
KOMPLETT_INTERVALL = 6 * 3600

# Wetter-Abfrageintervall in Sekunden (wttr.in nicht ueberlasten!)
ABFRAGE_INTERVALL = 2 * 60   # alle 2 Minuten

# Drucken:
#   True  = bei JEDER gueltigen Abfrage drucken (auch wenn nichts anders ist)
#   False = nur wenn sich Werte geaendert haben (empfohlen, spart Papier)
IMMER_DRUCKEN = False


# ---------------------------------------------------------------------------
# T68dSender – Version 4 (UNVERÄNDERT)
# ---------------------------------------------------------------------------

class T68dSender:

    BAUD_RATE = 50
    BIT_TIME  = 1 / BAUD_RATE
    STOP_TIME = BIT_TIME * 1.5

    def __init__(self, tx_pin=17, adc_pins=[32,33,34]):

        self._tx   = Pin(tx_pin, Pin.OUT, value=1)
        self._mode = 'LTRS'

        # ADC-Kanäle initialisieren
        self._adcs = []
        for p in adc_pins:
            adc = ADC(Pin(p))
            adc.atten(ADC.ATTN_11DB)
            adc.width(ADC.WIDTH_12BIT)
            self._adcs.append(adc)

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def sync(self, duration=0.5):
        self._tx.value(1)
        time.sleep(duration)

    def send_text(self, text):

        # 1. Makros ersetzen
        text = self._expand_shortcodes(text)

        # 2. ADC-Kanäle ersetzen
        text = self._expand_adc(text)

        # 3. Transliteration
        expanded = self._expand(text)

        # 4. Soft-Wrap
        wrapped = self._wrap_lines(expanded)

        # 5. Senden
        for ch in wrapped:
            if ch == '\n':
                self.send_crlf()
            else:
                self._send_char(ch)

    def send_line(self, text):
        self.send_text(text)
        self.send_crlf()

    def send_crlf(self):
        self._send_frame(_CODE_CR)
        self._send_frame(_CODE_LF)

    def reset_shift(self):
        self._send_frame(_CODE_LTRS)
        self._send_frame(_CODE_LTRS)
        self._mode = 'LTRS'

    # ------------------------------------------------------------------
    # Kurzbefehle: DATUM, ZEIT
    # ------------------------------------------------------------------

    def _expand_shortcodes(self, text):
        now = time.localtime()
        repl = {
            "DATUM": f"{now[2]:02d}.{now[1]:02d}.{now[0]}",
            "ZEIT":  f"{now[3]:02d}:{now[4]:02d}:{now[5]:02d}",
        }
        for k,v in repl.items():
            text = text.replace(k, v)
        return text

    # ------------------------------------------------------------------
    # ADC-Kanäle
    # ------------------------------------------------------------------

    def _expand_adc(self, text):
        for i, adc in enumerate(self._adcs, start=1):
            key = f"KANAL{i}"
            if key in text:
                raw = adc.read()
                volt = raw * 3.3 / 4095
                text = text.replace(key, f"{volt:.2f}")
        return text

    # ------------------------------------------------------------------
    # Soft-Wrap
    # ------------------------------------------------------------------

    def _wrap_lines(self, text):
        lines = []
        for paragraph in text.split('\n'):
            current = []
            length = 0
            for word in paragraph.split(' '):
                sep = 1 if current else 0
                if length + len(word) + sep > T68D_LINE_LENGTH:
                    lines.append(' '.join(current))
                    current = [word]
                    length = len(word)
                else:
                    current.append(word)
                    length += len(word) + sep
            lines.append(' '.join(current))
        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # Transliteration
    # ------------------------------------------------------------------

    def _expand(self, text):
        result = []
        for ch in text:
            upper = ch.upper()

            if upper in _BAUDOT_LETTERS or upper in _BAUDOT_FIGURES:
                result.append(ch)
                continue

            if ch in TRANSLITERATION:
                result.append(TRANSLITERATION[ch])
                continue

            if upper in TRANSLITERATION:
                result.append(TRANSLITERATION[upper])
                continue

            print(f"[Warnung] Zeichen {ch!r} nicht darstellbar")
            result.append('[?]')

        return ''.join(result)

    # ------------------------------------------------------------------
    # ITA2-Senden
    # ------------------------------------------------------------------

    def _send_char(self, ch):
        upper = ch.upper()

        if upper in _BAUDOT_LETTERS:
            self._shift_to('LTRS')
            self._send_frame(_BAUDOT_LETTERS[upper])

        elif upper in _BAUDOT_FIGURES:
            self._shift_to('FIGS')
            self._send_frame(_BAUDOT_FIGURES[upper])

    def _shift_to(self, mode):
        if mode == self._mode:
            return
        code = _CODE_LTRS if mode == 'LTRS' else _CODE_FIGS
        self._send_frame(code)
        self._mode = mode

    def _send_frame(self, bits):
        self._tx.value(0)
        time.sleep(self.BIT_TIME)

        for i in range(4, -1, -1):
            self._tx.value(int(bits[i]))
            time.sleep(self.BIT_TIME)

        self._tx.value(1)
        time.sleep(self.STOP_TIME)


# ---------------------------------------------------------------------------
# Unicode → ASCII für T68d
# ---------------------------------------------------------------------------

def sanitize_weather_text(text):
    arrows = {
        "↗": "NO", "↘": "SO", "↙": "SW", "↖": "NW",
        "↑": "N",  "↓": "S",  "→": "O",  "←": "W"
    }
    for k, v in arrows.items():
        text = text.replace(k, v)

    moons = {
        "🌑": "NEUMOND",   "🌒": "ZUNEHMEND", "🌓": "1.VIERTEL",
        "🌔": "ZUNEHMEND", "🌕": "VOLLMOND",   "🌖": "ABNEHMEND",
        "🌗": "LETZTES V.","🌘": "ABNEHMEND"
    }
    for k, v in moons.items():
        text = text.replace(k, v)

    return text


# ---------------------------------------------------------------------------
# Wetterdaten abrufen  (EIN Request statt 10 -> schont wttr.in)
# ---------------------------------------------------------------------------

# Reihenfolge MUSS zu WEATHER_FORMAT passen!
# Hinweis: KEIN "%d" (das ist wttr.in "Dusk", nicht die Windrichtung).
#          Die Windrichtung steckt bereits im Windfeld "%w".
WEATHER_FIELDS = ["TEMP", "GEFUEHLT", "FEUCHTE", "DRUCK", "WIND",
                  "WETTER", "AUFGANG", "UNTERGANG", "MOND"]
WEATHER_FORMAT = "%t|%f|%h|%P|%w|%C|%S|%s|%m"

def get_weather_all():
    # Alle Felder in EINEM Request, per '|' getrennt; Ort ASCII (ohne Umlaut)
    url = "http://wttr.in/Kuenzelsau?format=" + WEATHER_FORMAT

    r = None
    try:
        r = urequests.get(url)
        text = r.text.strip()
    except Exception as e:
        # Netzwerkfehler -> alle Felder als Fehler markieren
        return {key: f"ERR {e}" for key in WEATHER_FIELDS}
    finally:
        if r is not None:
            r.close()   # Socket IMMER schliessen (auch bei Fehler)

    parts = text.split("|")
    if len(parts) != len(WEATHER_FIELDS):
        # Antwort passt nicht zum erwarteten Format -> ungueltig behandeln
        return {key: "ERR format" for key in WEATHER_FIELDS}

    return {key: val.strip() for key, val in zip(WEATHER_FIELDS, parts)}


# ---------------------------------------------------------------------------
# Gültigkeitsprüfung
# ---------------------------------------------------------------------------

def is_value_valid(v):
    if not v:
        return False
    if v.startswith("ERR"):
        return False
    low = v.lower()
    for bad in ("not available", "unknown location", "sorry", "we were unable"):
        if bad in low:
            return False
    return True

def is_valid(data):
    return any(is_value_valid(v) for v in data.values())

def has_changed(new_data, previous_data):
    changed_keys = []
    for key, new_val in new_data.items():
        if not is_value_valid(new_val):
            continue
        prev_val = previous_data.get(key)
        if prev_val is None or new_val != prev_val:
            changed_keys.append(key)
    return len(changed_keys) > 0, changed_keys


# ---------------------------------------------------------------------------
# Druckhilfen
# ---------------------------------------------------------------------------

FIELD_LABELS = {
    "TEMP":      "TEMP",
    "GEFUEHLT":  "GEFUEHLT",
    "FEUCHTE":   "FEUCHTE",
    "DRUCK":     "DRUCK",
    "WIND":      "WIND",
    "WETTER":    "WETTER",
    "AUFGANG":   "SONNENAUFGANG",
    "UNTERGANG": "SONNENUNTERGANG",
    "MOND":      "MONDPHASE"
}

def print_header(sender):
    for _ in range(4):
        sender._send_frame(_CODE_CR)
    for _ in range(4):
        sender._send_frame(_CODE_LF)
    for _ in range(4):
        sender._send_frame(_CODE_LTRS)
    sender._mode = 'LTRS'

def print_footer(sender):
    sender.send_line("")
    sender.send_line("RYRYRYRYRY")
    sender.send_line("55 73 AR SK")


# ---------------------------------------------------------------------------
# Druckfunktionen
# ---------------------------------------------------------------------------

def send_komplett(sender, w):
    print("[DRUCK] Komplett-Datensatz")
    motor.value(1)
    time.sleep(2)

    print_header(sender)

    sender.send_line("WETTER KUENZELSAU AM DATUM UM ZEIT")
    sender.send_line("")

    sender.send_line(f"TEMP: {sanitize_weather_text(w['TEMP'])}")
    sender.send_line(f"GEFUEHLT: {sanitize_weather_text(w['GEFUEHLT'])}")
    sender.send_line(f"FEUCHTE: {sanitize_weather_text(w['FEUCHTE'])}")
    sender.send_line(f"DRUCK: {sanitize_weather_text(w['DRUCK'])}")
    sender.send_line(f"WIND: {sanitize_weather_text(w['WIND'])}")
    sender.send_line(f"WETTER: {sanitize_weather_text(w['WETTER'])}")
    sender.send_line(f"SONNENAUFGANG: {sanitize_weather_text(w['AUFGANG'])}")
    sender.send_line(f"SONNENUNTERGANG: {sanitize_weather_text(w['UNTERGANG'])}")
    sender.send_line(f"MONDPHASE: {sanitize_weather_text(w['MOND'])}")

    print_footer(sender)

    time.sleep(5)
    motor.value(0)


def send_aenderung(sender, w, changed_keys):
    print(f"[DRUCK] Aenderungsdruck: {', '.join(changed_keys)}")
    motor.value(1)
    time.sleep(2)

    print_header(sender)

    sender.send_line("ZEIT")
    sender.send_line("")

    for key in FIELD_LABELS:
        if key not in changed_keys:
            continue
        label = FIELD_LABELS[key]
        val = sanitize_weather_text(w[key])
        sender.send_line(f"{label}: {val}")

    print_footer(sender)

    time.sleep(5)
    motor.value(0)


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main():

    # OLED initialisieren
    i2c = I2C(0, scl=Pin(22), sda=Pin(21))
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)

    oled.fill(0)
    oled.text("T68d Wetterstation", 0, 0)
    oled.text("Verbinde WLAN...", 0, 16)
    oled.show()

    wlan = connect_wifi()

    # Uhrzeit direkt aus den Wetterdaten (wttr.in HTTP-Date-Header) holen
    print("Synchronisiere Uhrzeit ueber wttr.in ...")
    if sync_time_from_weather():
        print("Zeit gesetzt:", time.localtime())
    else:
        print("Zeitsync fehlgeschlagen – interne Uhr wird verwendet.")

    oled.fill(0)
    oled.text("WLAN OK", 0, 0)
    ip = wlan.ifconfig()[0]
    oled.text("IP:", 0, 16)
    oled.text(ip, 0, 26)
    oled.text("Starte System...", 0, 46)
    oled.show()
    time.sleep(2)

    sender = T68dSender(tx_pin=17, adc_pins=[32,33,34])

    print("Synchronisiere mit T68d ...")
    sender.sync(1.0)
    print("Bereit.\n")

    previous_data = None
    letzter_komplett = None  # Zeitpunkt des letzten Komplett-Drucks
    letzter_abruf   = None   # Zeitpunkt der letzten Wetterabfrage
    letzter_zeitsync = time.time()  # Zeitpunkt der letzten Uhr-Synchronisation

    while True:
        jetzt = time.time()

        # OLED laeuft jede Sekunde weiter (Uhr + Laufschrift)
        oled_status(oled, wlan.isconnected(), None)

        # Wetter nur alle ABFRAGE_INTERVALL Sekunden holen (wttr.in schonen)
        if letzter_abruf is not None and (jetzt - letzter_abruf) < ABFRAGE_INTERVALL:
            time.sleep(1)
            continue
        letzter_abruf = jetzt

        # Uhr etwa stuendlich aus den Wetterdaten nachziehen
        if (jetzt - letzter_zeitsync) >= 3600:
            if sync_time_from_weather():
                letzter_zeitsync = jetzt

        w = get_weather_all()

        # Debug-Ausgabe
        print("\n--- WETTERDATEN (DEBUG) ---")
        now = time.localtime()
        print(f"Datum: {now[2]:02d}.{now[1]:02d}.{now[0]}")
        print(f"Uhrzeit: {now[3]:02d}:{now[4]:02d}:{now[5]:02d}")
        for key, value in w.items():
            print(f"  {key}: {value}")

        gueltig = is_valid(w)
        print(f"Datensatz gueltig: {gueltig}")

        if not gueltig:
            print("Status: Datensatz ungueltig – kein Druck.")
            print("---------------------------\n")
            time.sleep(1)
            continue

        if previous_data is None:
            # Erster gültiger Datensatz -> immer Komplett-Druck
            print("Status: Erster gueltiger Datensatz – Komplett-Druck.")
            oled_status(oled, wlan.isconnected(), "Komplettdruck")
            send_komplett(sender, w)
            oled_status(oled, wlan.isconnected(), None)
            previous_data   = {k: v for k, v in w.items() if is_value_valid(v)}
            letzter_komplett = jetzt

        else:
            geaendert, changed_keys = has_changed(w, previous_data)
            print(f"Aenderung erkannt: {geaendert}  {changed_keys if geaendert else ''}")

            komplett_faellig = (letzter_komplett is None or
                                (jetzt - letzter_komplett) >= KOMPLETT_INTERVALL)

            if komplett_faellig:
                # 6-Stunden-Komplett-Druck (unabhaengig von Aenderung)
                print("Status: 6-Stunden-Intervall – Komplett-Druck.")
                oled_status(oled, wlan.isconnected(), "Komplettdruck")
                send_komplett(sender, w)
                oled_status(oled, wlan.isconnected(), None)
                letzter_komplett = jetzt

            elif geaendert:
                # Neue/aktuelle Werte -> Aenderungsdruck
                print("Status: Aenderungsdruck.")
                oled_status(oled, wlan.isconnected(), ", ".join(changed_keys))
                send_aenderung(sender, w, changed_keys)
                oled_status(oled, wlan.isconnected(), None)

            elif IMMER_DRUCKEN:
                # Nichts geaendert, aber es soll trotzdem gedruckt werden
                print("Status: Immer-Druck (keine Aenderung).")
                oled_status(oled, wlan.isconnected(), "Druck")
                send_komplett(sender, w)
                oled_status(oled, wlan.isconnected(), None)

            else:
                print("Status: Kein Druck (keine Aenderung).")

            # Vergleichsdatensatz aktualisieren (nur gültige Werte)
            for k, v in w.items():
                if is_value_valid(v):
                    previous_data[k] = v

        print("---------------------------\n")
        time.sleep(1)   # 1-Sekunden-Takt; Wetterintervall wird oben geprueft


if __name__ == "__main__":
    main()
