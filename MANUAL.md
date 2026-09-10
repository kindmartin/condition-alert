# Manual de usuario — Condition Alert

Bot que revisa el pronóstico de viento (Open-Meteo) para tus sitios de vuelo
cada hora, y te manda un mail solo cuando se cumplen las condiciones que vos
definiste. Corre gratis en la nube (GitHub Actions) — no necesitás tener
ninguna PC prendida.

## 1. Qué hace, en criollo

Cada hora, en un servidor de GitHub (no en tu compu):

1. **Busca el pronóstico** de todos los sitios configurados en un solo
   pedido a Open-Meteo — viento en superficie, en distintos niveles de
   altura, y nubosidad.
2. **Calcula el viento a las alturas que te interesan** (ej. "1000m arriba
   del despegue") interpolando entre los niveles que da la API.
3. **Chequea, hora por hora del día de hoy**, si TODAS las condiciones que
   configuraste para ese sitio se cumplen a la vez (viento mínimo/máximo,
   dirección, ráfaga máxima).
4. Si encuentra al menos una hora que cumple, y todavía no te mandó mail
   por ese sitio hoy, **te manda un mail** con el listado completo de horas
   que califican y los valores reales (para que puedas chequear vos mismo).
5. Guarda en el repo qué ya mandó, para no mandarte el mismo mail 24 veces
   por hora mientras dure la ventana buena.

Al otro día (hora local del sitio), el conteo arranca de nuevo.

## 2. El archivo que vas a tocar vos: `config/sites.yaml`

Ahí vive todo lo que podés cambiar sin programar nada. Por cada sitio:

- **`points`**: coordenadas y elevación (msnm) del despegue y, si aplica,
  del aterrizaje.
- **`layers`**: la lista de capas a chequear. Cada capa dice:
  - **`kind`**: `surface` (viento a 10m), `agl` (X metros sobre el punto)
    o `msl` (X metros sobre el nivel del mar).
  - **`min_speed_kmh` / `max_speed_kmh`**: rango de velocidad aceptable.
  - **`max_gust_kmh`**: ráfaga máxima (solo tiene sentido en `surface`).
  - **`directions`**: rango(s) de grados aceptables. Si el rango cruza el
    norte (ej. de 315° a 45°) se escribe igual, el bot entiende que da la
    vuelta por el 0°.
- **`logic: all`**: significa que TODAS las capas del sitio tienen que
  cumplirse en la misma hora. Es el único modo soportado por ahora.

**Los valores que están cargados hoy son de ejemplo** — ajustalos a tu
criterio real de piloto antes de confiar en las alertas. También hay
coordenadas marcadas `TBD` (Luján, Bariloche, aterrizaje de Grünten) que son
aproximadas — confirmalas con tus propios pines antes de usarlas en serio.

Para editar: entrás a
[config/sites.yaml en GitHub](https://github.com/kindmartin/condition-alert/blob/main/config/sites.yaml),
click en el lápiz (✏️) arriba a la derecha, editás, y "Commit changes"
abajo. No hace falta instalar nada ni escribir código.

## 3. Cómo se ve el mail

Un mail por sitio, por día, así:

```
Subject: Alerta de viento: Grünten (Allgäu, DE) — 3 hora(s) volable(s) el 2026-09-14

Ventanas de vuelo en Grünten (Allgäu, DE) — 2026-09-14 (Europe/Berlin):

14:00
  Superficie@launch: 18 km/h desde 215°
  Superficie@landing: 9 km/h desde 230°
  +1000m AGL@launch (~2050m ASL): 22 km/h desde 230°
  ...
  Nubosidad: 40% (baja 20%/media 30%/alta 10%)   Techo de nubes (estimado): ~1450m ASL

15:00
  ...
```

Te llega a la dirección que configuraste en el secret `ALERT_TO_EMAIL`.

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
[gruenten] no qualifying hours for 2026-09-14
[bariloche] WOULD SEND:
Subject: Alerta de viento: Bariloche...
```

### Opción B — forzar un mail real de prueba

1. Editá temporalmente un sitio en `sites.yaml`: poné `min_speed_kmh: 0`,
   `max_speed_kmh: 999`, y borrá o comentá la sección `directions` de sus
   capas. Así cualquier viento real va a calificar.
2. Corré el workflow de nuevo, esta vez **sin** tildar `dry_run`.
3. Revisá la casilla de `ALERT_TO_EMAIL` — debería llegar el mail.
4. Volvé los valores a los reales (paso 1, pero al revés) y commiteá.

## 5. Cómo funciona la frecuencia (para que no te spamee)

- El workflow corre **cada hora**, automáticamente, sin que hagas nada.
- Por cada sitio, mira si hoy (en su huso horario local) ya te mandó mail.
  Si ya te mandó, no vuelve a mandar aunque la condición se siga
  cumpliendo.
- Si el pronóstico mejora *después* de que ya te llegó el mail del día,
  no te llega un segundo mail actualizado — es una limitación conocida de
  esta v1 (documentada en el [README](README.md)).

## 6. Agregar un sitio nuevo

Copiá el bloque de un sitio existente en `sites.yaml`, cambiale el `id`
(único, sin espacios), el `name`, las coordenadas/elevación reales de
despegue (y aterrizaje si aplica), y las capas que te interesen. No hace
falta tocar nada más — el bot lee todos los sitios listados
automáticamente en la próxima corrida horaria.

## 7. Los secrets (ya configurados)

En Settings → Secrets and variables → Actions del repo:

- `GMAIL_USER`: la cuenta de Gmail que envía los mails.
- `GMAIL_APP_PASSWORD`: el App Password de esa cuenta (no tu contraseña
  normal — se genera en
  [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
- `ALERT_TO_EMAIL`: a dónde llegan las alertas.

Si alguna vez rotás el App Password, solo hace falta actualizar el secret
`GMAIL_APP_PASSWORD` — no se toca código.

## 8. Problemas comunes

| Síntoma | Causa probable |
|---|---|
| No aparece "Run workflow" | Puede estar en un menú `...` a la derecha, o hay que scrollear horizontalmente en pantallas chicas. |
| El log dice "GMAIL_USER/GMAIL_APP_PASSWORD not set" | Falta cargar esos secrets, o el nombre tiene un typo. |
| Nunca llega mail aunque el clima esté bueno | Revisá que los umbrales de `sites.yaml` no sean demasiado estrictos, y que las coordenadas/elevación del sitio sean correctas. |
| Llega a spam | Marcá el primer mail como "No es spam" en Gmail; al ser el mismo remitente todos los días debería dejar de pasar rápido. |
| El workflow no corrió en la última hora | GitHub Actions en el plan gratuito puede demorar el disparo del cron unos minutos en horarios de mucha carga — es normal, no hay que hacer nada. |

## 9. Dónde está cada cosa (para referencia)

- Configuración de sitios: [`config/sites.yaml`](config/sites.yaml)
- Lógica del bot: [`src/`](src)
- El cron: [`.github/workflows/wind-check.yml`](.github/workflows/wind-check.yml)
- Historial de qué mails ya se mandaron: [`state/sent_log.json`](state/sent_log.json)
- Detalles técnicos para quien quiera meter mano al código: [`README.md`](README.md)
