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
| T1 | keine Konsolenfehler | `pruefe_seite.mjs` (Playwright, Chromium) | keine | ok |
| T2 | Werkzeug vor Text: der Knopf „Drucken“ steht bei 210 px | `pruefe_seite.mjs` (Playwright, Chromium) | erster Knopf oberhalb 400 px | ok |
| T3 | ITA2 gegen die Nachrechnung aus RTTY_Wetter_20.py: 149 Rahmen, 0 abweichend | `pruefe_seite.mjs` (Playwright, Chromium) | kein einziger abweichender Rahmen | ok |
| T4 | Transliteration und Umbruch gleich (2 Abschnitte, längster 63 von 69 Zeichen) | `pruefe_seite.mjs` (Playwright, Chromium) | Zeichenketten gleich | ok |
| T5 | Bitzeiten: 50 Baud, 1 Bit = 20000 µs (Soll 20000), Stopp = 30000 µs (Soll 30000 = 1,5 Bit), Zeichen = 150000 µs (Soll 150000), Streifenbreite 69 | `pruefe_seite.mjs` (Playwright, Chromium) | 20000 / 30000 / 150000 µs, 50 Baud, 69 Zeichen | ok |
| T6 | dieselben Zeiten wie in der Firmware (20000 / 30000 / 150000 µs) | `pruefe_seite.mjs` (Playwright, Chromium) | gleich der Firmware | ok |
| T7 | Echtzeit bei Tempo 1×: 26 Rahmen, Soll 3.90 s, gelaufen 3.77 s (3.2 % Abweichung, Schranke 20 %) | `pruefe_seite.mjs` (Playwright, Chromium) | Abweichung < 20 % von N · 150 ms | ok |
| T8 | Streifen nach dem Durchlauf: 262 Zeichen, alle 12 erwarteten Stücke des Geräts vorhanden | `pruefe_seite.mjs` (Playwright, Chromium) | alle zwölf Stücke vorhanden, Anfang wörtlich | ok |
| T9 | Streifenspalten: 262 (Umschaltzeichen drucken nichts und rücken nicht vor) | `pruefe_seite.mjs` (Playwright, Chromium) | Spaltenzahl = Zeichenzahl, > 250 | ok |
| T10 | Motorfreigabe nach dem Druck wieder aus (0) | `pruefe_seite.mjs` (Playwright, Chromium) | Motorfreigabe = 0 | ok |
| T11 | Video eingebettet: 1.87 MB im data:video/mp4 (Soll 1.87 MB, Zeichenzahl 2616598 = Soll 2616598) — der Prüfbrowser hat keinen H.264-Decoder (MEDIA_ERR_SRC_NOT_SUPPORTED), Spielbarkeit mit ffprobe belegt | `pruefe_seite.mjs` (Playwright, Chromium) | Zeichenzahl des data:video/mp4 = Dateigröße | ok |
| T12 | drei Fotos vom Gerät geladen: 944×2048, 944×2048, 944×2048 | `pruefe_seite.mjs` (Playwright, Chromium) | drei Bilder, alle geladen | ok |
| T13 | Manuskript als Reiter in der Seite, Länge 31305 | `pruefe_seite.mjs` (Playwright, Chromium) | vier Stichworte, > 18 000 Zeichen | ok |
| T14 | neutralisiert: 0 Netzadressen in der Seite (Schranke 0), Netzname und Kennwort nur als Platzhalter — gesucht wird der Platzhalter, nie der Wert | `pruefe_seite.mjs` (Playwright, Chromium) | 0 Netzadressen, Platzhalter vorhanden | ok |
| T15 | Kopfzeile: Fassung 1.0 · 29.09.2026 · Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI u | `pruefe_seite.mjs` (Playwright, Chromium) | Fassung, Datum, Namensnennung | ok |
| T16 | OLED gezeichnet (277 helle Bildpunkte von 8192, Schranke 150 — vier Zeilen zu 8 Punkten Höhe) | `pruefe_seite.mjs` (Playwright, Chromium) | > 150 helle Bildpunkte | ok |
| T17 | Streifen mit Schrift und Lochung gezeichnet (130629 dunkle Bildpunkte) | `pruefe_seite.mjs` (Playwright, Chromium) | > 2000 dunkle Bildpunkte | ok |
Stand: 2026-09-29 21:13**Bildschirmfotos angesehen** (`fernschreiber_seite.png`, `fernschreiber_streifen.png`,
`fernschreiber_oled.png`, `fernschreiber_geraet.png`): der Streifen läuft mit Schrift und Lochung
nach links aus der gezeichneten Maschine, die Motorlampe leuchtet während des Drucks, das OLED zeigt
`WLAN OK`, `10.07.2026`, `16:55:09` und `BEREIT`, das Zeitdiagramm zeigt die vier letzten Rahmen mit
ihren Codes, und die drei Fotos vom Gerät stehen neben dem Video.

**Was der Prüfbrowser nicht kann.** Das Chromium von Playwright wird ohne den H.264-Decoder gebaut;
es meldet für das eingebettete Video `MEDIA_ERR_SRC_NOT_SUPPORTED`. Geprüft wird deshalb, dass die
vollständige Datei bitgenau in der Seite steht (Zeichenzahl des `data:`-Verweises gegen die
Dateigröße); dass sie ein spielbares Video ist, ist mit `ffprobe` belegt: H.264 + AAC, 22,07 s,
540 × 960, 30 Bilder/s, 1 962 432 Byte, keine Aufnahme- oder Ortsangaben in den Metadaten.
