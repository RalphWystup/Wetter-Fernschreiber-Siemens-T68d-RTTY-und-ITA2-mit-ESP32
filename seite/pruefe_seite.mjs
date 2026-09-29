// Prüfung der Seite „Wetter-Fernschreiber“ im echten Browser (Chromium über Playwright).
//   T1  keine Konsolenfehler
//   T2  Werkzeug vor Text: der erste Knopf steht oben
//   T3  die ITA2-Umsetzung im Browser stimmt Rahmen für Rahmen mit der Nachrechnung in Python aus
//       RTTY_Wetter_20.py überein (nachrechnung_ita2.py) — kein einziger abweichender Rahmen
//   T4  die Bitzeiten stimmen auf µs mit 1/50 s und 1,5 Stoppbit
//   T5  Echtzeit: ein Druck bei Tempo 1× dauert so lange, wie 50 Baud es verlangen
//   T6  der gedruckte Streifen trägt nach dem Durchlauf den Text des Geräts (gegen das Druckbild)
//   T7  das Video ist eingebunden und lädt
//   T8  Dokumentation vorhanden und neutralisiert (gesucht wird der Platzhalter, nie der Wert)
//   T9  Kopfzeile mit Fassung, Datum und Namensnennung
//   T10 OLED und Streifen sind gezeichnet
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('/tmp/node_modules/playwright');

const H = '/workspace/Fernschreiber/Seite/';
const V = fs.readFileSync(H + 'VERSION', 'utf8').trim();
const S = '/tmp/claude-1000/-workspace/905236e7-aea4-4c03-805a-5e5668f5230d/scratchpad/';
let fehler = 0; const BEF = [];
const sage = (gut, t) => { console.log(`  ${gut ? 'ok    ' : 'FEHLER'} ${t}`); BEF.push({ gut, text: t }); if (!gut) fehler++; };

// --- der zweite Weg: die Firmware selbst rechnet die Rahmen auf dem PC ------------------------
const soll = JSON.parse(execFileSync('python3', [H + 'nachrechnung_ita2.py', '--probe'], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }));

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
const konsole = [];
p.on('pageerror', e => konsole.push(e.message));
p.on('console', m => { if (m.type() === 'error') konsole.push(m.text()); });
await p.goto(`file://${H}Fernschreiber_${V}.html`, { waitUntil: 'load', timeout: 180000 });
await p.waitForTimeout(1200);

sage(konsole.length === 0, 'keine Konsolenfehler' + (konsole.length ? ': ' + konsole[0].slice(0, 140) : ''));

const lage = await p.evaluate(() => document.getElementById('drucken').getBoundingClientRect().top);
sage(lage < 400, `Werkzeug vor Text: der Knopf „Drucken“ steht bei ${lage.toFixed(0)} px`);

// --- T3: Rahmen für Rahmen gegen die Nachrechnung ---------------------------------------------
const ist = await p.evaluate(t => window.LABOR.rahmen(t), soll.text);
let abweichend = 0, ersteAbweichung = '';
const n = Math.max(ist.rahmen.length, soll.rahmen.length);
for (let i = 0; i < n; i++) {
  const a = ist.rahmen[i], e = soll.rahmen[i];
  const gleich = a && e && a.art === e.art && a.zeichen === e.zeichen && a.code === e.code;
  if (!gleich) { abweichend++; if (!ersteAbweichung) ersteAbweichung = `#${i + 1}: Browser ${JSON.stringify(a)} ≠ Python ${JSON.stringify(e)}`; }
}
sage(abweichend === 0 && ist.rahmen.length === soll.rahmen.length,
  `ITA2 gegen die Nachrechnung aus RTTY_Wetter_20.py: ${soll.rahmen.length} Rahmen, ${abweichend} abweichend` + (ersteAbweichung ? ' — ' + ersteAbweichung : ''));
sage(ist.erweitert === soll.erweitert && ist.wrapped === soll.wrapped,
  `Transliteration und Umbruch gleich (${soll.wrapped.split('\n').length} Abschnitte, längster ${Math.max(...soll.wrapped.split('\n').map(z => z.length))} von ${soll.zeilenlaenge} Zeichen)`);

// --- T4: Bitzeiten auf µs ----------------------------------------------------------------------
const bz = await p.evaluate(() => window.LABOR.bitzeiten);
sage(bz.baud === 50 && bz.bit_us === 20000 && bz.stop_us === 30000 && bz.zeichen_us === 150000 && bz.zeilenlaenge === 69,
  `Bitzeiten: ${bz.baud} Baud, 1 Bit = ${bz.bit_us} µs (Soll 20000), Stopp = ${bz.stop_us} µs (Soll 30000 = 1,5 Bit), Zeichen = ${bz.zeichen_us} µs (Soll 150000), Streifenbreite ${bz.zeilenlaenge}`);
