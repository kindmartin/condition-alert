/**
 * Apps Script bound to the "Amigo del Viento" response Sheet.
 * Receives POSTs from docs/index.html and appends a row exactly like a
 * native Google Form submission would — sync_subscribers.py doesn't need
 * to change at all.
 *
 * Setup (one time, in your Google account — see MANUAL.md):
 *   1. Open the response Sheet -> Extensions -> Apps Script.
 *   2. Paste this whole file in, replacing the default Code.gs content.
 *   3. Deploy -> New deployment -> type "Web app" -> Execute as "Me",
 *      who has access "Anyone" -> Deploy. Copy the /exec URL.
 *   4. Paste that URL into APPS_SCRIPT_URL in docs/index.html and commit.
 *
 * Column order in the sheet does NOT matter here — this looks up each
 * column by keyword in row 1, the same way scripts/sync_subscribers.py
 * does on the Python side, so reordering columns later won't break it.
 */

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
      .map((h) => normalize(h));

    const row = new Array(headers.length).fill("");

    const set = (keywords, value) => {
      const idx = findCol(headers, keywords);
      if (idx !== -1) row[idx] = value;
    };

    set(["timestamp"], new Date());
    // "nombre" alone matches the person's name column (it appears first in
    // the sheet); "Nombre de la Alerta" is matched separately below with
    // both keywords required, so it isn't shadowed by this broader match.
    set(["nombre"], payload.nombre || "");
    set(["email"], payload.email || "");
    set(["telegram"], payload.telegram || "");
    set(["baja"], payload.accion || "Nueva Alerta"); // matches "...Baja de Alerta?" header
    set(["sitio"], payload.sitio || "");
    set(["referencia"], payload.tipoReferencia || "");
    set(["capa"], payload.tipoDeCapa || "");
    set(["metros"], payload.metros || "");
    set(["velocidad", "minima"], payload.velocidadMinima || "");
    set(["velocidad", "maxima"], payload.velocidadMaxima || "");
    set(["rafaga"], payload.rafagaMaxima || "");
    set(["direccion", "minima"], payload.direccionMinima);
    set(["direccion", "maxima"], payload.direccionMaxima);
    set(["nombre", "alerta"], payload.nombreAlerta || "");

    sheet.appendRow(row);

    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function normalize(text) {
  return String(text)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, ""); // strip accents
}

function findCol(headersNorm, keywords) {
  for (let i = 0; i < headersNorm.length; i++) {
    if (keywords.every((k) => headersNorm[i].indexOf(k) !== -1)) return i;
  }
  return -1;
}
