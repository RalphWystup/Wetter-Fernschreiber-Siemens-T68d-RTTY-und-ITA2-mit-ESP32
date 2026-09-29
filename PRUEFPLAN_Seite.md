# Prüfplan — Seite „Wetter-Fernschreiber“ (Fassung 1.0, 29.09.2026)

Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)

Die Seite trägt die ITA2-Umsetzung der ESP32-Software (`RTTY_Wetter_20.py`) als JavaScript: dieselben
Tabellen — sie werden beim Bauen aus der Firmware eingelesen —, derselbe Ablauf aus `send_text()`,
dieselben Bitzeiten. Dazu den gezeichneten Siemens T68d Streifenschreiber, das Sende-Frame als
Zeitdiagramm, das OLED, den gespeicherten Wetterabruf, Video, Fotos und das Manuskript als Reiter.
Jede Zeile hat eine Schranke.

**Der zweite Weg.** T3 ist die tragende Prüfung: `nachrechnung_ita2.py` lädt die **Firmware selbst**
auf dem PC (mit denselben Attrappen wie `test_rtty.py`) und rechnet die Rahmenliste aus. Der Browser
rechnet sie unabhängig davon in JavaScript. Verglichen wird Rahmen für Rahmen — Art, Zeichen und
Fünf-Bit-Code. Der Prüfsatz erzwingt beide Ebenen und mehrfaches Umschalten (Ziffern, Satzzeichen,
Klammern, das ganze Alphabet, Zeilenumbruch).

| Nr. | Kriterium | Prüfmittel | Schranke | Ergebnis |
|:--|:--|:--|:--|:--|
| T1 | keine Konsolenfehler | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T2 | Werkzeug vor Text: der Knopf „Drucken“ steht bei 210 px | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T3 | ITA2 gegen die Nachrechnung aus RTTY_Wetter_20.py: 149 Rahmen, 0 abweichend | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T4 | Transliteration und Umbruch gleich (2 Abschnitte, längster 63 von 69 Zeichen) | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T5 | Bitzeiten: 50 Baud, 1 Bit = 20000 µs (Soll 20000), Stopp = 30000 µs (Soll 30000 = 1,5 Bit), Zeichen = 150000 µs (Soll 150000), Streifenbreite 69 | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T6 | dieselben Zeiten wie in der Firmware (20000 / 30000 / 150000 µs) | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T7 | Echtzeit bei Tempo 1×: 26 Rahmen, Soll 3.90 s, gelaufen 3.77 s (3.2 % Abweichung, Schranke 20 %) | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T8 | Streifen nach dem Durchlauf: 262 Zeichen, alle 12 erwarteten Stücke des Geräts vorhanden | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T9 | Streifenspalten: 262 (Umschaltzeichen drucken nichts und rücken nicht vor) | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T10 | Motorfreigabe nach dem Druck wieder aus (0) | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T11 | Video eingebettet: 1.87 MB im data:video/mp4 (Soll 1.87 MB, Zeichenzahl 2616598 = Soll 2616598) — der Prüfbrowser hat keinen H.264-Decoder (MEDIA_ERR_SRC_NOT_SUPPORTED), Spielbarkeit mit ffprobe belegt | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T12 | drei Fotos vom Gerät geladen: 944×2048, 944×2048, 944×2048 | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T13 | Manuskript als Reiter in der Seite, Länge 31305 | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T14 | neutralisiert: 0 Netzadressen in der Seite (Schranke 0), Netzname und Kennwort nur als Platzhalter — gesucht wird der Platzhalter, nie der Wert | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T15 | Kopfzeile: Fassung 1.0 · 29.09.2026 · Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI u | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T16 | OLED gezeichnet (277 helle Bildpunkte von 8192, Schranke 150 — vier Zeilen zu 8 Punkten Höhe) | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T17 | Streifen mit Schrift und Lochung gezeichnet (130629 dunkle Bildpunkte) | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
| T18 | Abruf aus dem Netz: Hamburg, 9 Felder, 29.09.2026 23:45:00 — „+18°C|+16°C|61%|1020hPa|↘12km/h|Overcast|07:…“ | `pruefe_seite.mjs` (Playwright, Chromium) | siehe Text | ok |
Stand: 2026-09-29T21:51 · 18 Kriterien, 0 Beanstandung(en).
`fernschreiber_oled.png`, `fernschreiber_geraet.png`): der Streifen läuft mit Schrift und Lochung
nach links aus der gezeichneten Maschine, die Motorlampe leuchtet während des Drucks, das OLED zeigt
`WLAN OK`, `10.07.2026`, `16:55:09` und `BEREIT`, das Zeitdiagramm zeigt die vier letzten Rahmen mit
ihren Codes, und die drei Fotos vom Gerät stehen neben dem Video.

**Was der Prüfbrowser nicht kann.** Das Chromium von Playwright wird ohne den H.264-Decoder gebaut;
es meldet für das eingebettete Video `MEDIA_ERR_SRC_NOT_SUPPORTED`. Geprüft wird deshalb, dass die
vollständige Datei bitgenau in der Seite steht (Zeichenzahl des `data:`-Verweises gegen die
Dateigröße); dass sie ein spielbares Video ist, ist mit `ffprobe` belegt: H.264 + AAC, 22,07 s,
540 × 960, 30 Bilder/s, 1 962 432 Byte, keine Aufnahme- oder Ortsangaben in den Metadaten.


**Nachtrag 29.09.2026 — der Abruf aus dem Netz.** Auf Wunsch des Verfassers holt die Seite auf Knopfdruck den **wirklichen** Wetterbericht für einen eingetragenen Ort und druckt ihn auf den Streifen. Das Gerät fragt wttr.in; wttr.in gibt einem Browser aber die Bildschirmfassung statt der einen Textzeile, weil es nach der Browserkennung entscheidet und eine Seite die nicht setzen darf. Deshalb holt die Seite dieselben neun Größen bei Open-Meteo (Ortssuche und Wetter, beide ohne Schlüssel, beide mit `Access-Control-Allow-Origin: *`) und setzt sie in genau das Format, das das Gerät von wttr.in bekommt — ab da läuft alles durch denselben Code. Die Mondphase rechnet die Seite aus dem Alter seit einem bekannten Neumond, der Windpfeil zeigt die Richtung, aus der es weht. **T18** prüft das: nach dem Abruf für einen anderen Ort müssen neun Felder dastehen, andere als vorher, mit dem Ortsnamen aus der Ortssuche. Ohne Netz muss die Seite beim gespeicherten Abruf bleiben und das melden — auch das gilt als bestanden, damit die Prüfung ohne Netz nicht falsch anschlägt.
