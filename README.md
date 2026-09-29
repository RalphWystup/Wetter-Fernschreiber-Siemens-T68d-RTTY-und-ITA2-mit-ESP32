# Der Wetter-Fernschreiber: ein Siemens T68d Streifenschreiber am ESP32

<img src="Foto_Ralph_Wystup.jpg" align="right" width="140" alt="Prof. Dr.-Ing. Ralph Wystup">

Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)

**Seite öffnen:** https://ralphwystup.github.io/Wetter-Fernschreiber-Siemens-T68d-RTTY-und-ITA2-mit-ESP32/ — Text eingeben und zusehen, wie er nach ITA2 wird; das Sende-Frame als
Zeitdiagramm; ein gezeichneter Streifenschreiber, der in Echtzeit auf einen Papierstreifen druckt;
der gespeicherte Wetterbericht; das OLED; Video und Fotos vom Gerät; das Manuskript als Reiter.
Läuft offline.

Ein ESP32 holt zyklisch den Wetterbericht von wttr.in und druckt ihn auf einer Fernschreibmaschine
von 1959 aus — im klassischen RTTY-Verfahren, im Fünf-Bit-Code ITA2, bei 50 Baud. Der Siemens T68d
ist ein **Streifenschreiber**: er schreibt fortlaufend auf einen schmalen Papierstreifen, deshalb
druckt er Wagenrücklauf und Zeilenvorschub als sichtbare Zeichen („&lt;“ und „≡“). Datum und Uhrzeit
kommen ohne Zeitdienst aus dem HTTP-Kopf derselben Antwort, mit selbsttätiger Sommerzeit. Ein OLED
zeigt den Zustand; ein Emulator und ein Prüfprogramm führen dieselbe Software auf dem PC aus.

![Das Druckbild des Geräts](bilder/T68d_Druckbild.jpeg)

## Was drin ist

| Datei | Inhalt |
|:--|:--|
| [`Fernschreiber_1.0.html`](Fernschreiber_1.0.html) | die Seite: ITA2-Umsetzung, Sende-Frame, gezeichneter Streifenschreiber, Wetterbericht, OLED, Video, Fotos, Dokumentation |
| [`MANUSKRIPT_Fernschreiber.pdf`](MANUSKRIPT_Fernschreiber.pdf) | das Manuskript: Aufbau, Theorie RTTY/ITA2, jede Funktion der Programme, die Uhr aus den Wetterdaten, Prüfungen, Bedienung, Fehlersuche, Anhang (auch als `.md` und `.docx`) |
| [`PRUEFPLAN_Seite.md`](PRUEFPLAN_Seite.md) | der Prüfplan der Seite: 17 Kriterien, jedes mit Schranke und Ergebnis |
| `firmware/RTTY_Wetter_20.py` | die ESP32-Software (MicroPython): ITA2-Tabellen, `T68dSender`, Wetterabruf, Uhr aus dem HTTP-Kopf, Druckfunktionen; Netzname und Kennwort sind Platzhalter |
| `firmware/ssd1306.py`, `firmware/boot.py`, `firmware/previous.json` | der Displaytreiber für den SSD1306 (MicroPython-Standardtreiber), die Startdatei des Geräts und der zuletzt gespeicherte Wetterstand, an dem die Änderungserkennung misst |
| `pc/fernschreiber_emulator.py` | der Emulator: bildet Maschine, OLED und Motorlampe auf dem PC nach und benutzt dabei die **echten** Funktionen der Firmware |
| `pc/test_rtty.py` | das Prüfprogramm: Wetterzerlegung, RTTY-Rückschleife, Zeilenumbruch, Uhr und Sommerzeit — 23 Prüfungen |
| `seite/` | der Erzeuger der Seite, die Browser-Prüfung (Playwright) mit ihrem Ergebnis und `nachrechnung_ita2.py`, das die ITA2-Umsetzung unabhängig aus der Firmware nachrechnet |
| `bilder/`, `Video_Fernschreiber_druckt.mp4` | die Maschine, die Steuerelektronik, das Druckbild; das Video zeigt die Maschine beim Tippen (22 s, mit Ton) |
| `index.html` | leitet auf die Seite weiter, damit GitHub Pages sie unter der Adresse oben zeigt |

Emulator und Prüfprogramm laden `RTTY_Wetter_20.py` aus dem Ordner, in dem sie liegen — für den
Betrieb auf dem PC also eine Kopie der Firmware neben sie legen:

```
cp firmware/RTTY_Wetter_20.py pc/ && cd pc && python3 test_rtty.py
```

Alle Netzadressen, Netznamen und Kennwörter des Aufbaus sind in dieser Veröffentlichung durch
Platzhalter ersetzt; das Kennwort steht als ebenso viele „x“, wie es Zeichen hat.
Die Siemens-Betriebsanleitung *Fernschreibmaschine T68*, Dezember 1959, ist als Quelle benutzt, aber
wegen fremden Urheberrechts nicht mitveröffentlicht.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
