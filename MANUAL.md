# Manual de usuario — Amigo del Viento

Revisa el pronóstico de viento (Open-Meteo) para sitios de vuelo
cada hora, y avisa a cada suscriptor (por mail y/o Telegram) solo cuando se
cumplen SUS propias condiciones. Corre gratis en la nube (GitHub Actions) —
no hace falta tener ninguna PC prendida.

## 1. Qué hace, en criollo

Cada hora, en un servidor de GitHub (no en tu compu):

1. **Busca el pronóstico** de todos los sitios configurados en un solo
   pedido a Open-Meteo — viento en superficie, en distintos niveles de
   altura, y nubosidad, para los próximos **3 días** (ventana móvil: como
   corre cada hora, esos 3 días siempre están "desde ahora" en adelante).
2. **Calcula el viento a las alturas que interesan** (ej. "1000m arriba
   del despegue") interpolando entre los niveles que da la API.
3. Para **cada alerta** de cada suscriptor de cada sitio, chequea hora por
   hora de esos 3 días si TODAS las capas de ESA alerta se cumplen a la vez
   (viento mínimo/máximo, dirección, ráfaga máxima). Una persona puede
   tener varias alertas independientes en el mismo sitio (sección 2) — se
   evalúan por separado, no hace falta que todas se cumplan juntas.
4. Cada alerta tiene un estado **prendida/apagada** (guardado en el repo).
   Solo manda aviso cuando ese estado **cambia**:
   - Estaba apagada y aparece al menos una hora que cumple → la prende y
     manda el mail/Telegram con el listado completo de horas que califican.
   - Estaba prendida y ya no queda ninguna hora que cumpla en los próximos
     3 días → la apaga y manda un aviso de "la condición ya no está
     disponible".
   - Si no cambió nada (sigue prendida o sigue apagada), no manda nada —
     así no repite el mismo aviso cada hora mientras dure la ventana buena,
     pero SÍ te entera cuando una ventana que ya tenías confirmada se cae.

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
      "alert_name": "Alerta 1",
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
sitio en `sites.yaml`. Cada entrada de la lista es **una alerta** (no
necesariamente una persona distinta): todas sus capas deben cumplirse a la
vez (Y) para que le llegue el aviso de esa alerta puntual.

`email` y `telegram_chat_id` son ambos opcionales, pero un suscriptor
necesita **al menos uno** de los dos. Si tiene los dos, le llega por ambos
canales.

### Varias alertas independientes en el mismo sitio

La misma persona (mismo email o `telegram_chat_id`) puede aparecer más de
una vez en la lista de un sitio, cada vez con un `alert_name` distinto
(ej. `"Alerta 1"`, `"Alerta 2"`) y sus propias capas. Cada una se evalúa
por separado — si CUALQUIERA de sus alertas se cumple, recibe un aviso
identificando cuál (O entre alertas, Y adentro de cada una). Así una
persona puede pedir, por ejemplo, "avisame si sopla suave para térmica" Y
por separado "avisame si sopla fuerte para travesía", sin que una
condición interfiera con la otra. Ver el ejemplo completo en
[`config/subscribers.example.json`](config/subscribers.example.json).

`alert_name` es opcional — si se omite, esa persona tiene una sola alerta
"sin nombre" en ese sitio (comportamiento de antes de que existiera esta
función).

**Ejemplo real de cómo se combinan dos envíos del formulario** (esto pasó
de verdad probando el sistema):

| Envío | Sitio | Nombre de la Alerta | Tipo Referencia | Tipo de capa |
|---|---|---|---|---|
| 1 | Vicente López | Alerta 1 | Despegue | surface |
| 2 | Vicente López | Alerta 1 | **Aterrizaje** | surface |

Como los dos comparten sitio + nombre de alerta, van al mismo grupo — pero
como el **Tipo Referencia difiere** (despegue vs aterrizaje), no es "la
misma capa reeditada", es una capa distinta. Resultado: **"Alerta 1" queda
con 2 capas** (viento en despegue Y viento en aterrizaje, ambas tienen que
cumplirse a la vez). Si el segundo envío hubiera puesto "Despegue" de
nuevo (igual que el primero), el resultado habría sido reemplazar la
capa 1 por la 2, no sumarlas.

En criollo: **para editar una capa, repetí exactamente el mismo Tipo
Referencia + Tipo de capa + Metros que la vez anterior.** Si cambiás
cualquiera de esos tres, es una capa nueva que se agrega a la alerta.

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

### Editar o darse de baja (self-service, vía el mismo formulario)

El formulario tiene dos preguntas clave para esto: **"Alta, Modificación o
Baja"** y **"Nombre de la Alerta"** (`Alerta 1`/`Alerta 2`/`Alerta 3`, para
distinguir cuál de tus alertas en ese sitio estás tocando si tenés más de
una — ver "Varias alertas independientes" en la sección 2).