sage(bz.bit_us === soll.bit_us && bz.stop_us === soll.stop_us && bz.zeichen_us === soll.zeichen_us,
  `dieselben Zeiten wie in der Firmware (${soll.bit_us} / ${soll.stop_us} / ${soll.zeichen_us} µs)`);

// --- T5: Echtzeit ------------------------------------------------------------------------------
await p.selectOption('#tempo', '1');
await p.fill('#eingabe', 'RYRYRYRYRY 55 73 AR SK');
await p.waitForTimeout(150);
await p.click('#drucken');
await p.waitForFunction(() => window.LABOR.fertig === true, null, { timeout: 120000 });
const echt = await p.evaluate(() => ({ ms: window.LABOR.echtzeit_ms, n: window.LABOR.gedruckt }));
const sollMs = echt.n * 150;
const abw = Math.abs(echt.ms - sollMs) / sollMs;
sage(abw < 0.20, `Echtzeit bei Tempo 1×: ${echt.n} Rahmen, Soll ${(sollMs / 1000).toFixed(2)} s, gelaufen ${(echt.ms / 1000).toFixed(2)} s (${(abw * 100).toFixed(1)} % Abweichung, Schranke 20 %)`);

// --- T6: der gedruckte Streifen ----------------------------------------------------------------
await p.click('#leeren');
await p.selectOption('#tempo', '40');
await p.click('#wetter');
await p.waitForFunction(() => window.LABOR.fertig === true, null, { timeout: 300000 });
const streifen = await p.evaluate(() => window.LABOR.streifen());
const erwartet = ['<<<<≡≡≡≡WETTER KUENZELSAU AM 10.07.2026 UM 16:55:09',
  'TEMP: +28 GRAD C', 'GEFUEHLT: +28 GRAD C', 'FEUCHTE: 30 PROZ ', 'DRUCK: 1016HPA',
  'WIND: SW12KM/H', 'WETTER: SUNNY', 'SONNENAUFGANG: 05:26:34', 'SONNENUNTERGANG: 21:26:10',
  'MONDPHASE: ABNEHMEND', 'RYRYRYRYRY', '55 73 AR SK'];
const fehlt = erwartet.filter(t => !streifen.includes(t));
sage(fehlt.length === 0 && streifen.startsWith(erwartet[0]),
  `Streifen nach dem Durchlauf: ${streifen.length} Zeichen, alle ${erwartet.length} erwarteten Stücke des Geräts vorhanden` + (fehlt.length ? ' — fehlt: ' + fehlt.join(' / ') : ''));
const spalten = await p.evaluate(() => window.LABOR.spalten());
sage(spalten === streifen.length && spalten > 250, `Streifenspalten: ${spalten} (Umschaltzeichen drucken nichts und rücken nicht vor)`);
const motorAus = await p.evaluate(() => window.LABOR.motor());
sage(motorAus === 0, `Motorfreigabe nach dem Druck wieder aus (${motorAus})`);

await p.evaluate(() => window.scrollTo(0, 0));
await p.waitForTimeout(300);
await p.screenshot({ path: S + 'fernschreiber_seite.png' });

// --- T7: das Video -----------------------------------------------------------------------------
// Die Bytezahl ist die harte Schranke: so viele Byte hat die Datei, so viele müssen in der Seite
// stehen. Ob der Prüfbrowser sie auch abspielt, ist eine zweite Frage — das Chromium von Playwright
// wird ohne den H.264-Decoder gebaut; die Spielbarkeit ist deshalb mit ffprobe belegt (siehe Prüfplan).
const bytesDatei = fs.statSync('/workspace/Fernschreiber/Video_Fernschreiber_druckt.mp4').size;
const sollLaenge = 'data:video/mp4;base64,'.length + Math.ceil(bytesDatei / 3) * 4;
const video = await p.evaluate(async () => {
  const v = document.getElementById('video');
  if (!v) return null;
  if (v.readyState < 1 && !v.error) { await new Promise(r => { v.addEventListener('loadedmetadata', r, { once: true }); v.addEventListener('error', r, { once: true }); setTimeout(r, 15000); }); }
  return { dauer: v.duration, breite: v.videoWidth, hoehe: v.videoHeight, typ: v.currentSrc.slice(0, 22), laenge: v.currentSrc.length, fehler: v.error ? v.error.code : 0 };
});
const videoBytes = video ? (video.laenge - 'data:video/mp4;base64,'.length) / 4 * 3 : 0;
sage(!!video && video.typ === 'data:video/mp4;base64,' && video.laenge === sollLaenge,
  `Video eingebettet: ${(videoBytes / 1024 / 1024).toFixed(2)} MB im data:video/mp4 (Soll ${(bytesDatei / 1024 / 1024).toFixed(2)} MB, Zeichenzahl ${video ? video.laenge : '—'} = Soll ${sollLaenge})`
  + (video && video.fehler === 4 ? ' — der Prüfbrowser hat keinen H.264-Decoder (MEDIA_ERR_SRC_NOT_SUPPORTED), Spielbarkeit mit ffprobe belegt' : ` — der Prüfbrowser lädt es: ${video && video.dauer ? video.dauer.toFixed(1) + ' s, ' + video.breite + '×' + video.hoehe : 'Metadaten noch nicht da'}`));
