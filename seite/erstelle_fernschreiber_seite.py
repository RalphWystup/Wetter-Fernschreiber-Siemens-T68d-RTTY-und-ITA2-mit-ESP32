#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""erstelle_fernschreiber_seite.py — die Seite „Wetter-Fernschreiber" (Fassung aus VERSION):
eine einzige HTML mit Simulation und eingebauter Dokumentation, eigenstaendig und ohne Netz.

  * Umsetzung eines eingegebenen Textes nach ITA2 — Transliteration, Zeilenumbruch auf die
    Streifenbreite, Umschaltung zwischen Buchstaben- und Ziffernebene, die Fuenf-Bit-Muster.
    Die Tabellen kommen unveraendert aus RTTY_Wetter_20.py (sie werden hier eingelesen, nicht
    abgeschrieben); der Ablauf ist Zeile fuer Zeile derselbe wie in send_text().
  * Das Sende-Frame: Ruhe, Startbit, fuenf Datenbits, 1,5 Bit Stopp bei 50 Baud, mit den Bitzeiten
    als Zahlen und einem mitlaufenden Zeitdiagramm des GPIO-Pegels.
  * Ein gezeichneter Siemens T68d Streifenschreiber, der auf einen fortlaufenden Papierstreifen
    druckt — im Takt der echten Bitzeiten, mit Motorfreigabe; Wagenruecklauf und Zeilenvorschub
    erscheinen als Zeichen auf dem Streifen, wie es das Druckbild des Geraets zeigt.
  * Ein gespeicherter Beispiel-Abruf von wttr.in (kein Netzzugriff) wird aufbereitet und gedruckt
    wie am Geraet, mit Kopf und Nachspann.
  * Das OLED (128 x 64) mit demselben Aufbau wie oled_status().
  * Dokumentation: das Manuskript als Reiter; dazu das Video und die drei Fotos vom Geraet.

Aufruf: python3 Seite/erstelle_fernschreiber_seite.py   -> Seite/Fernschreiber_<VERSION>.html
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import types
from pathlib import Path

H = Path(__file__).resolve().parent
P = H.parent                      # /workspace/Fernschreiber
A = P.parent                      # /workspace  (dort liegen Firmware, Manuskript und Bilder)
VERSION = (H / "VERSION").read_text(encoding="utf-8").strip()
DATUM = "29.09.2026"
NAMENSNENNUNG = "Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)"
ZIEL = H / f"Fernschreiber_{VERSION}.html"

MANUSKRIPT = A / "MANUSKRIPT_Fernschreiber.md"
FIRMWARE = A / "RTTY_Wetter_20.py"
VIDEO = P / "Video_Fernschreiber_druckt.mp4"
BILDER = [
    (A / "signal-2026-07-09-163350_002.jpeg",
     "Die Maschine: ein Siemens T68d Streifenschreiber. Auf der Wählscheibe steht das "
     "Amateurfunk-Rufzeichen DB3SU, das auch im Nachspann jedes Ausdrucks wiederkehrt. Oben links "
     "hängt die Steuerbox mit dem ESP32."),
    (A / "signal-2026-07-09-163350.jpeg",
     "Die Steuerelektronik: ein ESP32 auf einer Erweiterungsplatine in einem Gehäuse mit "
     "Kabelverschraubungen. Herausgeführt sind die Sendeleitung (GPIO 17), die Motorfreigabe "
     "(GPIO 16) und der I2C-Bus zum OLED (SDA 21 / SCL 22)."),
    (A / "Druckbild_T68D_Wetter.jpeg",
     "Das Druckbild des Geräts: drei Streifen eines Komplettdrucks vom 10.07.2026. Am Anfang "
     "stehen vier „&lt;“ und vier „≡“ — das sind die vier Wagenrückläufe und vier Zeilenvorschübe "
     "aus print_header(); der Streifenschreiber hat keinen Wagen und druckt beide als Zeichen."),
]

# --- Neutralisierung: eine Regel je Ersetzung, nur in den Kopien (Arbeitsbereich bleibt unveraendert).
# Die Attrappen in Emulator und Testsuite tragen erfundene Adressen; ein Textpruefer kann eine
# erfundene nicht von einer echten unterscheiden, also gehen auch sie als Platzhalter hinaus.
NEUTRAL = [
    (r"192\.168\.0\.42", "<IP-des-ESP32>"),
    (r"192\.168\.0\.2\b", "<IP-des-ESP32>"),
    (r"192\.168\.0\.1\b", "<IP-des-Routers>"),
    (r"8\.8\.8\.8", "<IP-des-Namensdienstes>"),
    (r"255\.255\.255\.0", "<Netzmaske>"),
]
# Netzname und Kennwortwert des Aufbaus stehen nur in neutral_privat.json (nicht in der Ausfuhr),
# damit sie nicht im veroeffentlichten Erzeuger selbst stehen; fehlt die Datei, gelten nur die Regeln oben.
if (H / "neutral_privat.json").is_file():
    NEUTRAL += [(re.escape(m), e) for m, e in json.loads((H / "neutral_privat.json").read_text(encoding="utf-8"))]


def neutral(text: str) -> str:
    for m, e in NEUTRAL:
        text = re.sub(m, e, text)
    return text


def daten_uri(pfad: Path) -> str:
    typ = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "mp4": "video/mp4"}[pfad.suffix.lower().lstrip(".")]
    return f"data:{typ};base64," + base64.b64encode(pfad.read_bytes()).decode()


# ---------------------------------------------------------------------------------------------
# Die Tabellen kommen aus der Firmware selbst — abgeschrieben wird nichts.
# ---------------------------------------------------------------------------------------------
def firmware_laden():
    """RTTY_Wetter_20.py mit MicroPython-Attrappen laden (wie nachrechnung_ita2.py)."""
    for name, bauen in (("machine", _machine), ("network", _network), ("urequests", _urequests), ("ssd1306", _ssd1306)):
        sys.modules[name] = bauen()
    sys.path.insert(0, str(FIRMWARE.parent))
    import RTTY_Wetter_20 as rtty
    return rtty


def _machine():
    m = types.ModuleType("machine")

    class Pin:
        OUT = 1
        IN = 0

        def __init__(self, id, mode=None, value=None):
            self.id, self._v = id, 0 if value is None else value

        def value(self, v=None):
            if v is None:
                return self._v
            self._v = v

    class ADC:
        ATTN_11DB = 3
        WIDTH_12BIT = 3

        def __init__(self, pin):
            pass

        def atten(self, a):
            pass

        def width(self, w):
            pass

        def read(self):
            return 2048

    class I2C:
        def __init__(self, *a, **k):
            pass

    m.Pin, m.ADC, m.I2C = Pin, ADC, I2C
    return m


def _network():
    m = types.ModuleType("network")

    class WLAN:
        STA_IF = 0

        def __init__(self, *a):
            pass

        def active(self, *a):
            pass

        def isconnected(self):
            return True

        def connect(self, *a):
            pass

        def ifconfig(self):
            return ("<IP-des-ESP32>",) * 4

    m.WLAN, m.STA_IF = WLAN, 0
    return m


