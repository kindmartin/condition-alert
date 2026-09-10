# Condition Alert — alerta de viento para parapente

Bot que corre cada hora en GitHub Actions, consulta Open-Meteo para los sitios
definidos en [`config/sites.yaml`](config/sites.yaml), y manda un email (uno
por suscriptor por día) cuando el viento en superficie/altura cumple las
condiciones que ese suscriptor configuró.

Para una guía paso a paso de uso ver [`MANUAL.md`](MANUAL.md). Este README es
la referencia técnica más corta.

## Cómo funciona

0. Canales de aviso: mail (siempre disponible) y/o Telegram (opcional, si
   el suscriptor trae `telegram_chat_id` y está el secret
   `TELEGRAM_BOT_TOKEN`). Un suscriptor puede tener uno o ambos.
1. `.github/workflows/wind-check.yml` corre `python src/main.py` cada hora.
2. `src/fetch_forecast.py` pide a Open-Meteo el pronóstico horario (viento
   en superficie y en niveles de presión 1000-500 hPa, nubosidad) para todos
   los puntos de todos los sitios en un solo request.
3. `src/interpolate.py` calcula viento a alturas arbitrarias (ej. "+1000m
   sobre el despegue") interpolando entre niveles de presión.
4. `src/rules.py` evalúa, para cada hora del día (hora local del sitio) y
   cada suscriptor, si TODAS las capas que ese suscriptor configuró se
   cumplen a la vez.
5. Si hay al menos una hora que cumple y todavía no se le mandó mail ese día
   a ese suscriptor (`state/sent_log.json`), se manda un único digest con
   todas las horas que califican.
6. El workflow commitea `state/sent_log.json` de vuelta al repo para
   recordar qué ya se mandó (evita spam de un mail por corrida).

## Dos archivos de configuración distintos

- **`config/sites.yaml`** (público, commiteado): solo define DÓNDE están
  los sitios — coordenadas y elevación de despegue/aterrizaje. Nada
  sensible.
- **Secret `SUBSCRIBERS_JSON`** (privado, nunca commiteado): la lista real
  de quién se suscribe a qué sitio, con su email y sus propios umbrales de
  viento. Va en un secret porque el repo es público y los emails de la
  gente no deberían quedar expuestos en el código. Ver el formato en
  [`config/subscribers.example.json`](config/subscribers.example.json)
  (ese archivo es solo de referencia, con datos falsos — no se usa en
  runtime).

## Setup (una sola vez)

### 1. Gmail App Password

Necesitás verificación en 2 pasos activada en la cuenta de Gmail que va a
enviar los mails. Después generá un App Password en
https://myaccount.google.com/apppasswords (elegí "Correo"/"Otro", copiá el
password de 16 caracteres).

**No lo pegues en el chat con el asistente ni lo commitees al repo.**
Cargalo directo como secret de GitHub (ver paso 2).

### 2. Secrets del repo

Vía la web: Settings → Secrets and variables → Actions → New repository
secret, en https://github.com/kindmartin/condition-alert/settings/secrets/actions

- `GMAIL_USER`: la cuenta de Gmail que envía.
- `GMAIL_APP_PASSWORD`: el App Password del paso 1.
- `TELEGRAM_BOT_TOKEN`: opcional, solo si algún suscriptor usa Telegram
  (`telegram_chat_id`) — token generado con @BotFather.
- `SUBSCRIBERS_JSON`: el JSON completo de suscriptores (ver
  `config/subscribers.example.json` para el formato, y `MANUAL.md` para
  cómo agregar gente).

### 3. Probar

```bash
# Local, sin mandar mail ni tocar estado — imprime lo que evaluó:
pip install -r requirements.txt
export SUBSCRIBERS_JSON='{"gruenten": [...]}'   # o el contenido real
python src/main.py --dry-run

# En GitHub, manual y en modo dry-run: pestaña Actions -> Wind check ->
# Run workflow -> tildar dry_run.
```

## Limitaciones conocidas (v1)

- El "techo de nubes" es una estimación (`125 × (temp − punto de rocío)`),
  no un dato directo de Open-Meteo (que no lo expone de forma confiable).
- Un mail por suscriptor por día: si el pronóstico mejora más tarde en el
  día (después de ya haber mandado el mail), no se reenvía.
- Coordenadas de Luján y Bariloche, y el aterrizaje de Grünten, son
  aproximadas (`TBD` en `sites.yaml`) — confirmar antes de confiar en ellas.
- Agregar/sacar suscriptores requiere editar el secret `SUBSCRIBERS_JSON`
  a mano (sin self-service todavía).