const bilder = await p.evaluate(() => [...document.querySelectorAll('figure img')].map(i => ({ ok: i.complete && i.naturalWidth > 0, w: i.naturalWidth, h: i.naturalHeight })));
sage(bilder.length === 3 && bilder.every(x => x.ok), `drei Fotos vom Gerät geladen: ${bilder.map(x => x.w + '×' + x.h).join(', ')}`);

// --- T8: Dokumentation, neutralisiert ----------------------------------------------------------
await p.evaluate(() => document.getElementById('dokuManuskript').open = true);
await p.waitForTimeout(400);
const doku = (await p.evaluate(() => document.getElementById('dokuManuskript').textContent)).replace(/\s+/g, ' ');
sage(doku.includes('Streifenschreiber') && doku.includes('Sende-Frame') && doku.includes('Zellers Kongruenz') && doku.includes('Entwicklungsgeschichte') && doku.length > 18000,
  `Manuskript als Reiter in der Seite, Länge ${doku.length}`);
const ganz = await p.evaluate(() => document.body.textContent);
const adressen = (ganz.match(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g) || []);
sage(adressen.length === 0 && /WLAN_NAME/.test(ganz) && /WLAN_WORT/.test(ganz),
  `neutralisiert: ${adressen.length} Netzadressen in der Seite (Schranke 0), Netzname und Kennwort nur als Platzhalter \u2014 gesucht wird der Platzhalter, nie der Wert`);

const kopf = await p.$eval('#fassung', e => e.textContent);
sage(kopf.includes(`Fassung ${V}`) && kopf.includes('Ralph Wystup') && kopf.includes('Claude Code'), `Kopfzeile: ${kopf.slice(0, 80)}`);

// --- T10: gezeichnet ---------------------------------------------------------------------------
const oledPix = await p.evaluate(() => { const c = document.getElementById('cOled'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i + 1] > 128) n++; return n; });
sage(oledPix > 150, `OLED gezeichnet (${oledPix} helle Bildpunkte von ${128 * 64}, Schranke 150 \u2014 vier Zeilen zu 8 Punkten H\u00f6he)`);
const streifenPix = await p.evaluate(() => { const c = document.getElementById('cStreifen'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] < 90) n++; return n; });
sage(streifenPix > 2000, `Streifen mit Schrift und Lochung gezeichnet (${streifenPix} dunkle Bildpunkte)`);

await p.evaluate(() => document.getElementById('cStreifen').scrollIntoView({ block: 'center' }));
await p.waitForTimeout(300);
await p.screenshot({ path: S + 'fernschreiber_streifen.png' });
await p.evaluate(() => document.getElementById('cOled').scrollIntoView({ block: 'center' }));
await p.waitForTimeout(300);
await p.screenshot({ path: S + 'fernschreiber_oled.png' });
await p.evaluate(() => document.getElementById('video').scrollIntoView({ block: 'center' }));
await p.waitForTimeout(500);
await p.screenshot({ path: S + 'fernschreiber_geraet.png' });

// 18: der Abruf aus dem Netz — dieselben neun Felder, aber frisch fuer einen anderen Ort.
// Ohne Netz muss die Seite beim gespeicherten Abruf bleiben und das auch sagen; beides gilt als bestanden.
{
  const vorher = await p.evaluate(() => window.LABOR.wetterStand());
  await p.fill('#ort', 'Hamburg');
  await p.click('#jetzt');
  await p.waitForFunction(() => !document.getElementById('jetzt').disabled, { timeout: 40000 }).catch(() => {});
  const stand = await p.evaluate(() => document.getElementById('netzstand').textContent);
  const nachher = await p.evaluate(() => window.LABOR.wetterStand());
  const felder = nachher.roh.split('|').length;
  const frisch = nachher.roh !== vorher.roh && felder === 9 && /Hamburg/.test(nachher.ort);
  const ohneNetz = /Kein Abruf möglich/.test(stand) && nachher.roh === vorher.roh;
  sage(frisch || ohneNetz, frisch
    ? `Abruf aus dem Netz: ${nachher.ort}, ${felder} Felder, ${nachher.datum} ${nachher.uhr} — „${nachher.roh.slice(0, 44)}…“`
    : `kein Netz: gespeicherter Abruf bleibt stehen und wird gemeldet`);
}

await b.close();
fs.writeFileSync(H + 'pruefe_seite.json', JSON.stringify({ datum: new Date().toISOString(), fassung: V, befunde: BEF, fehler }, null, 1));
console.log(fehler ? `${fehler} Beanstandung(en)` : 'alles in Ordnung');
process.exit(fehler ? 1 : 0);
