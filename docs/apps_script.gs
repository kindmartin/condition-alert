/**
 * Apps Script bound to the "Amigo del Viento" response Sheet.
 * Receives POSTs from docs/index.html (alerts) and docs/new-site.html
 * (site proposals) and appends a row to the right tab — sync_subscribers.py
 * doesn't need to change at all for the alerts path.
 *
 * Setup (one time, in your Google account — see MANUAL.md):
 *   1. Open the response Sheet -> Extensions -> Apps Script.
 *   2. Paste this whole file in, replacing the default Code.gs content.
 *   3. Deploy -> New deployment -> type "Web app" -> Execute as "Me",
 *      who has access "Anyone" -> Deploy. Copy the /exec URL.
 *   4. Paste that URL into APPS_SCRIPT_URL in docs/index.html AND
 *      docs/new-site.html, then commit.
 *
 * Column order in the alerts sheet does NOT matter — this looks up each
 * column by keyword in row 1, the same way scripts/sync_subscribers.py
 * does on the Python side, so reordering columns later won't break it.
 * The "Sitios propuestos" tab is created by this script itself (fixed
 * column order, since nothing else reads it — a human reviews it by eye).
 */

const PROPOSALS_SHEET_NAME = "Sitios propuestos";
const PROPOSALS_HEADERS = [
  "Timestamp", "Nombre", "Email", "Nombre del sitio",
  "Despegue lat", "Despegue lon", "Despegue elev (m)",
  "Tiene aterrizaje", "Aterrizaje lat", "Aterrizaje lon", "Aterrizaje elev (m)",
  "Comentarios",
];

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    if (payload._kind === "site_proposal") {
      handleSiteProposal(payload);
    } else {
      handleAlert(payload);
    }
    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function handleAlert(payload) {
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
}

function handleSiteProposal(payload) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(PROPOSALS_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(PROPOSALS_SHEET_NAME);
    sheet.appendRow(PROPOSALS_HEADERS);
  }
  sheet.appendRow([
    new Date(),
    payload.nombre || "",
    payload.email || "",
    payload.nombreSitio || "",
    payload.despegueLat,
    payload.despegueLon,
    payload.despegueElev || "",
    payload.tieneAterrizaje || "No",
    payload.aterrizajeLat || "",
    payload.aterrizajeLon || "",
    payload.aterrizajeElev || "",
    payload.comentarios || "",
  ]);
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
