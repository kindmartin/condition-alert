# Manual de usuario — Condition Alert

Bot que revisa el pronóstico de viento (Open-Meteo) para sitios de vuelo
cada hora, y manda un mail a cada suscriptor solo cuando se cumplen SUS
propias condiciones. Corre gratis en la nube (GitHub Actions) — no hace
falta tener ninguna PC prendida.

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
quiera; TODAS deben cumplirse a la vez para que le llegue el mail.

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
Subject: Alerta de viento: Grünten (Allgäu, DE) — 3 hora(s) volable(s) el 2026-09-14

Hola Juan,

Ventanas de vuelo en Grünten (Allgäu, DE) — 2026-09-14 (Europe/Berlin):

14:00
  Superficie@launch: 18 km/h desde 215°
  +1000m AGL@launch (~2050m ASL): 22 km/h desde 230°
  ...
  Nubosidad: 40% (baja 20%/media 30%/alta 10%)   Techo de nubes (estimado): ~1450m ASL

15:00
  ...
```

Solo muestra las capas que ESE suscriptor configuró (no las de todos).

## 4. Probarlo manualmente (sin esperar a que se cumpla una condición real)

### Opción A — desde la web de GitHub (más simple)

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
[bariloche] no qualifying hours for juan@example.com on 2026-09-14
[bariloche] WOULD SEND to maria@example.com:
Subject: Alerta de viento: Bariloche...
```

### Opción B — forzar un mail real de prueba

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

## 7. Los secrets (ya configurados)

En Settings → Secrets and variables → Actions del repo:

- `GMAIL_USER`: la cuenta de Gmail que envía los mails.
- `GMAIL_APP_PASSWORD`: el App Password de esa cuenta (no la contraseña
  normal — se genera en
  [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
- `SUBSCRIBERS_JSON`: la lista de suscriptores con sus condiciones (ver
  sección 2).

Si alguna vez se rota el App Password, solo hace falta actualizar el
secret `GMAIL_APP_PASSWORD` — no se toca código.

## 8. Problemas comunes

| Síntoma | Causa probable |
|---|---|
| No aparece "Run workflow" | Puede estar en un menú `...` a la derecha, o hay que scrollear horizontalmente en pantallas chicas. |
| El log dice "GMAIL_USER/GMAIL_APP_PASSWORD not set" | Falta cargar esos secrets, o el nombre tiene un typo. |
| `[sitio] no subscribers, skipping` | Ese `id` de sitio no tiene ninguna entrada en `SUBSCRIBERS_JSON` — es normal si nadie se anotó todavía. |
| Nunca llega mail a alguien aunque el clima esté bueno | Revisá que sus umbrales no sean demasiado estrictos, y que las coordenadas/elevación del sitio sean correctas. |
| `SUBSCRIBERS_JSON` inválido | Es JSON, no YAML — comas, comillas dobles y llaves tienen que cerrar bien. Si el workflow falla al arrancar, probablemente sea un typo ahí. |
| Llega a spam | Marcar el primer mail como "No es spam" en Gmail suele bastar; al ser el mismo remitente todos los días debería dejar de pasar rápido. |
| El workflow no corrió en la última hora | GitHub Actions en el plan gratuito puede demorar el disparo del cron unos minutos en horarios de mucha carga — es normal. |

## 9. Dónde está cada cosa (para referencia)

- Sitios (público): [`config/sites.yaml`](config/sites.yaml)
- Formato de suscriptores (ejemplo, no real): [`config/subscribers.example.json`](config/subscribers.example.json)
- Lógica del bot: [`src/`](src)
- El cron: [`.github/workflows/wind-check.yml`](.github/workflows/wind-check.yml)
- Historial de qué mails ya se mandaron: [`state/sent_log.json`](state/sent_log.json)
- Detalles técnicos para quien quiera meter mano al código: [`README.md`](README.md)
