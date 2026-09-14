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
  "Estado",     // Pendiente / Aprobado / Rechazado — el admin lo cambia a mano
  "Site ID",    // slug único (ej. "cerro_tal") — lo completa el admin al aprobar
  "Timezone",   // IANA (ej. "America/Argentina/Cordoba") — lo completa el admin al aprobar
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
    "Pendiente",
    "",
    "",
  ]);
}

/**
 * Run this ONCE, manually, from the Apps Script editor (select
 * "seedExistingSites" in the function dropdown next to Run -> Run) to load
 * the sites that already existed in config/sites.yaml before this sheet
 * became the source of truth. Safe to re-run — it skips ids already present.
 */
function seedExistingSites() {
  const existing = [
    { id: "gruenten", name: "Grünten (Allgäu, DE)", tz: "Europe/Berlin",
      launch: [47.553, 10.317, 1050], landing: [47.568, 10.335, 780] },
    { id: "lujan", name: "Luján (Buenos Aires, AR)", tz: "America/Argentina/Buenos_Aires",
      launch: [-34.57, -59.05, 30] },
    { id: "cerro_otto", name: "Cerro Otto (Bariloche, AR)", tz: "America/Argentina/Salta",
      launch: [-41.14408, -71.37665, 1380] },
    { id: "cerro_san_martin", name: "Cerro San Martín / La Vieja (Bariloche, AR)", tz: "America/Argentina/Salta",
      launch: [-41.1578, -71.4289, 1250] },
    { id: "piltriquitron", name: "Piltriquitrón (El Bolsón, AR)", tz: "America/Argentina/Salta",
      launch: [-41.97461, -71.48016, 1115] },
    { id: "vicente_lopez", name: "Vicente López (Buenos Aires, AR)", tz: "America/Argentina/Buenos_Aires",
      launch: [-34.52833, -58.46155, 8] },
    { id: "loma_bola", name: "Loma Bola (Tucumán, AR)", tz: "America/Argentina/Tucuman",
      launch: [-26.82281, -65.36882, 1355] },
    { id: "merlo", name: "Merlo (San Luis, AR)", tz: "America/Argentina/San_Luis",
      launch: [-32.36947, -64.9391, 1772] },
    { id: "cuchi_corral", name: "Cuchi Corral (Córdoba, AR)", tz: "America/Argentina/Cordoba",
      launch: [-30.96712, -64.58465, 1103] },
  ];

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(PROPOSALS_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(PROPOSALS_SHEET_NAME);
    sheet.appendRow(PROPOSALS_HEADERS);
  }

  const idColIdx = PROPOSALS_HEADERS.indexOf("Site ID");
  const existingIds = sheet.getLastRow() > 1
    ? sheet.getRange(2, idColIdx + 1, sheet.getLastRow() - 1, 1).getValues().flat()
    : [];

  existing.forEach((site) => {
    if (existingIds.indexOf(site.id) !== -1) return; // already seeded
    sheet.appendRow([
      new Date(),
      "seed",
      "",
      site.name,
      site.launch[0], site.launch[1], site.launch[2],
      site.landing ? "Si" : "No",
      site.landing ? site.landing[0] : "",
      site.landing ? site.landing[1] : "",
      site.landing ? site.landing[2] : "",
      "Sitio original, cargado por seedExistingSites()",
      "Aprobado",
      site.id,
      site.tz,
    ]);
  });
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