def _urequests():
    m = types.ModuleType("urequests")

    class _Resp:
        def __init__(self, text):
            self.text = text

        def close(self):
            pass

    m.get, m._Resp = (lambda url, **k: _Resp("")), _Resp
    return m


def _ssd1306():
    m = types.ModuleType("ssd1306")

    class SSD1306_I2C:
        def __init__(self, *a, **k):
            pass

        def fill(self, *a):
            pass

        def text(self, *a):
            pass

        def show(self, *a):
            pass

    m.SSD1306_I2C = SSD1306_I2C
    return m


RTTY = firmware_laden()

# Ein gespeicherter Abruf — die Werte des Komplettdrucks vom 10.07.2026, den das Foto
# Druckbild_T68D_Wetter.jpeg zeigt. Kein Netzzugriff in der Seite.
WETTER_ROH = "+28°C|+28°C|30%|1016hPa|↙12km/h|Sunny|05:26:34|21:26:10|🌘"
WETTER_ZEIT = ("10.07.2026", "16:55:09")

FIRMWARE_DATEN = {
    "letters": RTTY._BAUDOT_LETTERS,
    "figures": RTTY._BAUDOT_FIGURES,
    "translit": RTTY.TRANSLITERATION,
    "CODE_LTRS": RTTY._CODE_LTRS,
    "CODE_FIGS": RTTY._CODE_FIGS,
    "CODE_CR": RTTY._CODE_CR,
    "CODE_LF": RTTY._CODE_LF,
    "zeilenlaenge": RTTY.T68D_LINE_LENGTH,
    "baud": RTTY.T68dSender.BAUD_RATE,
    "bit_us": round(RTTY.T68dSender.BIT_TIME * 1e6),
    "stop_us": round(RTTY.T68dSender.STOP_TIME * 1e6),
    "pfeile": {"↗": "NO", "↘": "SO", "↙": "SW", "↖": "NW", "↑": "N", "↓": "S", "→": "O", "←": "W"},
    "monde": {"🌑": "NEUMOND", "🌒": "ZUNEHMEND", "🌓": "1.VIERTEL", "🌔": "ZUNEHMEND",
              "🌕": "VOLLMOND", "🌖": "ABNEHMEND", "🌗": "LETZTES V.", "🌘": "ABNEHMEND"},
    "felder": RTTY.WEATHER_FIELDS,
    "format": RTTY.WEATHER_FORMAT,
    "labels": RTTY.FIELD_LABELS,
    "wetter_roh": WETTER_ROH,
    "wetter_datum": WETTER_ZEIT[0],
    "wetter_uhr": WETTER_ZEIT[1],
    "wetter_ort": "Kuenzelsau",
}


def dokument_html(pfad: Path) -> str:
    md = neutral(pfad.read_text(encoding="utf-8"))
    kopf = re.match(r"---\n(.*?)\n---\n", md, re.S)
    md = md[kopf.end():] if kopf else md
    # Bildverweise auf Dateien im Arbeitsbereich: in der Seite stehen die Bilder ohnehin eigens,
    # in der eingebetteten Dokumentation werden sie durch ihre Unterschrift ersetzt.
    md = re.sub(r"!\[(.*?)\]\((?!data:)[^)]*\)(\{[^}]*\})?", r"*(Bild: \1)*", md, flags=re.S)
    return subprocess.run(["pandoc", "-f", "markdown", "-t", "html", "--mathml"],
                          input=md, capture_output=True, text=True, check=True).stdout


