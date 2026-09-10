# Condition Alert — alerta de viento para parapente

Bot que corre cada hora en GitHub Actions, consulta Open-Meteo para los sitios
definidos en [`config/sites.yaml`](config/sites.yaml), y manda un email (uno
por sitio por día) cuando el viento en superficie/altura cumple las
condiciones configuradas.

## Cómo funciona

1. `.github/workflows/wind-check.yml` corre `python src/main.py` cada hora.
2. `src/fetch_forecast.py` pide a Open-Meteo el pronóstico horario (viento
   en superficie y en niveles de presión 1000-500 hPa, nubosidad) para todos
   los puntos de todos los sitios en un solo request.
3. `src/interpolate.py` calcula viento a alturas arbitrarias (ej. "+1000m
   sobre el despegue") interpolando entre niveles de presión.
4. `src/rules.py` evalúa, para cada hora del día (hora local del sitio), si
   TODAS las capas configuradas del sitio se cumplen.
5. Si hay al menos una hora que cumple y todavía no se mandó mail ese día
   para ese sitio (`state/sent_log.json`), se manda un único digest con todas
   las horas que califican.
6. El workflow commitea `state/sent_log.json` de vuelta al repo para
   recordar qué ya se mandó (evita spam de un mail por corrida).

## Configurar un sitio nuevo

Editar [`config/sites.yaml`](config/sites.yaml) — no hace falta tocar código.
Cada sitio necesita coordenadas de despegue (y opcionalmente aterrizaje) y
una lista de capas con los umbrales de viento/dirección que te interesan.
Los valores que vienen cargados son placeholders de ejemplo: ajustalos a tu
criterio real antes de confiar en las alertas.

## Setup (una sola vez)

### 1. Gmail App Password

Necesitás verificación en 2 pasos activada en la cuenta de Gmail que va a
enviar los mails. Después generá un App Password en
https://myaccount.google.com/apppasswords (elegí "Correo"/"Otro", copiá el
password de 16 caracteres).

**No lo pegues en el chat con el asistente ni lo commitees al repo.**
Cargalo vos mismo como secret de GitHub (ver paso 2).

### 2. Secrets del repo

Corré esto vos mismo desde una terminal (te va a pedir el valor de forma
interactiva, sin mostrarlo en el historial de comandos):

```bash
gh secret set GMAIL_USER --repo <tu-usuario>/condition-alert
gh secret set GMAIL_APP_PASSWORD --repo <tu-usuario>/condition-alert
gh secret set ALERT_TO_EMAIL --repo <tu-usuario>/condition-alert
```

`ALERT_TO_EMAIL` es la dirección que recibe las alertas (ej.
`xtrail2explore@gmail.com`).

### 3. Probar

```bash
# Local, sin mandar mail ni tocar estado — imprime lo que evaluó:
pip install -r requirements.txt
python src/main.py --dry-run

# En GitHub, manual y en modo dry-run:
gh workflow run wind-check.yml -f dry_run=true
gh run watch
```

Para forzar un mail real de prueba, ensanchá temporalmente los umbrales de
un sitio en `sites.yaml` (ej. `min_speed_kmh: 0`, `max_speed_kmh: 999`, sin
`directions`) y corré `gh workflow run wind-check.yml -f dry_run=false`.
Volvé los umbrales a valores reales después.

## Limitaciones conocidas (v1)

- El "techo de nubes" es una estimación (`125 × (temp − punto de rocío)`),
  no un dato directo de Open-Meteo (que no lo expone de forma confiable).
- Un mail por sitio por día: si el pronóstico mejora más tarde en el día
  (después de ya haber mandado el mail), no se reenvía. Se puede ajustar
  en `src/main.py` más adelante si hace falta.
- Coordenadas de Luján y Bariloche, y el aterrizaje de Grünten, son
  aproximadas (`TBD` en `sites.yaml`) — confirmar antes de confiar en ellas.
