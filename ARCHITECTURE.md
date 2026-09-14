# Arquitectura de Amigo del Viento

Documento técnico: cómo está armado el sistema y por qué. Para la guía
paso a paso de setup/troubleshooting ver [`MANUAL.md`](MANUAL.md). La
última sección de este documento es el manual de operación desde el
punto de vista de quien usa el producto (piloto/suscriptor).

## 1. Idea general

Todo el sistema corre sin servidores ni hardware propio: el cómputo son
cron jobs de GitHub Actions, el almacenamiento son un archivo committeado
en el repo (`docs/sites.json`), un secret de GitHub Actions
(`SUBSCRIBERS_JSON`) y una Google Sheet, y la interfaz de usuario son dos
páginas estáticas servidas por GitHub Pages. No hay backend propio, no hay
base de datos, no hay costo.

Tres pipelines independientes, cada uno en su propio workflow con su
propio cron:

| Workflow | Cada | Qué hace |
|---|---|---|
| `sync-sites.yml` | 15 min | Sheet "Sitios propuestos" (filas Aprobado) → `docs/sites.json` |
| `sync-subscribers.yml` | 15 min | Sheet de respuestas del form → secret `SUBSCRIBERS_JSON` |
| `wind-check.yml` | 1 hora | `docs/sites.json` + `SUBSCRIBERS_JSON` + Open-Meteo → emails/Telegram |

Están separados a propósito: sitios y suscriptores cambian con
frecuencias y niveles de riesgo distintos (ver §4), y el chequeo de
viento no necesita correr más seguido que una vez por hora porque el
pronóstico no cambia tan rápido.

## 2. Fuente de datos de pronóstico: Open-Meteo

`src/fetch_forecast.py` hace **un solo request batcheado** a
`api.open-meteo.com/v1/forecast` con todos los lat/lon de todos los
puntos de todos los sitios juntos (`latitude=47.5,...` separado por
comas). Open-Meteo devuelve un array paralelo de resultados (o un objeto
plano si hay un solo punto — se normaliza en el código).

Variables horarias pedidas:
- `wind_speed_10m` / `wind_direction_10m` / `wind_gusts_10m` — superficie.
- `wind_speed_{lvl}hPa` / `wind_direction_{lvl}hPa` /
  `geopotential_height_{lvl}hPa` para `lvl` en `[1000, 925, 850, 700, 600,
  500]` — perfil vertical de viento por nivel de presión.
- `temperature_2m` / `dew_point_2m` — para estimar techo de nubes.
- `cloud_cover(_low/_mid/_high)`, `freezing_level_height`.

`timezone=auto` deja que Open-Meteo devuelva cada punto en su propia
zona horaria local aunque el request sea multi-país en un solo call
(confirmado en pruebas reales). `wind_speed_unit=kmh` evita conversión
manual. `forecast_days=3` (constante `FORECAST_DAYS` en `main.py`) define
la ventana rodante.

**Nota importante**: el campo `elevation` que devuelve la API es la
altura del grid del modelo climático, no la altura real del terreno —
puede diferir varios cientos de metros. Por eso el sistema *nunca* usa
ese campo; toda cuenta de AGL usa `elevation_m` cargado a mano (vía el
form de sitios nuevos) para cada punto.

## 3. Interpolación de viento a altura arbitraria

`src/interpolate.py` — Open-Meteo da viento solo en los niveles de
presión fijos de arriba, cada uno con su altura real (`geopotential_height`)
para esa hora (varía con la presión atmosférica). Para estimar viento a
una altura pedida por el usuario (ej. "+1000m AGL sobre el despegue"):

1. Se arma el perfil de esa hora: lista `(altura_m, velocidad, dirección)`
   ordenada de menor a mayor altura (`level_profile`).
2. Se ubican los dos niveles que "abrazan" la altura objetivo.
3. **No se puede promediar grados de dirección directamente** (270° y
   10° están cerca en la realidad pero lejos numéricamente — el
   promedio ingenuo da 140°, totalmente equivocado). Se convierte cada
   viento a componentes vectoriales u/v (`_to_uv`), se interpola
   linealmente cada componente por separado, y se reconvierte a
   velocidad/dirección (`_from_uv`).
4. Si la altura pedida cae fuera del rango de niveles disponibles, se
   usa el nivel más cercano y se marca `extrapolated: true` (aparece en
   el mail como aviso).

## 4. Los tres pipelines de datos

### 4.1 Sitios (`docs/sites.json`)

**Por qué es un proceso separado y con revisión humana**, a diferencia
de suscriptores: una coordenada mal cargada en un sitio rompe el chequeo
para *todos* los suscriptores de ese sitio; un umbral mal puesto en una
alerta personal solo afecta a esa persona. El radio de impacto de un
error justifica un gate manual acá y no en el otro flujo.