SEITE_JS = r"""
// =============================================================================================
//  Die ITA2-Umsetzung — Zeile fuer Zeile aus RTTY_Wetter_20.py (die Tabellen sind aus der
//  Firmware eingelesen und stehen in FW, nicht abgeschrieben).
// =============================================================================================
const $ = id => document.getElementById(id);
const LETTERS = FW.letters, FIGURES = FW.figures, TRANSLIT = FW.translit;
const CODE_LTRS = FW.CODE_LTRS, CODE_FIGS = FW.CODE_FIGS, CODE_CR = FW.CODE_CR, CODE_LF = FW.CODE_LF;
const ZEILENLAENGE = FW.zeilenlaenge, BAUD = FW.baud, BIT_US = FW.bit_us, STOP_US = FW.stop_us;
const ZEICHEN_US = 6 * BIT_US + STOP_US;                 // Start + 5 Daten + 1,5 Stopp

// _expand(text) aus T68dSender: sendbare Zeichen bleiben, sonst Transliteration, sonst [?]
function expand(text) {
  const raus = [];
  for (const ch of text) {
    const gross = ch.toUpperCase();
    if (gross in LETTERS || gross in FIGURES) { raus.push(ch); continue; }
    if (ch in TRANSLIT) { raus.push(TRANSLIT[ch]); continue; }
    if (gross in TRANSLIT) { raus.push(TRANSLIT[gross]); continue; }
    raus.push('[?]');
  }
  return raus.join('');
}

// _wrap_lines(text): weicher Umbruch auf die Streifenbreite ZEILENLAENGE
function wrapLines(text) {
  const zeilen = [];
  for (const absatz of text.split('\n')) {
    let aktuell = [], laenge = 0;
    for (const wort of absatz.split(' ')) {
      const trenn = aktuell.length ? 1 : 0;
      if (laenge + wort.length + trenn > ZEILENLAENGE) { zeilen.push(aktuell.join(' ')); aktuell = [wort]; laenge = wort.length; }
      else { aktuell.push(wort); laenge += wort.length + trenn; }
    }
    zeilen.push(aktuell.join(' '));
  }
  return zeilen.join('\n');
}

// send_text(): Zeichen fuer Zeichen; _send_char schaltet ueber _shift_to die Ebene, wenn noetig.
// Ergebnis ist die Liste der Rahmen, die auf die Leitung gehen.
function rahmen(text) {
  const erweitert = expand(text), umbrochen = wrapLines(erweitert), liste = [];
  let ebene = 'LTRS';
  for (const ch of umbrochen) {
    if (ch === '\n') { liste.push({ art: 'CR', zeichen: '<', code: CODE_CR }); liste.push({ art: 'LF', zeichen: '≡', code: CODE_LF }); continue; }
    const gross = ch.toUpperCase();
    if (gross in LETTERS) {
      if (ebene !== 'LTRS') { liste.push({ art: 'LTRS', zeichen: '', code: CODE_LTRS }); ebene = 'LTRS'; }
      liste.push({ art: 'Zeichen', zeichen: gross, code: LETTERS[gross] });
    } else if (gross in FIGURES) {
      if (ebene !== 'FIGS') { liste.push({ art: 'FIGS', zeichen: '', code: CODE_FIGS }); ebene = 'FIGS'; }
      liste.push({ art: 'Zeichen', zeichen: gross, code: FIGURES[gross] });
    }
    // Zeichen ohne Code (das \r aus der Transliteration von \n) erzeugen keinen Rahmen
  }
  return { erweitert, wrapped: umbrochen, rahmen: liste, anzahl: liste.length, dauer_s: +(liste.length * ZEICHEN_US / 1e6).toFixed(3) };
}

// print_header(): 4x CR, 4x LF, 4x LTRS — der definierte Anfang jedes Ausdrucks
function kopfRahmen() {
  const l = [];
  for (let k = 0; k < 4; k++) l.push({ art: 'CR', zeichen: '<', code: CODE_CR });
  for (let k = 0; k < 4; k++) l.push({ art: 'LF', zeichen: '≡', code: CODE_LF });
  for (let k = 0; k < 4; k++) l.push({ art: 'LTRS', zeichen: '', code: CODE_LTRS });
  return l;
}

// sanitize_weather_text(): Windpfeile und Mondzeichen in fernschreibertaugliche Kuerzel
function sanitize(text) {
  for (const k in FW.pfeile) text = text.split(k).join(FW.pfeile[k]);
  for (const k in FW.monde) text = text.split(k).join(FW.monde[k]);
  return text;
}

// get_weather_all(): der gespeicherte Abruf wird genau wie die Antwort von wttr.in zerlegt
function wetterFelder() {
  const teile = FW.wetter_roh.split('|');
  const w = {};
  if (teile.length !== FW.felder.length) { FW.felder.forEach(k => w[k] = 'ERR format'); return w; }
  FW.felder.forEach((k, i) => w[k] = teile[i].trim());
  return w;
}

// send_komplett(): derselbe Aufbau wie in der Firmware, mit DATUM und ZEIT aus dem Abruf
function wetterText() {
  const w = wetterFelder(), z = [`WETTER ${FW.wetter_ort.toUpperCase()} AM ${FW.wetter_datum} UM ${FW.wetter_uhr}`, ''];
  for (const k in FW.labels) z.push(`${FW.labels[k]}: ${sanitize(w[k])}`);
  z.push('', 'RYRYRYRYRY', '55 73 AR SK');
  return z.join('\n');
}

// get_weather_all() im Browser: derselbe Dienst, dieselbe Formatzeile, dieselbe Zerlegung wie in der
// Firmware. Die Uhr kommt wie am Geraet aus dem Date-Kopf der Antwort (bei CORS ist er lesbar) und wird
// mit derselben Regel auf MEZ/MESZ gerechnet: Sommerzeit vom letzten Sonntag im Maerz bis zum letzten
// im Oktober. Schlaegt der Abruf fehl, bleibt der gespeicherte Abruf stehen — die Seite laeuft ohne Netz.
function _letzterSonntag(jahr, monat) {          // wie _letzter_sonntag() in der Firmware
  const tage = new Date(Date.UTC(jahr, monat, 0)).getUTCDate();
  for (let d = tage; d > 0; d--) if (new Date(Date.UTC(jahr, monat - 1, d)).getUTCDay() === 0) return d;
  return tage;
}
function _istSommerzeit(u) {                      // u = Date in UTC
  const j = u.getUTCFullYear(), m = u.getUTCMonth() + 1, d = u.getUTCDate(), h = u.getUTCHours();
  if (m < 3 || m > 10) return false;
  if (m > 3 && m < 10) return true;
  if (m === 3) { const s = _letzterSonntag(j, 3); return d > s || (d === s && h >= 1); }
  const s = _letzterSonntag(j, 10); return d < s || (d === s && h < 1);
}
function _zweistellig(n) { return String(n).padStart(2, '0'); }

// WMO-Wetterschluessel in die kurzen englischen Woerter, die auch wttr.in druckt (%C).
const _WMO = {0:'Clear', 1:'Mainly clear', 2:'Partly cloudy', 3:'Overcast', 45:'Fog', 48:'Rime fog',
  51:'Light drizzle', 53:'Drizzle', 55:'Heavy drizzle', 56:'Freezing drizzle', 57:'Freezing drizzle',
  61:'Light rain', 63:'Rain', 65:'Heavy rain', 66:'Freezing rain', 67:'Freezing rain',
  71:'Light snow', 73:'Snow', 75:'Heavy snow', 77:'Snow grains', 80:'Light showers', 81:'Showers',
  82:'Heavy showers', 85:'Snow showers', 86:'Snow showers', 95:'Thunderstorm', 96:'Thunderstorm',
  99:'Thunderstorm'};
// Der Pfeil zeigt die Himmelsrichtung, aus der es weht; die Firmware macht daraus in sanitize() NO, SO, ...
const _PFEIL = ['↑','↗','→','↘','↓','↙','←','↖'];
// Mondphase aus dem Alter seit einem bekannten Neumond (6.1.2000 18:14 UTC), synodischer Monat 29,530588853 d.
function _mond(datum) {
  const alter = (((datum.getTime() - Date.UTC(2000, 0, 6, 18, 14)) / 86400000) % 29.530588853 + 29.530588853) % 29.530588853;
  return ['🌑','🌒','🌓','🌔','🌕','🌖','🌗','🌘'][Math.floor(alter / 29.530588853 * 8) % 8];
}
function _vz(x) { return (x >= 0 ? '+' : '') + Math.round(x); }

// Der Abruf im Browser. Das Gerät fragt wttr.in; wttr.in liefert einem Browser aber die Bildschirmfassung
// statt der einen Textzeile (es entscheidet nach der Browserkennung, die eine Seite nicht setzen darf).
// Deshalb holt die Seite dieselben neun Groessen bei Open-Meteo und setzt daraus genau dieselbe Zeile
// zusammen, die das Geraet von wttr.in bekommt — ab da laeuft alles durch denselben Code wie in der Firmware.
// Schlaegt der Abruf fehl, bleibt der gespeicherte Abruf stehen; die Seite arbeitet weiter ohne Netz.
async function wetterHolen(ort) {
  const o = (ort || '').trim() || FW.wetter_ort;
  const g = await fetch('https://geocoding-api.open-meteo.com/v1/search?count=1&language=de&name='
                        + encodeURIComponent(o), { cache: 'no-store' });
  if (!g.ok) throw new Error('Ortssuche antwortet mit ' + g.status);
  const gj = await g.json();
  if (!gj.results || !gj.results.length) throw new Error('Ort nicht gefunden: ' + o);
  const s = gj.results[0];
  const url = 'https://api.open-meteo.com/v1/forecast?latitude=' + s.latitude + '&longitude=' + s.longitude
    + '&current=temperature_2m,apparent_temperature,relative_humidity_2m,surface_pressure,'
    + 'wind_speed_10m,wind_direction_10m,weather_code&daily=sunrise,sunset&timezone=auto&forecast_days=1';
  const a = await fetch(url, { cache: 'no-store' });
  if (!a.ok) throw new Error('Wetterdienst antwortet mit ' + a.status);
  const d = await a.json(), c = d.current;
  const pfeil = _PFEIL[Math.round(((c.wind_direction_10m % 360) + 360) % 360 / 45) % 8];
  const roh = [
    _vz(c.temperature_2m) + '°C',
    _vz(c.apparent_temperature) + '°C',
    Math.round(c.relative_humidity_2m) + '%',
    Math.round(c.surface_pressure) + 'hPa',
    pfeil + Math.round(c.wind_speed_10m) + 'km/h',
    (_WMO[c.weather_code] || ('Code ' + c.weather_code)),
    (d.daily.sunrise[0].split('T')[1] + ':00'),
    (d.daily.sunset[0].split('T')[1] + ':00'),
    _mond(new Date(c.time + ':00Z')),
  ].join('|');
  if (roh.split('|').length !== FW.felder.length)
    throw new Error('Zeile hat ' + roh.split('|').length + ' statt ' + FW.felder.length + ' Feldern');
  const [tag, uhrzeit] = c.time.split('T');
  const [jj, mm, tt] = tag.split('-');
  FW.wetter_roh = roh; FW.wetter_datum = `${tt}.${mm}.${jj}`; FW.wetter_uhr = uhrzeit + ':00';
  FW.wetter_ort = s.name; STREIFEN.uhr = FW.wetter_uhr;
  return { roh, datum: FW.wetter_datum, uhr: FW.wetter_uhr, ort: s.name,
           land: s.country || '', hoehe: s.elevation, aus_dem_netz: true };
}

// =============================================================================================
//  Der Streifen: was der T68d druckt
// =============================================================================================
const STREIFEN = { spalten: [], motor: 0, laeuft: false, tempo: 1, uhr: FW.wetter_uhr, ebene: 'LTRS' };
const SPALTEN_MAX = 4000;

function streifenText() { return STREIFEN.spalten.map(s => s.zeichen).join(''); }

const STREIFEN_H = 250;

function streifenZeichnen() {
  const c = $('cStreifen'), ctx = c.getContext('2d');
  const B = c.clientWidth, Hh = STREIFEN_H;
  c.width = B * devicePixelRatio; c.height = Hh * devicePixelRatio;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  ctx.clearRect(0, 0, B, Hh);

  const mx = Math.max(200, B - 250);       // linke Kante des Gehaeuses
  const bandY = 96, bandH = 58;            // Papierstreifen: oben die Schrift, unten die Lochung
  const druck = mx - 10;                   // die Druckstelle unter dem Typenkopf

  // --- Papierstreifen als durchgehendes Band, es laeuft nach links aus der Maschine
  ctx.fillStyle = '#f6f1e0'; ctx.fillRect(0, bandY, mx + 6, bandH);
  ctx.strokeStyle = '#cdc4a8'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, bandY + .5); ctx.lineTo(mx + 6, bandY + .5);
  ctx.moveTo(0, bandY + bandH - .5); ctx.lineTo(mx + 6, bandY + bandH - .5); ctx.stroke();
  // leichter Schattenrand an der Austrittskante
  const sch = ctx.createLinearGradient(mx - 30, 0, mx + 6, 0);
  sch.addColorStop(0, 'rgba(0,0,0,0)'); sch.addColorStop(1, 'rgba(0,0,0,0.16)');
  ctx.fillStyle = sch; ctx.fillRect(mx - 30, bandY, 36, bandH);

  // --- Zeichen und Lochung, von der Druckstelle nach links
  const pitch = 9.4;                        // Zeichenabstand in Bildpunkten
  const anzahl = Math.floor(druck / pitch);
  const sicht = STREIFEN.spalten.slice(Math.max(0, STREIFEN.spalten.length - anzahl));
  ctx.font = '12px "DejaVu Sans Mono", "Courier New", monospace';
  ctx.textBaseline = 'top'; ctx.textAlign = 'center';
  const lochung = $('lochung').checked;
  const spurY = bandY + 27;                 // Oberkante der Lochspuren
  sicht.forEach((s, i) => {
    const x = druck - (sicht.length - 1 - i) * pitch;
    ctx.fillStyle = '#1b1b1b';
    if (s.zeichen !== ' ') ctx.fillText(s.zeichen, x, bandY + 6);
    if (!lochung) return;
    for (let b = 0; b < 5; b++) {            // Spur 1 … 5; Spur 1 ist das zuerst gesendete Bit
      const gesetzt = s.code[4 - b] === '1';
      const yy = spurY + b * 4.6 + (b >= 2 ? 3.6 : 0);     // Transportloch zwischen Spur 2 und 3
      ctx.beginPath(); ctx.arc(x, yy, gesetzt ? 2.0 : 0.6, 0, 2 * Math.PI);
      ctx.fillStyle = gesetzt ? '#1b1b1b' : '#ddd5b8'; ctx.fill();
    }
    ctx.beginPath(); ctx.arc(x, spurY + 2 * 4.6 + 0.6, 1.0, 0, 2 * Math.PI); ctx.fillStyle = '#6b6252'; ctx.fill();
  });

  // --- das Gehaeuse: Grundkoerper, Deckplatte, Waehlscheibe, Typenkopf, Tastenfeld, Lampe
  const mw = B - mx;
  ctx.fillStyle = '#b7a691'; ctx.fillRect(mx, 6, mw, Hh - 12);
  ctx.fillStyle = '#c3b39f'; ctx.fillRect(mx, 6, mw, 78);                  // Deckplatte
  ctx.fillStyle = '#9d8d76'; ctx.fillRect(mx, 84, mw, 6);                  // Kante ueber dem Streifen
  ctx.fillStyle = '#7d6f5c'; ctx.fillRect(mx, bandY - 4, 8, bandH + 8);    // Papierschacht
  ctx.strokeStyle = '#8d7d68'; ctx.lineWidth = 1; ctx.strokeRect(mx + .5, 6.5, mw - 1, Hh - 13);

  // Waehlscheibe mit dem Rufzeichen
  const dx = mx + 52, dy = 44, dr = 30;
  ctx.beginPath(); ctx.arc(dx, dy, dr, 0, 2 * Math.PI); ctx.fillStyle = '#e8e2d4'; ctx.fill();
  ctx.strokeStyle = '#9a8b74'; ctx.stroke();
  for (let k = 0; k < 10; k++) {
    const a = -Math.PI * 0.82 + k * (Math.PI * 1.64) / 9;
    ctx.beginPath(); ctx.arc(dx + (dr - 7) * Math.cos(a), dy + (dr - 7) * Math.sin(a), 3.2, 0, 2 * Math.PI);
    ctx.fillStyle = '#fbf8f0'; ctx.fill(); ctx.strokeStyle = '#b6a98f'; ctx.stroke();
  }
  ctx.beginPath(); ctx.arc(dx, dy, dr - 13, 0, 2 * Math.PI); ctx.fillStyle = '#f3efe4'; ctx.fill(); ctx.strokeStyle = '#b6a98f'; ctx.stroke();
  ctx.fillStyle = '#3f3a31'; ctx.font = '8px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText('DB3SU', dx, dy);

  // Typenkopf ueber der Druckstelle
  ctx.fillStyle = '#4e4034'; ctx.fillRect(mx - 26, bandY - 26, 34, 20);
  ctx.beginPath(); ctx.moveTo(mx - 9, bandY - 2); ctx.lineTo(mx - 16, bandY - 8); ctx.lineTo(mx - 2, bandY - 8); ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#6b6252'; ctx.font = '8px sans-serif'; ctx.textBaseline = 'bottom';
  ctx.fillText('Druckstelle', mx - 9, bandY - 30);

  // Tastenfeld
  ctx.fillStyle = '#a4937d'; ctx.fillRect(mx + 10, bandY + bandH + 12, mw - 20, Hh - (bandY + bandH + 12) - 26);
  for (let r = 0; r < 3; r++) {
    for (let k = 0; k < 10; k++) {
      const kx = mx + 22 + k * ((mw - 44) / 9) + r * 5, ky = bandY + bandH + 26 + r * 17;
      if (kx > B - 12) continue;
      ctx.beginPath(); ctx.arc(kx, ky, 6, 0, 2 * Math.PI);
      ctx.fillStyle = '#352c24'; ctx.fill(); ctx.strokeStyle = '#1f1a15'; ctx.stroke();
    }
  }

  // Motor-/Freigabelampe
  const lx = B - 34, ly = 44;
  ctx.beginPath(); ctx.arc(lx, ly, 11, 0, 2 * Math.PI);
  ctx.fillStyle = STREIFEN.motor ? '#ff7d1a' : '#57301a'; ctx.fill();
  ctx.strokeStyle = '#3a2a1a'; ctx.stroke();
  if (STREIFEN.motor) { ctx.beginPath(); ctx.arc(lx, ly, 17, 0, 2 * Math.PI); ctx.fillStyle = 'rgba(255,140,40,0.22)'; ctx.fill(); }
  ctx.fillStyle = '#4a4438'; ctx.font = '8px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  ctx.fillText('MOTOR', lx, ly + 15);

  ctx.textAlign = 'left'; ctx.fillStyle = '#6b6252'; ctx.font = '10px sans-serif';
  ctx.fillText('SIEMENS  T68d', mx + 14, Hh - 20);
}

// =============================================================================================
//  Das Sende-Frame: Zeitdiagramm des GPIO-Pegels
// =============================================================================================
let ZEITFENSTER = [];                                     // die letzten Rahmen als Pegelverlauf

function frameZeichnen() {
  const c = $('cFrame'), ctx = c.getContext('2d');
  const B = c.clientWidth, Hh = 150;
  c.width = B * devicePixelRatio; c.height = Hh * devicePixelRatio;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  ctx.clearRect(0, 0, B, Hh);
  const L = 42, R = 8, T = 26, U = Hh - 34;
  const gesamt_us = 4 * ZEICHEN_US;                        // vier Zeichen breit = 600 ms
  const X = us => L + (B - L - R) * us / gesamt_us;
  const Y = p => p ? T : U;

  ctx.strokeStyle = '#ddd'; ctx.beginPath(); ctx.moveTo(L, T); ctx.lineTo(B - R, T); ctx.moveTo(L, U); ctx.lineTo(B - R, U); ctx.stroke();
  ctx.fillStyle = '#666'; ctx.font = '10px sans-serif'; ctx.textAlign = 'right';
  ctx.fillText('Mark 1', L - 6, T + 4); ctx.fillText('Space 0', L - 6, U + 4);

  // Pegelverlauf aufbauen: je Rahmen Start(0) + 5 Datenbits + Stopp(1, 1,5 Bit)
  let t = 0; const punkte = [];
  for (const r of ZEITFENSTER) {
    punkte.push([t, 0]); t += BIT_US;                       // Startbit
    for (let i = 4; i >= 0; i--) { punkte.push([t, +r.code[i]]); t += BIT_US; }
    punkte.push([t, 1]); t += STOP_US;                      // Stoppbit 1,5 Bit
  }
  punkte.push([t, 1]);
  ctx.strokeStyle = '#1b3a8f'; ctx.lineWidth = 2; ctx.beginPath();
  let letzt = 1; ctx.moveTo(X(0), Y(punkte.length ? punkte[0][1] : 1));
  for (const [tt, p] of punkte) { ctx.lineTo(X(tt), Y(letzt)); ctx.lineTo(X(tt), Y(p)); letzt = p; }
  ctx.lineTo(X(Math.min(t, gesamt_us)), Y(letzt)); ctx.stroke();

  // Rahmengrenzen und Beschriftung
  ctx.textAlign = 'center'; ctx.font = '9px sans-serif';
  let tt = 0;
  for (const r of ZEITFENSTER) {
    ctx.strokeStyle = '#eee'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(X(tt), T - 8); ctx.lineTo(X(tt), U + 8); ctx.stroke();
    ctx.fillStyle = '#b0171f'; ctx.fillText(r.art === 'Zeichen' ? (r.zeichen === ' ' ? '␣' : r.zeichen) : r.art, X(tt + ZEICHEN_US / 2), T - 12);
    ctx.fillStyle = '#888'; ctx.fillText(r.code, X(tt + ZEICHEN_US / 2), U + 14);
    tt += ZEICHEN_US;
  }
  ctx.fillStyle = '#666'; ctx.textAlign = 'left';
  ctx.fillText(`1 Bit = ${(BIT_US / 1000).toFixed(0)} ms · Stopp = ${(STOP_US / 1000).toFixed(0)} ms (1,5 Bit) · 1 Zeichen = ${(ZEICHEN_US / 1000).toFixed(0)} ms`, L, Hh - 6);
}

function frameAufbau() {                                   // der statische Aufbau eines Rahmens
  const c = $('cAufbau'), ctx = c.getContext('2d');
  const B = c.clientWidth, Hh = 120;
  c.width = B * devicePixelRatio; c.height = Hh * devicePixelRatio;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0); ctx.clearRect(0, 0, B, Hh);
  const bits = [['Ruhe', 1, 1], ['Start', 0, 1], ['b1', 1, 1], ['b2', 1, 1], ['b3', 0, 1], ['b4', 0, 1], ['b5', 0, 1], ['Stopp', 1, 1.5], ['Ruhe', 1, 1]];
  const summe = bits.reduce((s, b) => s + b[2], 0), L = 10, R = 10, T = 34, U = 84;
  let x = L; const w = (B - L - R) / summe;
  ctx.lineWidth = 2; ctx.strokeStyle = '#1b3a8f'; ctx.beginPath(); ctx.moveTo(L, bits[0][1] ? T : U);
  let letzt = bits[0][1];
  for (const [name, p, n] of bits) {
    ctx.lineTo(x, letzt ? T : U); ctx.lineTo(x, p ? T : U); ctx.lineTo(x + n * w, p ? T : U); letzt = p; x += n * w;
  }
  ctx.stroke();
  x = L; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
  for (const [name, p, n] of bits) {
    ctx.strokeStyle = '#eee'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, T - 12); ctx.lineTo(x, U + 18); ctx.stroke();
    ctx.fillStyle = '#444'; ctx.fillText(name, x + n * w / 2, 22);
    ctx.fillStyle = '#888'; ctx.fillText((n * BIT_US / 1000).toFixed(0) + ' ms', x + n * w / 2, U + 16);
    x += n * w;
  }
  ctx.fillStyle = '#666'; ctx.textAlign = 'left'; ctx.font = '10px sans-serif';
  ctx.fillText(`Beispiel „A“ = ${LETTERS['A']} (Tabelle, Bit 5 … 1) — gesendet wird das niederwertige Bit zuerst, also ${LETTERS['A'].split('').reverse().join(' ')}`, L, Hh - 6);
}

// =============================================================================================
//  Das OLED (128 x 64) — Aufbau wie oled_status()
// =============================================================================================
let scrollPos = 0;

function oledZeichnen(wlanOk, drucktext) {
  const c = $('cOled'), ctx = c.getContext('2d');
  c.width = 128; c.height = 64;
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, 128, 64);
  ctx.fillStyle = '#39e08b'; ctx.font = '8px "DejaVu Sans Mono", monospace'; ctx.textBaseline = 'top';
  const schreibe = (s, x, y) => ctx.fillText(s, x, y);
  schreibe(wlanOk ? 'WLAN OK' : 'KEIN WLAN', 0, 0);
  schreibe(FW.wetter_datum, 0, 16);
  schreibe(STREIFEN.uhr, 0, 26);
  if (drucktext) { const t = drucktext + '   '; schreibe(t.slice(scrollPos, scrollPos + 16), 0, 40); scrollPos = (scrollPos + 1) % t.length; }
  else { scrollPos = 0; schreibe('BEREIT', 0, 40); }
}

// =============================================================================================
//  Der Druckvorgang — im Takt der echten Bitzeiten
// =============================================================================================
let ABLAUF = null;

function drucke(text, mitKopf) {
  if (ABLAUF) return;
  const erg = rahmen(text);
  const liste = (mitKopf ? kopfRahmen() : []).concat(erg.rahmen, mitKopf ? [{ art: 'CR', zeichen: '<', code: CODE_CR }, { art: 'LF', zeichen: '≡', code: CODE_LF }] : []);
  LETZT = erg; tabelleZeichnen(erg);
  STREIFEN.motor = 1; STREIFEN.laeuft = true; oledZeichnen(true, mitKopf ? 'Komplettdruck' : 'Druck');
  const start = performance.now();
  let i = 0;
  window.LABOR.fertig = false; window.LABOR.gedruckt = liste.length;
  const schritt = () => {
    const tempo = +$('tempo').value;
    const soll = ZEICHEN_US / 1000 / tempo;
    const r = liste[i];
    if (r.art !== 'LTRS' && r.art !== 'FIGS') STREIFEN.spalten.push({ zeichen: r.zeichen, code: r.code });
    if (STREIFEN.spalten.length > SPALTEN_MAX) STREIFEN.spalten.splice(0, STREIFEN.spalten.length - SPALTEN_MAX);
    ZEITFENSTER.push(r); if (ZEITFENSTER.length > 4) ZEITFENSTER.shift();
    i++;
    if (i % 2 === 0 || i === liste.length) { streifenZeichnen(); frameZeichnen(); }
    $('stand').textContent = `Rahmen ${i} von ${liste.length} · ${(i * ZEICHEN_US / 1e6).toFixed(2)} s Sendezeit`;
    if (i % 7 === 0) oledZeichnen(true, mitKopf ? 'Komplettdruck' : 'Druck');
    if (i < liste.length && STREIFEN.laeuft) { ABLAUF = setTimeout(schritt, soll); }
    else {
      ABLAUF = null; STREIFEN.motor = 0; STREIFEN.laeuft = false; streifenZeichnen(); oledZeichnen(true, null);
      window.LABOR.fertig = true; window.LABOR.echtzeit_ms = performance.now() - start;
      $('stand').textContent = `fertig: ${i} Rahmen, ${(i * ZEICHEN_US / 1e6).toFixed(2)} s Sendezeit bei ${BAUD} Baud (gelaufen in ${((performance.now() - start) / 1000).toFixed(2)} s)`;
    }
  };
  schritt();
}

function anhalten() { STREIFEN.laeuft = false; if (ABLAUF) { clearTimeout(ABLAUF); ABLAUF = null; } STREIFEN.motor = 0; streifenZeichnen(); oledZeichnen(true, null); }

// =============================================================================================
//  Die Umsetzungstabelle unter dem Eingabefeld
// =============================================================================================
let LETZT = null;

function tabelleZeichnen(erg) {
  const koerper = $('umsetzung'); const zeilen = [];
  let ebene = 'LTRS', n = 0;
  for (const r of erg.rahmen) {
    n++;
    if (n > 240) { zeilen.push(`<tr><td colspan="5" class="small">… ${erg.rahmen.length - 240} weitere Rahmen</td></tr>`); break; }
    if (r.art === 'LTRS' || r.art === 'FIGS') ebene = r.art;
    const zg = r.art === 'Zeichen' ? (r.zeichen === ' ' ? '␣' : r.zeichen) : '';
    zeilen.push(`<tr><td>${n}</td><td>${r.art}</td><td><b>${zg}</b></td><td><code>${r.code}</code></td><td><code>${r.code.split('').reverse().join(' ')}</code></td></tr>`);
  }
  koerper.innerHTML = zeilen.join('');
  const zeichen = erg.rahmen.filter(r => r.art === 'Zeichen').length;
  const um = erg.rahmen.filter(r => r.art === 'LTRS' || r.art === 'FIGS').length;
  const crlf = erg.rahmen.filter(r => r.art === 'CR' || r.art === 'LF').length;
  $('bilanz').innerHTML = `<b>${erg.anzahl} Rahmen</b> = ${zeichen} Zeichen + ${um} Umschaltungen + ${crlf} Wagenrücklauf/Zeilenvorschub · `
    + `Sendezeit ${erg.dauer_s.toFixed(2)} s bei ${BAUD} Baud (${(ZEICHEN_US / 1000).toFixed(0)} ms je Rahmen) · `
    + `längste Zeile ${Math.max(...erg.wrapped.split('\n').map(z => z.length))} von ${ZEILENLAENGE} Zeichen`;
  $('erweitert').textContent = erg.erweitert.replace(/\r/g, '');
  $('umbrochen').textContent = erg.wrapped.replace(/\r/g, '');
}

function neuUmsetzen() { const erg = rahmen($('eingabe').value); LETZT = erg; tabelleZeichnen(erg); ZEITFENSTER = erg.rahmen.slice(0, 4); frameZeichnen(); }

// =============================================================================================
window.addEventListener('DOMContentLoaded', () => {
  $('eingabe').addEventListener('input', neuUmsetzen);
  $('drucken').onclick = () => drucke($('eingabe').value, false);
  $('wetter').onclick = () => { $('eingabe').value = wetterText(); neuUmsetzen(); drucke(wetterText(), true); };
  $('jetzt').onclick = async () => {
    const n = $('netzstand'), knopf = $('jetzt');
    knopf.disabled = true; n.textContent = 'Frage wttr.in nach „' + $('ort').value.trim() + '“ …';
    try {
      const r = await wetterHolen($('ort').value);
      $('rohdaten').textContent = FW.wetter_roh;
      n.textContent = `Frischer Abruf für ${r.ort}${r.land ? ', ' + r.land : ''} — Ortszeit ${r.datum} ${r.uhr}. Die neun Felder stehen unten als Zeile, wie sie das Gerät von wttr.in bekommt.`;
      $('eingabe').value = wetterText(); neuUmsetzen(); drucke(wetterText(), true);
    } catch (f) {
      n.textContent = 'Kein Abruf möglich (' + f.message + '). Es bleibt beim gespeicherten Abruf vom '
        + FW.wetter_datum + ' — die Seite arbeitet weiter ohne Netz.';
    } finally { knopf.disabled = false; }
  };
  $('anhalten').onclick = anhalten;
  $('leeren').onclick = () => { STREIFEN.spalten = []; ZEITFENSTER = []; streifenZeichnen(); frameZeichnen(); $('stand').textContent = 'Streifen leer.'; };
  $('lochung').addEventListener('change', streifenZeichnen);
  $('tempo').addEventListener('change', () => $('tempoWert').textContent = $('tempo').selectedOptions[0].text);
  $('tempoWert').textContent = $('tempo').selectedOptions[0].text;
  $('rohdaten').textContent = FW.wetter_roh;
  $('formatzeile').textContent = FW.format;
  neuUmsetzen(); frameAufbau(); streifenZeichnen(); oledZeichnen(true, null);
  window.addEventListener('resize', () => { streifenZeichnen(); frameZeichnen(); frameAufbau(); });
  // Zugriffe fuer die Browser-Pruefung. Bewusst Funktionen und keine Getter: Object.assign wuerde
  // einen Getter beim Zuweisen einmal auslesen und damit einfrieren.
  window.LABOR = {
    rahmen, expand, wrapLines, sanitize, wetterFelder, wetterText, drucke, anhalten,
    wetterHolen, wetterStand: () => ({ ort: FW.wetter_ort, roh: FW.wetter_roh, datum: FW.wetter_datum, uhr: FW.wetter_uhr }),
    bitzeiten: { baud: BAUD, bit_us: BIT_US, stop_us: STOP_US, zeichen_us: ZEICHEN_US, zeilenlaenge: ZEILENLAENGE },
    letzt: () => LETZT, streifen: () => streifenText(),
    spalten: () => STREIFEN.spalten.length, motor: () => STREIFEN.motor,
    fertig: true, gedruckt: 0, echtzeit_ms: 0,
  };
});
"""