- **Nueva Alerta / Reconfigurar una Alerta previa**: si volvés a completar
  el formulario para el mismo sitio + mismo nombre de alerta + mismo tipo
  de capa (mismo `kind`+`point`+`metros`), la sincronización **reemplaza**
  esa condición por la nueva — así se edita, no se acumula. Si es una capa
  distinta dentro de la misma alerta (otra altura, otro punto), se agrega
  al lado de las que ya tenía esa alerta.
- **Remover Alerta**: en la próxima sincronización se borran todas las
  capas de ESA alerta puntual (identificada por sitio + nombre de alerta)
  — tus otras alertas en ese sitio, si tenés, quedan intactas. Para volver
  a sumarla alcanza con completar el form de nuevo con "Nueva Alerta" y el
  mismo nombre.

Esto lo resuelve automáticamente `scripts/sync_subscribers.py` procesando
las respuestas en el orden en que llegaron (la última gana). No hace falta
tocar la planilla ni el secret a mano para editar o dar de baja a alguien.

### Editar el secret a mano (excepcional)

Para casos puntuales (o si el formulario no tiene la pregunta "Acción"
todavía): Settings → Secrets and variables → Actions → `SUBSCRIBERS_JSON`
→ lápiz → pegás el JSON completo actualizado → Update secret. Ojo: la
próxima sincronización automática (sección 7) **reescribe esto** con lo
que diga la planilla en ese momento — un cambio manual no sobrevive al
siguiente sync si la planilla dice otra cosa.

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

Hay dos tipos de aviso — mirá la sección 1 para cuándo se manda cada uno.

**Cuando una alerta se prende** (aparece una ventana que antes no estaba):

```
Subject: Amigo del Viento — Grünten (Allgäu, DE): 5 hora(s) volable(s) en los próximos días

Hola Juan,

Ventanas de vuelo en Grünten (Allgäu, DE) (Europe/Berlin):

== 2026-09-14 ==
14:00
  Superficie@launch: 18 km/h desde 215°
  +1000m AGL@launch (~2050m ASL): 22 km/h desde 230°
  ...
  Nubosidad: 40% (baja 20%/media 30%/alta 10%)   Techo de nubes (estimado): ~1450m ASL

15:00
  ...

== 2026-09-15 ==
11:00
  ...

Pronóstico automático de Open-Meteo — verificá siempre las condiciones en el lugar antes de volar.
Te vamos a avisar de nuevo si esta condición deja de cumplirse y después vuelve a darse.
— Amigo del Viento 🪂
```

Como la ventana puede caer en distintos días (mira hasta 3 días adelante),
cada bloque de fecha (`== YYYY-MM-DD ==`) agrupa las horas de ese día.

**Cuando una alerta se apaga** (la ventana que tenías confirmada desapareció):

```
Subject: Amigo del Viento — Grünten (Allgäu, DE): la condición ya no está disponible

Hola Juan,

La condición de tu alerta en Grünten (Allgäu, DE) ya no se cumple en el pronóstico de los próximos días.
Te avisamos de nuevo apenas vuelva a darse.

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
[piltriquitron] juan@example.com#Alerta 1: sin cambio (on=False)
[piltriquitron] WOULD SEND (ALERT ON) to maria@example.com#Alerta 1:
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

- El workflow corre **cada hora**, automáticamente, y mira una ventana
  móvil de **3 días hacia adelante** (no solo "hoy").
- Cada alerta tiene un estado prendida/apagada guardado en
  `state/sent_log.json`. Solo se manda aviso cuando ese estado **cambia**
  (ver sección 1) — mientras siga prendida (la ventana se mantiene) o
  siga apagada (nada calificó), no manda nada nuevo.
- Si la ventana que ya tenías confirmada desaparece del pronóstico (el
  clima cambió), te llega un aviso de "condición ya no disponible" — no
  te quedás pensando que todavía va a andar.
- Si después de apagarse vuelve a aparecer una ventana (mismo día u otro,
  dentro de los 3 que mira), se prende de nuevo y te llega un aviso nuevo.

## 6. Agregar cosas nuevas

**Un sitio nuevo** (un cerro/spot que todavía no existe): copiá un bloque
de sitio en `sites.yaml` (público), cambiale `id`, `name`, coordenadas y
elevación reales. Sin suscriptores todavía no manda nada — el bot salta
sitios sin suscriptores (`no subscribers, skipping`).

**Un suscriptor nuevo** a un sitio que ya existe: agregás su entrada
(nombre, email, capas) dentro del arreglo correspondiente en el JSON de
`SUBSCRIBERS_JSON`, y actualizás el secret completo. No requiere tocar
`sites.yaml` ni código.

## 7. Alta automática de suscriptores

Hay dos "puertas de entrada" para que alguien se anote — las dos terminan
en la MISMA planilla de respuestas, así que se pueden usar indistintamente
o incluso las dos a la vez:

### Opción A — página propia (recomendada)

[`docs/index.html`](docs/index.html), pensada para ser mucho más fácil de
usar que un formulario genérico:

- Mapa satelital (Esri) centrado en el punto exacto del sitio elegido,
  con zoom a nivel de ~100m.
- Solo ofrece "Aterrizaje" como punto de referencia si ese sitio
  realmente tiene uno configurado (evita el bug que crasheó producción
  con Vicente López, sección 9).
- Selector visual (compás) para definir el cono de dirección, dibujado
  también como cuña sobre el mapa.
- Sliders para velocidad mínima/máxima.

Para que funcione hace falta desplegarla una vez (ver "Setup de la página
propia" más abajo). El link que se comparte con la gente es el de GitHub
Pages, ej. `https://kindmartin.github.io/condition-alert/`.