Flujo:
1. Alguien completa [`docs/new-site.html`](docs/new-site.html) (mapa
   Leaflet, click para marcar despegue/aterrizaje, botón de estimación
   automática de elevación vía `api.open-elevation.com`).
2. El form hace POST a un Google Apps Script (`docs/apps_script.gs`,
   función `handleSiteProposal`), que agrega una fila a la pestaña
   "Sitios propuestos" de la Sheet con `Estado: "Pendiente"` y
   `Site ID`/`Timezone` vacíos.
3. Un humano (admin) revisa la fila a mano, completa `Site ID` (slug
   único) y `Timezone` (zona IANA válida), y cambia `Estado` a
   `"Aprobado"`.
4. `scripts/sync_sites.py`, corrido cada 15 min por
   `sync-sites.yml`, lee esa pestaña publicada como CSV
   (`SITES_SHEET_CSV_URL`), filtra filas con Estado que contenga
   "aprobado"/"approved", valida que el timezone sea una zona IANA real
   (`zoneinfo.ZoneInfo`, si no existe descarta la fila con log) y que
   estén las 3 coordenadas de despegue, arma el punto `landing` solo si
   "Tiene aterrizaje" es verdadero y sus 3 coordenadas están presentes,
   aplica "última fila aprobada por `site_id` gana" (permite corregir un
   sitio re-aprobando una fila nueva), y escribe `docs/sites.json`
   ordenado por id.
5. El workflow commitea `docs/sites.json` con el `GITHUB_TOKEN` propio
   (no necesita ningún secret nuevo — a diferencia del pipeline de
   suscriptores, escribir un archivo del repo no requiere el cifrado
   sealed-box que sí exige la API de Secrets).
6. `docs/index.html` (página de alta de alertas) hace
   `fetch("sites.json")` al cargar y llena el dropdown de sitios en
   runtime — ningún sitio está hardcodeado en HTML/JS/Python/YAML.

Salvaguarda: si el resultado filtrado da 0 sitios (ej. la URL del CSV
está mal o la sheet está vacía), el script se niega a pisar
`docs/sites.json` con una lista vacía y sale con error.

### 4.2 Suscriptores (`SUBSCRIBERS_JSON` secret)

**Por qué va a un GitHub Secret y no a un archivo del repo**: el repo es
público; un archivo committeado con emails de la gente quedaría expuesto
para siempre en el historial de git. Un Secret de Actions no es legible
ni por lectura del repo ni por la API salvo por el propio workflow.

Flujo:
1. Alguien completa [`docs/index.html`](docs/index.html) (mapa, brújula
   SVG para elegir rango de dirección, sliders de velocidad, nombre de
   alerta).
2. POST al mismo Apps Script (`handleAlert`), que matchea columnas por
   keyword (`findCol`) y agrega una fila a la hoja principal de
   respuestas — sin pisar el orden de columnas si se agregan preguntas
   nuevas al form.
3. `scripts/sync_subscribers.py`, cada 15 min, lee esa hoja como CSV
   (`SHEET_CSV_URL`), reconstruye el `SUBSCRIBERS_JSON` completo desde
   cero a partir de **todas** las filas en orden cronológico (así llegan
   de Google Sheets), con semántica "la última fila de cada
   `(sitio, identidad, nombre_de_alerta, firma_de_capa)` gana":
   - Cada persona puede tener varias alertas independientes por sitio
     (campo "Nombre de la Alerta": "Alerta 1", "Alerta 2"...). Cada una
     se evalúa con lógica OR entre sí (alcanza con que una cumpla), y
     AND entre las capas dentro de una misma alerta.
   - Volver a enviar el form con la misma `(kind, point, meters)` bajo el
     mismo nombre de alerta **reemplaza** la capa anterior — así se
     edita.
   - Elegir "Baja/Remover" en el campo Acción limpia solo esa alerta
     nombrada, sin tocar otras alertas de la misma persona en el mismo
     sitio.
   - Emparejamiento de sitio tolerante a variantes de texto: `loose()`
     saca espacios/guiones/guiones bajos y compara sin acentos/mayúsculas,
     así "Vicente Lopez" matchea `vicente_lopez`.
4. `build_layer()` valida que el `point` (`launch`/`landing`) exista
   realmente en ese sitio (`docs/sites.json`) — si no, descarta la capa
   con un log en vez de dejar pasar un dato que rompería el chequeo
   horario.
5. El resultado se sube como el secret `SUBSCRIBERS_JSON` vía
   `scripts/github_secret.py`, que cifra el valor con la clave pública
   del repo (libsodium sealed box, requerido por la API de Secrets de
   GitHub) usando un PAT de permisos mínimos (`GH_PAT_FOR_SECRETS`,
   scope único "Secrets: Read and write").