def seite() -> str:
    doku = dokument_html(MANUSKRIPT)
    video = daten_uri(VIDEO)
    bilder = "".join(
        f'<figure><img src="{daten_uri(p)}" alt=""><figcaption class="small">{u}</figcaption></figure>'
        for p, u in BILDER)
    css = """
:root { --tinte:#1a1a1a; --leise:#666; --blau:#1b3a8f; --rot:#b0171f; --karte:#fff; --grund:#fbfaf7; --linie:#d8d4cc; }
body { font-family: "DejaVu Serif", Georgia, serif; color: var(--tinte); background: var(--grund); margin: 0; line-height: 1.45; }
header { padding: 12px 24px 8px; border-bottom: 1px solid var(--linie); background: #f3f1ea; }
h1 { margin: 0 0 3px; font-size: 21px; } h2 { font-size: 17px; margin: 16px 0 8px; } h3 { font-size: 15px; margin: 12px 0 6px; }
.small { color: var(--leise); font-size: 13px; }
main { display: grid; grid-template-columns: 420px 1fr; gap: 16px; padding: 14px 24px; }
@media (max-width: 1050px) { main { grid-template-columns: 1fr; } }
.karte { background: var(--karte); border: 1px solid var(--linie); border-radius: 8px; padding: 12px 16px; }
button { font: inherit; padding: 6px 12px; margin: 3px 6px 3px 0; border: 1px solid var(--blau); background: #eef2fa; border-radius: 6px; cursor: pointer; }
button.haupt { background: var(--blau); color: #fff; }
select, textarea { font: inherit; }
textarea { width: 100%; box-sizing: border-box; font-family: "DejaVu Sans Mono", monospace; font-size: 13px; }
canvas { display: block; width: 100%; background: #fff; }
canvas#cStreifen { height: 250px; border: 1px solid var(--linie); border-radius: 6px; background: #efece2; }
canvas#cFrame { height: 150px; border: 1px solid var(--linie); border-radius: 6px; }
canvas#cAufbau { height: 120px; border: 1px solid var(--linie); border-radius: 6px; }
canvas#cOled { width: 384px; max-width: 100%; height: 192px; border: 5px solid #222; border-radius: 5px; background: #000; image-rendering: pixelated; }
table.umsetz { border-collapse: collapse; font-size: 12px; width: 100%; }
table.umsetz td, table.umsetz th { border-bottom: 1px solid var(--linie); padding: 1px 6px; text-align: left; }
.rollen { max-height: 260px; overflow: auto; border: 1px solid var(--linie); border-radius: 6px; }
pre.streifentext { font-family: "DejaVu Sans Mono", monospace; font-size: 12px; background: #f4efdd; border: 1px solid var(--linie); border-radius: 6px; padding: 6px 8px; overflow-x: auto; margin: 4px 0; white-space: pre-wrap; word-break: break-all; }
details.doku { margin: 16px 24px; background: var(--karte); border: 1px solid var(--linie); border-radius: 8px; padding: 8px 16px; }
details.doku > summary { cursor: pointer; font-weight: bold; }
article.documentation { max-width: 900px; } article.documentation img { max-width: 100%; } article.documentation table { border-collapse: collapse; font-size: 13px; }
article.documentation td, article.documentation th { border-bottom: 1px solid var(--linie); padding: 2px 8px; text-align: left; vertical-align: top; }
figure { margin: 0 0 12px; } figure img { width: 100%; border: 1px solid var(--linie); border-radius: 6px; }
.galerie { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; } @media (max-width: 900px) { .galerie { grid-template-columns: 1fr; } }
video { width: 100%; max-width: 380px; border: 1px solid var(--linie); border-radius: 6px; background: #000; }
label.zeile { display: block; font-size: 13px; margin: 5px 0; }
"""
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>Wetter-Fernschreiber Siemens T68d · Fassung {VERSION}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"><style>{css}</style></head>
<body>
<header>
<h1>Der Wetter-Fernschreiber: ein Siemens T68d Streifenschreiber am ESP32 — RTTY und ITA2 bei 50 Baud</h1>
<p class="small" id="fassung">Fassung {VERSION} · {DATUM} · {NAMENSNENNUNG}</p>
<p class="small">Ein ESP32 holt den Wetterbericht aus dem Netz und tippt ihn auf einer Maschine von 1959 aus — fünf Bit je Zeichen, 50 Baud, Start-Stopp-Verfahren. Hier läuft dieselbe Umsetzung im Browser: Text eingeben, zusehen, wie er nach ITA2 wird, und den gezeichneten Streifenschreiber in Echtzeit drucken lassen. Alles rechnet ohne Netz.</p>
</header>
<main>
  <section class="karte">
    <h2 style="margin-top:0">Bedienen</h2>
    <button id="drucken" class="haupt">Drucken</button><button id="wetter">Wetterbericht drucken</button><button id="anhalten">Anhalten</button><button id="leeren">Streifen leeren</button>
    <label class="zeile">Ort <input id="ort" type="text" value="Künzelsau" size="16">
      <button id="jetzt">Wetter jetzt holen und drucken</button></label>
    <p class="small" id="netzstand">Der gespeicherte Abruf vom {WETTER_ZEIT[0]} ist eingestellt. „Wetter jetzt holen“ holt die neun Größen für den eingetragenen Ort aus dem Netz, setzt daraus dieselbe Zeile zusammen, die das Gerät von wttr.in bekommt, und druckt sie. Dafür braucht die Seite einmal Netz; alles andere rechnet ohne.</p>
    <label class="zeile">Tempo
      <select id="tempo"><option value="1" selected>1× — Echtzeit, 50 Baud</option><option value="4">4×</option><option value="10">10×</option><option value="40">40×</option></select>
      <span class="small" id="tempoWert"></span></label>
    <label class="zeile"><input type="checkbox" id="lochung" checked> Lochung auf dem Streifen zeigen</label>
    <label class="zeile">Text (wird sofort umgesetzt)</label>
    <textarea id="eingabe" rows="4">WETTER KUENZELSAU AM {WETTER_ZEIT[0]} UM {WETTER_ZEIT[1]}