### Opción B — Google Form

El [formulario de Google](https://forms.gle/gz4qX5SmnnXAXsAD6) original,
más simple de mantener pero con la interfaz genérica de Google. Sigue
funcionando igual que siempre.

### Cómo se procesan las respuestas (igual para las dos opciones)

Un workflow (`.github/workflows/sync-subscribers.yml`, en `scripts/sync_subscribers.py`)
corre **cada 15 minutos** y:

1. Lee las respuestas de la planilla conectada al formulario.
2. Reconoce el sitio aunque la persona haya elegido la etiqueta linda del
   desplegable, con matching flexible que ignora mayúsculas, acentos,
   espacios y guiones — "Vicente Lopez" y "Vicente Lopez (Buenos Aires)"
   matchean igual con el id `vicente_lopez`, porque el segundo texto
   *contiene* al primero (ver `loose()` en `scripts/sync_subscribers.py`
   si querés el detalle).
3. Agrupa las respuestas por **sitio + persona + nombre de alerta**
   (sección 2) — no junta todo lo de una persona en un sitio en una sola
   alerta, respeta las alertas separadas.
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

### Setup de la página propia (una sola vez)

1. **Habilitar GitHub Pages**: Settings → Pages → Source: "Deploy from a
   branch" → Branch: `main`, carpeta `/docs` → Save. GitHub te da la URL
   (ej. `https://kindmartin.github.io/condition-alert/`) — puede tardar
   uno o dos minutos en estar disponible la primera vez.
2. **Desplegar el Apps Script**: abrí la planilla de respuestas → menú
   **Extensions → Apps Script** → borrá el contenido de `Code.gs` y pegá
   entero [`docs/apps_script.gs`](docs/apps_script.gs) → **Deploy → New
   deployment** → tipo **"Web app"** → Execute as: **Me**, Who has
   access: **Anyone** → Deploy. Te da una URL que termina en `/exec`
   — copiala.
3. **Conectar la página con el script**: editá
   [`docs/index.html`](docs/index.html), buscá la línea
   `const APPS_SCRIPT_URL = "PEGAR_ACA...`, reemplazá el valor por la URL
   del paso 2, y commiteá/pusheá el cambio.
4. Probá completando la página vos mismo y confirmá que aparece la fila
   nueva en la planilla de respuestas.

Si alguna vez agregás un sitio nuevo en `config/sites.yaml`, acordate de
sumarlo también al arreglo `SITES` dentro de `docs/index.html` (son datos
duplicados a propósito, para que la página no dependa de leer YAML en el
navegador).

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
| `Wind check` falla con `KeyError` de un nombre de punto (ej. `'landing'`) | Alguien eligió "Aterrizaje" en un sitio que solo tiene despegue configurado en `sites.yaml`. El sync ya descarta esas capas inválidas automáticamente (no debería volver a pasar), pero si ves esto en un secret cargado a mano, revisá que el `point` de cada capa exista en los `points` del sitio. |
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
- Si la ventana se achica o se agranda pero sigue habiendo al menos una
  hora que califica, no se manda un mail actualizado con el detalle nuevo
  — solo se avisa en las transiciones prendida/apagada (sección 5), no en
  cada cambio de horario dentro de una ventana que sigue activa.
- Coordenadas del aterrizaje de Grünten son aproximadas (`TBD` en
  `sites.yaml`) — confirmar antes de confiar en ellas.
- Agregar/sacar sitios sigue requiriendo editar `sites.yaml` a mano
  (commit al repo); solo los suscriptores tienen alta automática.