### 4.3 Chequeo de viento y notificación (`wind-check.yml`, cada hora)

`src/main.py` es el orquestador. Por cada sitio con suscriptores:

1. Trae el pronóstico batcheado (§2) para todos sus puntos.
2. Por cada suscriptor y cada una de sus alertas nombradas, evalúa sus
   capas (`src/rules.py::evaluate_layers`) hora por hora, para toda la
   ventana de `FORECAST_DAYS=3` días.
3. Recorta a la ventana rodante real: solo horas desde "ahora" (hora
   local del sitio) en adelante — no repite horas ya pasadas del día.
4. Compara contra el estado guardado (`state/sent_log.json`) con una
   **máquina de estados on/off** por `(sitio, identidad#nombre_alerta)`:
   - Si antes estaba "off" y ahora hay ≥1 hora que cumple → **ALERT ON**,
     manda el mail/Telegram con el detalle de cada hora que cumple, y
     graba la clave como "on".
   - Si antes estaba "on" y ahora no cumple ninguna hora → **ALERT
     CLEARED**, manda un aviso corto de que la ventana desapareció, y
     borra la clave.
   - Si no cambió (on→on u off→off) → no manda nada.

   Este diseño reemplazó un dedup viejo por "un mail por día calendario"
   que no avisaba cuándo una ventana dejaba de estar disponible y podía
   perderse ventanas que aparecían y desaparecían dentro del mismo día.
5. Al final, `prune_stale()` borra del estado cualquier clave que ya no
   corresponda a un suscriptor/alerta vigente (por ejemplo alguien que se
   dio de baja mientras su alerta estaba en "on"), y el workflow
   commitea `state/sent_log.json` solo si cambió — con el mismo patrón
   `git add` → `git diff --staged --quiet` → commit/pull --rebase/push
   usado en `sync-sites.yml` (ver §6, bug histórico).

Resiliencia: cada suscriptor se evalúa dentro de su propio
`try/except` — si una entrada de datos rara revienta la evaluación de un
suscriptor, se loguea el error y se sigue con los demás en vez de que un
solo dato malo tumbe la corrida completa (esto costó un incidente real,
ver §6).

## 5. Piezas de infraestructura reutilizadas entre pipelines

- **`scripts/sheets.py`**: un GET plano a la URL de "Publicar en la web
  como CSV" de una sheet — cero autenticación, cero Google Cloud
  project, cero service account. Se adoptó después de toparse con un
  muro de verificación de facturación de Google Cloud al intentar usar
  la API de Sheets con service account.
- **`scripts/sheet_columns.py`**: `normalize()` (saca acentos/mayúsculas),
  `find_col()` (busca una columna por keywords en vez de posición/texto
  exacto), `cell()`, `parse_float()` — compartido entre
  `sync_subscribers.py` y `sync_sites.py` para que un cambio de
  redacción en una pregunta del form no rompa el parseo.
- **`scripts/github_secret.py`**: cifrado sealed-box + PUT a la API de
  Secrets de GitHub. Es la única pieza que necesita un PAT en vez del
  `GITHUB_TOKEN` automático, porque escribir un Secret (a diferencia de
  escribir un archivo del repo) requiere ese cifrado del lado cliente.
- **GitHub Pages** sirve `docs/` estático (`index.html`, `new-site.html`,
  `sites.json`) sin build step — Leaflet.js + tiles satelitales gratis de
  Esri World Imagery vía CDN.

## 6. Bugs de producción encontrados y su fix (por qué importan)

- **Push que nunca pasaba**: el paso "Persist state" tenía un
  `git diff --staged --quiet || git commit ...` seguido de un *segundo*
  chequeo idéntico antes del `push` — después del commit ya no quedaba
  nada staged, así que el segundo `git diff --staged --quiet` siempre
  cortaba antes de llegar al push. Cada corrida horaria arrancaba desde
  un estado vacío/viejo y **reenviaba mails reales cada hora**. Fix:
  un solo `if ! git diff --staged --quiet; then commit; pull --rebase;
  push; fi`. Mismo patrón usado ahora en `sync-sites.yml`.
