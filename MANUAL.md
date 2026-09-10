# Manual de usuario — Amigo del Viento

Revisa el pronóstico de viento (Open-Meteo) para sitios de vuelo
cada hora, y avisa a cada suscriptor (por mail y/o Telegram) solo cuando se
cumplen SUS propias condiciones. Corre gratis en la nube (GitHub Actions) —
no hace falta tener ninguna PC prendida.

## 1. Qué hace, en criollo

Cada hora, en un servidor de GitHub (no en tu compu):

1. **Busca el pronóstico** de todos los sitios configurados en un solo
   pedido a Open-Meteo — viento en superficie, en distintos niveles de
   altura, y nubosidad.
2. **Calcula el viento a las alturas que interesan** (ej. "1000m arriba
   del despegue") interpolando entre los niveles que da la API.
3. Para **cada suscriptor** de cada sitio, chequea hora por hora del día de
   hoy si TODAS las condiciones que ese suscriptor configuró se cumplen a
   la vez (viento mínimo/máximo, dirección, ráfaga máxima). Dos pilotos del
   mismo cerro pueden tener condiciones totalmente distintas.
4. Si encuentra al menos una hora que cumple, y todavía no le mandó mail
   a ese suscriptor por ese sitio hoy, **le manda un mail** con el listado
   completo de horas que califican y los valores reales.
5. Guarda en el repo a quién ya le mandó, para no repetir el mismo mail
   24 veces por hora mientras dure la ventana buena.

Al otro día (hora local del sitio), el conteo arranca de nuevo, por
suscriptor.

## 2. Dos lugares de configuración distintos

### `config/sites.yaml` (público — solo los SITIOS)

Este archivo vive en el repo, visible para cualquiera. Define únicamente
**dónde están los sitios**: coordenadas y elevación (msnm) del despegue y,
si aplica, del aterrizaje. No tiene emails ni condiciones de nadie.

```yaml
- id: gruenten
  name: "Grünten (Allgäu, DE)"
  timezone: "Europe/Berlin"
  points:
    launch:  { lat: 47.553, lon: 10.317, elevation_m: 1050 }
    landing: { lat: 47.568, lon: 10.335, elevation_m: 780 }
```

Para editar: [config/sites.yaml en GitHub](https://github.com/kindmartin/condition-alert/blob/main/config/sites.yaml)
→ lápiz (✏️) arriba a la derecha → editás → "Commit changes".

**Coordenadas marcadas `TBD`** (Luján, Bariloche, aterrizaje de Grünten)
son aproximadas — confirmalas con tus propios pines antes de confiar en
ellas.

### Secret `SUBSCRIBERS_JSON` (privado — QUIÉN y QUÉ condición)

Acá vive la lista real de suscriptores: su email, su nombre, y sus propias
capas de viento. Va en un **secret** de GitHub (no en un archivo del repo)
porque el repo es público y los emails de la gente no deberían quedar
expuestos ahí.

Formato (ver también [`config/subscribers.example.json`](config/subscribers.example.json),
que es solo de referencia con datos falsos, no se usa en runtime):

```json
{
  "gruenten": [
    {
      "name": "Juan Pérez",
      "email": "juan@example.com",
      "telegram_chat_id": 123456789,
      "layers": [
        {
          "id": "surface_launch",
          "point": "launch",
          "kind": "surface",
          "min_speed_kmh": 15,
          "max_speed_kmh": 35,
          "max_gust_kmh": 45,
          "directions": [{ "min_deg": 190, "max_deg": 260 }]
        }
      ]
    }
  ]
}
```

La clave de primer nivel (`"gruenten"`) tiene que ser el mismo `id` que el
sitio en `sites.yaml`. Cada suscriptor puede tener tantas capas como
quiera; TODAS deben cumplirse a la vez para que le llegue el aviso.

`email` y `telegram_chat_id` son ambos opcionales, pero un suscriptor
necesita **al menos uno** de los dos. Si tiene los dos, le llega por ambos
canales.

### Cómo conseguir un `telegram_chat_id`

1. (Una sola vez, lo hacés vos como admin) Creále un bot al proyecto:
   hablále a [@BotFather](https://t.me/BotFather) en Telegram, mandale
   `/newbot`, seguí las preguntas, y guardá el token que te da como el
   secret `TELEGRAM_BOT_TOKEN`.
2. Compartile a cada suscriptor el nombre de usuario del bot (ej.
   `@condition_alert_bot`) y pedile que le mande `/start`.
3. Para saber el `chat_id` de esa persona: que le hable a
   [@userinfobot](https://t.me/userinfobot), que le devuelve su ID
   numérico al instante. Ese número es el `telegram_chat_id`.

**Cómo editarlo**: Settings → Secrets and variables → Actions →
`SUBSCRIBERS_JSON` → lápiz → pegás el JSON completo actualizado → Update
secret. No hay forma de "agregar una persona" sin reescribir el JSON
entero (los secrets de GitHub no son editables parcialmente) — conviene
guardar una copia local del JSON actual (fuera del repo, o en un archivo
que esté en `.gitignore`) para no perder el historial de quién está
suscrito.

### Campos de una capa (`layers`), igual en ambos archivos

- **`kind`**: `surface` (viento a 10m), `agl` (X metros sobre el punto) o
  `msl` (X metros sobre el nivel del mar).
- **`point`**: `launch` o `landing` (el punto del sitio al que aplica).
- **`min_speed_kmh` / `max_speed_kmh`**: rango de velocidad aceptable.
- **`max_gust_kmh`**: ráfaga máxima (solo tiene sentido en `surface`).
- **`directions`**: rango(s) de grados aceptables. Si el rango cruza el
  norte (ej. de 315° a 45°) se escribe igual, el bot entiende que da la
  vuelta por el 0°. Omitir `directions` = cualquier dirección sirve.

### Ejemplos de capas listas para copiar

**Viento del NE, menos de 20 km/h, a 1000m sobre el nivel del mar:**

```json
{
  "id": "msl1000_NE",
  "point": "launch",
  "kind": "msl",
  "meters": 1000,
  "max_speed_kmh": 20,
  "directions": [{ "min_deg": 22, "max_deg": 68 }]
}
```

**Viento de superficie soplable para térmica/ladera, del SO, 10-25 km/h,
ráfaga máxima 35:**

```json
{
  "id": "surface_soarable_SW",
  "point": "launch",
  "kind": "surface",
  "min_speed_kmh": 10,
  "max_speed_kmh": 25,
  "max_gust_kmh": 35,
  "directions": [{ "min_deg": 210, "max_deg": 260 }]
}
```

**Corredor de viento en altura para travesía, 2500m MSL, del O, entre
25 y 50 km/h:**

```json
{
  "id": "msl2500_corridor_W",
  "point": "launch",
  "kind": "msl",
  "meters": 2500,
  "min_speed_kmh": 25,
  "max_speed_kmh": 50,
  "directions": [{ "min_deg": 260, "max_deg": 300 }]
}
```

## 3. Cómo se ve el mail

Un mail por suscriptor, por día, así:

```
Subject: Amigo del Viento — Grünten (Allgäu, DE): 3 hora(s) volable(s) el 2026-09-14

Hola Juan,

Ventanas de vuelo en Grünten (Allgäu, DE) — 2026-09-14 (Europe/Berlin):

14:00
  Superficie@launch: 18 km/h desde 215°
  +1000m AGL@launch (~2050m ASL): 22 km/h desde 230°
  ...
  Nubosidad: 40% (baja 20%/media 30%/alta 10%)   Techo de nubes (estimado): ~1450m ASL

15:00
  ...

Pronóstico automático de Open-Meteo — verificá siempre las condiciones en el lugar antes de volar.
— Amigo del Viento 🪂
```

Solo muestra las capas que ESE suscriptor configuró (no las de todos).

## 4. Probarlo manualmente (sin esperar a que se cumpla una condición real)

### Opción A — local, en tu propia máquina

```bash
pip install -r requirements.txt
export SUBSCRIBERS_JSON='{"gruenten": [...]}'   # el JSON real o uno de prueba
python src/main.py --dry-run
```

Imprime lo que evaluó para cada sitio/suscriptor sin mandar mail ni tocar
el estado — útil para iterar rápido en la lógica sin depender de GitHub
Actions.

### Opción B — desde la web de GitHub

1. Andá a la pestaña **[Actions](https://github.com/kindmartin/condition-alert/actions)** del repo.
2. En la barra izquierda, click en **"Wind check"**.
3. A la derecha de la franja que dice *"This workflow has a
   workflow_dispatch event trigger"* hay un botón **"Run workflow"** —
   puede estar más a la derecha de lo que se ve en pantallas chicas, o
   escondido en un menú `...`. Hacé click ahí.
4. Se abre un panel: tildá **`dry_run`**, dejá la rama en `main`, click
   **"Run workflow"**.
5. Esperá ~20-30 segundos y actualizá la página — va a aparecer una corrida
   en la lista. Hacé click en ella, después en el job (ej. "check"), y
   mirá los logs del paso **"Run wind check"**.

En modo `dry_run` el bot evalúa todo con datos reales pero **no manda mail
ni guarda estado** — solo imprime en el log qué habría hecho. Vas a ver
algo como:

```
[gruenten] no subscribers, skipping
[piltriquitron] no qualifying hours for juan@example.com on 2026-09-14
[piltriquitron] WOULD SEND to maria@example.com:
Subject: Amigo del Viento — Piltriquitrón...
```

### Opción C — forzar un mail real de prueba

1. En el secret `SUBSCRIBERS_JSON`, poné temporalmente en tu propia entrada
   `min_speed_kmh: 0`, `max_speed_kmh: 999`, y sacá `directions`. Así
   cualquier viento real va a calificar.
2. Corré el workflow de nuevo, esta vez **sin** tildar `dry_run`.
3. Revisá tu casilla — debería llegar el mail.
4. Volvé los valores a los reales (paso 1, al revés) y actualizá el secret.

## 5. Cómo funciona la frecuencia (para que no spamee)

- El workflow corre **cada hora**, automáticamente.
- Por cada suscriptor de cada sitio, mira si hoy (en el huso horario local
  del sitio) ya le mandó mail. Si ya le mandó, no vuelve a mandar aunque
  la condición se siga cumpliendo.
- Si el pronóstico mejora *después* de que ya le llegó el mail del día, no
  le llega un segundo mail actualizado — limitación conocida de esta v1.

## 6. Agregar cosas nuevas

**Un sitio nuevo** (un cerro/spot que todavía no existe): copiá un bloque
de sitio en `sites.yaml` (público), cambiale `id`, `name`, coordenadas y
elevación reales. Sin suscriptores todavía no manda nada — el bot salta
sitios sin suscriptores (`no subscribers, skipping`).

**Un suscriptor nuevo** a un sitio que ya existe: agregás su entrada
(nombre, email, capas) dentro del arreglo correspondiente en el JSON de
`SUBSCRIBERS_JSON`, y actualizás el secret completo. No requiere tocar
`sites.yaml` ni código.

## 7. Alta automática de suscriptores (Google Form)

En vez de editar `SUBSCRIBERS_JSON` a mano por cada persona, hay un
[formulario de Google](https://docs.google.com/forms/d/e/1FAIpQLSfgtBclpxaOoDpAtOivzvey36IxN9OR6SHIuXAymW0-EaLP0A/viewform)
que cualquiera puede completar (nombre, email o Telegram, sitio, y una
condición de viento). Ese es el único link que se comparte — nunca la
planilla de respuestas ni el editor del formulario.

Un workflow (`.github/workflows/sync-subscribers.yml`) corre **dos veces
por día** y:

1. Lee las respuestas de la planilla conectada al formulario.
2. Reconoce el sitio aunque la persona haya elegido la etiqueta linda del
   desplegable (ej. "cerro_otto (Bariloche)" matchea con el id `cerro_otto`).
3. Si la misma persona completó el formulario más de una vez para el mismo
   sitio, junta todas sus respuestas en un solo suscriptor con varias capas.
4. Reescribe el secret `SUBSCRIBERS_JSON` completo con el resultado — la
   planilla es la fuente de verdad; editar el secret a mano se pierde en la
   próxima sincronización.

Necesita 2 secrets adicionales (una sola vez, ver sección 8):
`SHEET_CSV_URL`, `GH_PAT_FOR_SECRETS`.

`SHEET_CSV_URL` sale de publicar la planilla como CSV: en la planilla de
respuestas, **Archivo → Compartir → Publicar en la web** → elegís la hoja
de respuestas → formato **"Valores separados por comas (.csv)"** →
Publicar. Te da una URL pública (no aparece en buscadores, pero cualquiera
que la tenga puede leerla) — copiala tal cual para el secret. Esto evita
tener que crear un proyecto de Google Cloud o cuenta de servicio.

Para forzar una sincronización manual sin esperar: pestaña Actions →
**"Sync subscribers"** → Run workflow (tildá `dry_run` para ver qué haría
sin tocar el secret todavía).

## 8. Setup completo (para levantar tu propia instancia desde cero)

Si estás armando esto para otro club/proyecto en vez de sumarte al que ya
existe, el orden es:

1. **Repo en GitHub**: forkeá o cloná este repo. Necesitás `gh` (GitHub
   CLI) autenticado y un token con permiso "Contents" + "Workflows: Read
   and write" sobre tu repo nuevo, para poder pushear código.
2. **Cuenta de Gmail para enviar** (puede ser una nueva, dedicada):
   - Activá verificación en 2 pasos: Google Account → Security → 2-Step
     Verification.
   - Generá un App Password en
     [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
     (nombre cualquiera, ej. "amigo-del-viento") → copiás el código de 16
     caracteres.
3. **Cargar los secrets básicos** en Settings → Secrets and variables →
   Actions → New repository secret: `GMAIL_USER` y `GMAIL_APP_PASSWORD`
   (los de arriba). Nunca los pegues en un chat con un asistente de IA ni
   los commitees al repo — van directo al formulario de GitHub.
4. **(Opcional) Bot de Telegram**: @BotFather → `/newbot` → guardás el
   token como secret `TELEGRAM_BOT_TOKEN`.
5. **Sitios**: editá `config/sites.yaml` con tus propios lugares (sección 2).
6. **Suscriptores**: para arrancar rápido, cargá el secret
   `SUBSCRIBERS_JSON` a mano (formato en
   [`config/subscribers.example.json`](config/subscribers.example.json)).
   Para alta automática vía formulario, seguí la sección 7 completa
   (Google Form → CSV publicado → secrets `SHEET_CSV_URL` y
   `GH_PAT_FOR_SECRETS`, este último con permiso "Secrets: Read and write"
   sobre tu repo — se crea en
   [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)).
7. **Probar** antes de confiar en que manda mails de verdad: ver sección 4.

### Los secrets (ya configurados en la instancia de kindmartin)

En Settings → Secrets and variables → Actions del repo:

- `GMAIL_USER`: la cuenta de Gmail que envía los mails.
- `GMAIL_APP_PASSWORD`: el App Password de esa cuenta (no la contraseña
  normal — se genera en
  [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
- `TELEGRAM_BOT_TOKEN`: el token del bot de Telegram (opcional — solo hace
  falta si algún suscriptor usa `telegram_chat_id`).
- `SUBSCRIBERS_JSON`: la lista de suscriptores con sus condiciones (ver
  sección 2). **Ahora la reescribe automáticamente** el workflow de
  sincronización (sección 7) — no hace falta tocarla a mano salvo para
  pruebas puntuales.
- `SHEET_CSV_URL`: la URL pública de la planilla publicada como CSV (ver
  sección 7 para cómo generarla).
- `GH_PAT_FOR_SECRETS`: un token de GitHub con permiso "Secrets: Read and
  write" sobre este repo — lo usa el workflow de sincronización para poder
  actualizar `SUBSCRIBERS_JSON` por sí mismo.

Si alguna vez se rota el App Password, solo hace falta actualizar el
secret `GMAIL_APP_PASSWORD` — no se toca código.

## 9. Problemas comunes

| Síntoma | Causa probable |
|---|---|
| No aparece "Run workflow" | Puede estar en un menú `...` a la derecha, o hay que scrollear horizontalmente en pantallas chicas. |
| El log dice "GMAIL_USER/GMAIL_APP_PASSWORD not set" | Falta cargar esos secrets, o el nombre tiene un typo. |
| `[sitio] no subscribers, skipping` | Ese `id` de sitio no tiene ninguna entrada en `SUBSCRIBERS_JSON` — es normal si nadie se anotó todavía. |
| Nunca llega mail a alguien aunque el clima esté bueno | Revisá que sus umbrales no sean demasiado estrictos, y que las coordenadas/elevación del sitio sean correctas. |
| `SUBSCRIBERS_JSON` inválido | Es JSON, no YAML — comas, comillas dobles y llaves tienen que cerrar bien. Si el workflow falla al arrancar, probablemente sea un typo ahí. |
| `TELEGRAM_BOT_TOKEN not set, skipping Telegram` | Falta cargar ese secret, o el suscriptor tiene `telegram_chat_id` pero el bot no está creado todavía. |
| No llega nada por Telegram aunque el `chat_id` esté bien | Esa persona no le mandó `/start` al bot — Telegram no deja que un bot le escriba primero a alguien. |
| Llega a spam | Marcar el primer mail como "No es spam" en Gmail suele bastar; al ser el mismo remitente todos los días debería dejar de pasar rápido. |
| El workflow no corrió en la última hora | GitHub Actions en el plan gratuito puede demorar el disparo del cron unos minutos en horarios de mucha carga — es normal. |
| `sync-subscribers` falla con error 401/403 | El `GH_PAT_FOR_SECRETS` venció, o no tiene permiso "Secrets: Read and write" sobre el repo. |
| Alguien no aparece después de completar el formulario | El sync corre solo 2 veces por día — puede tardar hasta 12hs. Para probar ya, corré el workflow manual (sección 7). |

## 10. Dónde está cada cosa (para referencia)

- Sitios (público): [`config/sites.yaml`](config/sites.yaml)
- Formato de suscriptores (ejemplo, no real): [`config/subscribers.example.json`](config/subscribers.example.json)
- Lógica del chequeo de viento, un archivo por responsabilidad:
  - [`src/fetch_forecast.py`](src/fetch_forecast.py): arma un solo request batcheado a Open-Meteo para todos los puntos de todos los sitios.
  - [`src/interpolate.py`](src/interpolate.py): calcula viento a alturas arbitrarias interpolando entre niveles de presión.
  - [`src/rules.py`](src/rules.py): evalúa las capas de un suscriptor contra el pronóstico, hora por hora.
  - [`src/notify.py`](src/notify.py): arma y manda el mail/Telegram.
  - [`src/state.py`](src/state.py): lleva el registro de a quién ya se le mandó, para el dedup.
  - [`src/main.py`](src/main.py): orquesta todo lo anterior, es lo que corre el cron cada hora.
- El cron de viento: [`.github/workflows/wind-check.yml`](.github/workflows/wind-check.yml)
- El cron de sincronización: [`.github/workflows/sync-subscribers.yml`](.github/workflows/sync-subscribers.yml), lógica en [`scripts/`](scripts)
- Historial de qué mails ya se mandaron: [`state/sent_log.json`](state/sent_log.json)
- Intro general (para quien no va a operar el bot, solo usarlo): [`README.md`](README.md)

## 11. Limitaciones conocidas (v1)

- El "techo de nubes" es una estimación (`125 × (temp − punto de rocío)`),
  no un dato directo de Open-Meteo (que no lo expone de forma confiable).
- Un mail por suscriptor por día: si el pronóstico mejora más tarde en el
  día (después de ya haber mandado el mail), no se reenvía.
- Coordenadas del aterrizaje de Grünten son aproximadas (`TBD` en
  `sites.yaml`) — confirmar antes de confiar en ellas.
- Agregar/sacar sitios sigue requiriendo editar `sites.yaml` a mano
  (commit al repo); solo los suscriptores tienen alta automática.