TEMP: +28 GRAD C, FEUCHTE 30 PROZ
RYRYRYRYRY 55 73 AR SK</textarea>
    <p class="small" id="stand">Bereit.</p>
    <p class="small" id="bilanz"></p>
    <h3>Nach der Transliteration</h3>
    <pre class="streifentext" id="erweitert"></pre>
    <h3>Nach dem Umbruch auf {FIRMWARE_DATEN["zeilenlaenge"]} Zeichen Streifenbreite</h3>
    <pre class="streifentext" id="umbrochen"></pre>
  </section>
  <section class="karte">
    <h2 style="margin-top:0">Der Streifenschreiber</h2>
    <canvas id="cStreifen"></canvas>
    <p class="small">Der Papierstreifen läuft nach links aus der Maschine. „&lt;“ ist der Wagenrücklauf, „≡“ der Zeilenvorschub — der T68d hat keinen Wagen und druckt beide als Zeichen; genau so steht es auf dem Streifen des Geräts. Unter der Schrift die fünf Codelöcher je Zeichen (Darstellung nach der Fünf-Spur-Norm, Transportloch zwischen Spur 2 und 3; die Zuordnung am Gerät ist nicht nachgemessen). Umschaltzeichen (LTRS/FIGS) drucken nichts und rücken den Streifen nicht vor.</p>
    <h2>Das Sende-Frame auf der Leitung (GPIO 17)</h2>
    <canvas id="cFrame"></canvas>
    <p class="small">Die letzten vier Rahmen als Pegelverlauf: Ruhe = Mark (1), dann Startbit (0), fünf Datenbits mit dem niederwertigen zuerst, dann 1,5 Bit Stopp.</p>
    <canvas id="cAufbau"></canvas>
    <h2>Das OLED am Gerät (128 × 64)</h2>
    <canvas id="cOled"></canvas>
    <p class="small">Vier Zeilen wie in <code>oled_status()</code>: WLAN, Datum, Uhrzeit, und während des Drucks die Laufschrift.</p>
  </section>