- **Colisión de columnas por substring**: la pregunta "¿Alta,
  Modificación o Baja de Alerta?" contiene la palabra "alerta", así que
  `find_col(headers, "alerta")` (pensado para encontrar "Nombre de la
  Alerta") matcheaba primero la columna de Acción. Fix: exigir *ambas*
  keywords, `find_col(headers, "nombre", "alerta")`.
- **`KeyError: 'landing'` tumbando la corrida completa**: una capa que
  referenciaba un punto que el sitio no tiene (ej. "landing" en un sitio
  sin aterrizaje configurado) hacía un acceso de diccionario sin guardas
  en `rules.evaluate_layer`, y la excepción sin capturar mataba
  `wind-check.yml` antes de llegar a los sitios siguientes en la lista —
  dejando sin evaluar a sus suscriptores por corridas enteras. Triple
  fix: (1) `evaluate_layer` devuelve un resultado "failed" en vez de
  levantar excepción, (2) `main.py` envuelve la evaluación de cada
  suscriptor en `try/except`, (3) `sync_subscribers.py` valida el punto
  al construir la capa y la rechaza antes de que el dato malo llegue al
  secret.
- **Longitud fuera de rango al dar la vuelta al mapa**: hacer pan del
  mapa mundial más de una vuelta completa en `new-site.html` producía un
  `lng` de Leaflet fuera de `[-180, 180]` (ej. `-2231.36...`,
  matemáticamente equivalente a `-71.36...` mod 360). Fix: `.wrap()`
  sobre `e.latlng` en el handler de click antes de guardarlo.

## 7. Manual de operación (para el usuario final)

### Si sos piloto y querés recibir alertas

1. Entrá a **https://kindmartin.github.io/condition-alert/**.
2. Elegí tu sitio de vuelo en el dropdown (la lista se carga sola desde
   los sitios aprobados — si no ves el tuyo, primero hay que proponerlo,
   ver más abajo).
3. Elegí cómo querés que te avisen: mail y/o Telegram.
4. Elegí el punto de referencia (despegue o aterrizaje, según lo que
   tenga cargado ese sitio), la capa (superficie, o una altura AGL/MSL),
   y con los sliders/brújula el rango de velocidad y dirección que te
   interesa.
5. Poné un nombre a esta alerta (ej. "Alerta 1") — así podés tener varias
   alertas distintas para el mismo sitio sin que se pisen.
6. Enviá. En un plazo de hasta 15 minutos tu alerta queda activa.

**¿Cuándo te llega un mail/Telegram?** Solo cuando la condición
*cambia de estado*: te avisamos apenas aparece una ventana volable en
los próximos 3 días ("ALERT ON", con el detalle hora por hora), y de
nuevo si esa ventana deja de existir en el pronóstico ("ALERT
CLEARED"). No es un resumen diario — si la condición sigue igual (sea
que siga cumpliéndose o que siga sin cumplirse) no te llega nada nuevo,
para no generar ruido.

**Para editar una alerta**: volvé a completar el mismo formulario con el
mismo email/Telegram, mismo sitio y mismo nombre de alerta, cambiando los
valores que quieras — la nueva entrada reemplaza a la anterior automáticamente
en menos de 15 minutos.

**Para tener una segunda alerta en el mismo sitio** (por ejemplo, una
para el despegue y otra distinta para la altura): completá el formulario
de nuevo con un nombre de alerta distinto ("Alerta 2"). Cada alerta
nombrada es independiente.

**Para darte de baja de una alerta puntual**: completá el formulario de
nuevo, mismo sitio y mismo nombre de alerta, y elegí la opción de
Baja/Remover en el campo de acción. Solo se borra esa alerta — tus otras
alertas (en ese sitio u otros) siguen activas.

### Si tu sitio de vuelo no está en la lista

1. Entrá a **https://kindmartin.github.io/condition-alert/new-site.html**.
2. Marcá el punto de despegue en el mapa satelital (click para poner el
   pin). Opcionalmente activá el modo "pin de aterrizaje" y marcá también
   ese punto.
3. Usá el botón de estimación automática de elevación, o cargá el dato
   vos mismo si lo sabés con más precisión (la estimación automática es
   aproximada, verificalo si te importa la precisión).
4. Completá nombre del sitio, tu contacto y cualquier comentario útil
   para quien lo revise (ej. condiciones típicas, restricciones de
   acceso).
5. Enviá. Tu propuesta queda pendiente de revisión humana — no se activa
   sola, a diferencia de las alertas. Esto es así porque una coordenada
   mal cargada en un sitio afectaría a todos los que se suscriban ahí,
   así que alguien la revisa antes de aprobarla.
6. Una vez aprobada, el sitio aparece en el dropdown de la página de
   alertas dentro de los siguientes 15 minutos, y ya podés (o cualquiera)
   suscribirse a él.

### Advertencia general

Es un pronóstico automático (Open-Meteo) — no un reemplazo del juicio
del piloto. El techo de nubes que se muestra es una **estimación**
calculada a partir de temperatura y punto de rocío, no una medición
directa. Verificá siempre las condiciones reales en el lugar antes de
volar.
