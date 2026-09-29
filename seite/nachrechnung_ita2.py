#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nachrechnung_ita2.py — die ITA2-Umsetzung unabhaengig nachrechnen, direkt aus der ESP32-Software.

Der zweite Weg zur Simulation in der Seite (Grundsatz „zwei unabhaengige Wege"): hier laeuft der
Originalcode der Firmware auf dem PC — dieselben Tabellen, dieselbe Pipeline —, und das Ergebnis ist
die Liste der gesendeten Rahmen. Die Browser-Pruefung (pruefe_seite.mjs) vergleicht Zeichen fuer
Zeichen mit dem, was die Seite im Browser erzeugt; abweichen darf kein einziger Rahmen.

Aufruf:   python3 nachrechnung_ita2.py "<Text>"        -> JSON auf der Standardausgabe
          python3 nachrechnung_ita2.py --probe          -> der Pruefsatz beider Ebenen
Ausgabe:  {"text": ..., "wrapped": ..., "rahmen": [{"art": "...", "zeichen": "A", "code": "00011"}, ...],
           "bit_us": 20000, "stop_us": 30000, "zeichen_us": 150000, "dauer_s": ...}
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

# --- MicroPython-Attrappen, damit die Firmware auf dem PC laedt (wie in test_rtty.py) ----------
PEGEL: list[tuple[int, int]] = []

machine = types.ModuleType("machine")


class Pin:
    OUT = 1
    IN = 0

    def __init__(self, id, mode=None, value=None):
        self.id = id
        self._v = 0 if value is None else value

    def value(self, v=None):
        if v is None:
            return self._v
        self._v = v
        PEGEL.append((self.id, v))


class ADC:
    ATTN_11DB = 3
    WIDTH_12BIT = 3

    def __init__(self, pin):
        self.pin = pin

    def atten(self, a):
        pass

    def width(self, w):
        pass

    def read(self):
        return 2048


class I2C:
    def __init__(self, *a, **k):
        pass


machine.Pin, machine.ADC, machine.I2C = Pin, ADC, I2C
sys.modules["machine"] = machine

network = types.ModuleType("network")


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


network.WLAN, network.STA_IF = WLAN, 0
sys.modules["network"] = network

urequests = types.ModuleType("urequests")


class _Resp:
    def __init__(self, text):
        self.text = text

    def close(self):
        pass


urequests.get = lambda url, **k: _Resp("")
urequests._Resp = _Resp
sys.modules["urequests"] = urequests

ssd1306 = types.ModuleType("ssd1306")


class SSD1306_I2C:
    def __init__(self, *a, **k):
        pass

    def fill(self, *a):
        pass

    def text(self, *a):
        pass

    def show(self, *a):
        pass


ssd1306.SSD1306_I2C = SSD1306_I2C
sys.modules["ssd1306"] = ssd1306

# Die Firmware liegt neben dieser Datei (Ausfuhr: firmware/) oder im Arbeitsbereich.
for kandidat in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent / "firmware", Path("/workspace")):
    if (kandidat / "RTTY_Wetter_20.py").is_file():
        sys.path.insert(0, str(kandidat))
        break
import RTTY_Wetter_20 as rtty          # noqa: E402

PROBE = ("TEMP: +28 GRAD C, FEUCHTE 30 PROZ; WIND SW12KM/H (BOE 45)\n"
         "RYRYRY 55 73 AR SK. 0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ?!/-:;")


def rahmen(text: str) -> dict:
    """Die Pipeline der Firmware Schritt fuer Schritt — ohne DATUM/ZEIT und ohne ADC, damit das
    Ergebnis nicht von der Uhr abhaengt: _expand (Transliteration) -> _wrap_lines -> Rahmen."""
    s = rtty.T68dSender(tx_pin=17, adc_pins=[32, 33, 34])
    erweitert = s._expand(text)
    umbrochen = s._wrap_lines(erweitert)

    liste: list[dict] = []
    mode = "LTRS"
    for ch in umbrochen:
        if ch == "\n":
            liste.append({"art": "CR", "zeichen": "<", "code": rtty._CODE_CR})
            liste.append({"art": "LF", "zeichen": "≡", "code": rtty._CODE_LF})
            continue
        u = ch.upper()
        if u in rtty._BAUDOT_LETTERS:
            if mode != "LTRS":
                liste.append({"art": "LTRS", "zeichen": "", "code": rtty._CODE_LTRS})
                mode = "LTRS"
            liste.append({"art": "Zeichen", "zeichen": u, "code": rtty._BAUDOT_LETTERS[u]})
        elif u in rtty._BAUDOT_FIGURES:
            if mode != "FIGS":
                liste.append({"art": "FIGS", "zeichen": "", "code": rtty._CODE_FIGS})
                mode = "FIGS"
            liste.append({"art": "Zeichen", "zeichen": u, "code": rtty._BAUDOT_FIGURES[u]})
        # Zeichen ohne Code (z. B. das \r aus der Transliteration) erzeugen keinen Rahmen

    bit_us = round(rtty.T68dSender.BIT_TIME * 1e6)
    stop_us = round(rtty.T68dSender.STOP_TIME * 1e6)
    return {"text": text, "erweitert": erweitert, "wrapped": umbrochen,
            "zeilenlaenge": rtty.T68D_LINE_LENGTH, "baud": rtty.T68dSender.BAUD_RATE,
            "bit_us": bit_us, "stop_us": stop_us, "zeichen_us": 6 * bit_us + stop_us,
            "rahmen": liste, "anzahl": len(liste),
            "dauer_s": round(len(liste) * (6 * bit_us + stop_us) / 1e6, 3)}


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--probe"
    print(json.dumps(rahmen(PROBE if arg == "--probe" else arg), ensure_ascii=False))