</main>
<section class="karte" style="margin:0 24px 16px">
  <h2 style="margin-top:0">Die Umsetzung Rahmen für Rahmen</h2>
  <div class="rollen"><table class="umsetz"><thead><tr><th>#</th><th>Art</th><th>Zeichen</th><th>Code (Bit 5 … 1)</th><th>gesendet (Bit 1 … 5)</th></tr></thead><tbody id="umsetzung"></tbody></table></div>
  <p class="small">Die Tabellen <code>_BAUDOT_LETTERS</code> und <code>_BAUDOT_FIGURES</code> stehen hier unverändert so, wie sie in der Firmware stehen — sie sind beim Bauen der Seite aus <code>RTTY_Wetter_20.py</code> eingelesen worden. Der Ablauf (Transliteration, Umbruch, Umschaltung, Rahmen) ist Zeile für Zeile derselbe wie in <code>T68dSender.send_text()</code>.</p>
</section>
<section class="karte" style="margin:0 24px 16px">
  <h2 style="margin-top:0">Der gespeicherte Wetterabruf</h2>
  <p class="small">Die Seite trägt eine gespeicherte Antwort von wttr.in — die des Komplettdrucks vom {WETTER_ZEIT[0]}, den das dritte Foto zeigt; ohne Netz rechnet sie damit. Mit „Wetter jetzt holen“ tritt an ihre Stelle ein frischer Abruf für den eingetragenen Ort. Das Gerät fragt wttr.in; wttr.in gibt einem Browser aber die Bildschirmfassung statt dieser einen Zeile, weil es nach der Browserkennung entscheidet und eine Seite die nicht setzen darf. Deshalb holt die Seite dieselben neun Größen bei Open-Meteo (Ortssuche und Wetter, beide ohne Schlüssel) und setzt sie in genau dieses Format; ab da läuft alles durch denselben Code wie in der Firmware. Die Mondphase rechnet sie selbst aus dem Alter seit einem bekannten Neumond, der Windpfeil zeigt die Richtung, aus der es weht. Angefordert wird sie mit der Formatzeile <code id="formatzeile"></code>, die Antwort kommt als eine Zeile mit „|“ zwischen den neun Feldern:</p>
  <pre class="streifentext" id="rohdaten"></pre>
  <p class="small">Daraus baut die Seite denselben Text wie <code>send_komplett()</code>: Kopf mit Datum und Uhrzeit, die neun Felder mit den Beschriftungen aus <code>FIELD_LABELS</code>, Nachspann „RYRYRYRYRY“ und „55 73 AR SK“. Windpfeil und Mondzeichen gehen vorher durch <code>sanitize_weather_text()</code>.</p>
</section>
<section class="karte" style="margin:0 24px 16px">
  <h2 style="margin-top:0">Vom Gerät</h2>
  <div class="galerie">
    <div><video id="video" controls preload="metadata" src="{video}"></video><p class="small">Die Maschine tippt den Wetterbericht (22 s, mit Ton). Der Streifen trägt die Schrift und darunter die Lochung.</p></div>
    {bilder}
  </div>
</section>
<details class="doku" id="dokuManuskript"><summary>Dokumentation — das Manuskript zum Wetter-Fernschreiber</summary>
<article class="documentation">{doku}</article></details>
<script>
const FW = {json.dumps(FIRMWARE_DATEN, ensure_ascii=False)};
{SEITE_JS}
</script>
</body></html>
"""


if __name__ == "__main__":
    t = seite()
    ZIEL.write_text(t, encoding="utf-8")
    print(f"{ZIEL.name}: {len(t.encode('utf-8'))/1024/1024:.2f} MB (Fassung {VERSION}, {DATUM})")
