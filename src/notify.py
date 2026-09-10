"""Build and send the daily digest (email and/or Telegram) for a site."""
import smtplib
from email.message import EmailMessage

import requests

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def layer_label(layer, site):
    point = layer["point"]
    if layer["kind"] == "surface":
        return f"Superficie@{point}"
    if layer["kind"] == "agl":
        elevation_m = site["points"][point]["elevation_m"]
        asl = elevation_m + layer["meters"]
        return f"+{layer['meters']}m AGL@{point} (~{asl}m ASL)"
    if layer["kind"] == "msl":
        return f"{layer['meters']}m MSL"
    return layer["id"]


def format_layer_value(result):
    if result["speed_kmh"] is None:
        return "sin datos"
    text = f"{result['speed_kmh']:.0f} km/h"
    if result["direction_deg"] is not None:
        text += f" desde {result['direction_deg']:.0f}°"
    if result["gust_kmh"] is not None:
        text += f" (ráfaga {result['gust_kmh']:.0f})"
    if result["extrapolated"]:
        text += " [fuera de rango de niveles, extrapolado]"
    return text


def format_cloud_line(cloud):
    if not cloud:
        return None
    cc, cl, cm, ch = (cloud.get(k) for k in ("cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high"))
    line = f"  Nubosidad: {cc}% (baja {cl}%/media {cm}%/alta {ch}%)"
    cb = cloud.get("cloud_base_estimate_m")
    if cb is not None:
        line += f"   Techo de nubes (estimado): ~{cb}m ASL"
    fz = cloud.get("freezing_level_height_m")
    if fz is not None:
        line += f"   Isocero: {fz:.0f}m"
    return line


def build_email_body(site, date_str, qualifying_hours, layers, subscriber_name=None, alert_name=None):
    lines = []
    if subscriber_name:
        lines.append(f"Hola {subscriber_name},")
        lines.append("")
    heading = f"Ventanas de vuelo en {site['name']}"
    if alert_name:
        heading += f" — {alert_name}"
    heading += f" — {date_str} ({site.get('timezone', '')}):"
    lines.append(heading)
    lines.append("")
    for hour in qualifying_hours:
        hhmm = hour["time"].split("T")[1]
        lines.append(hhmm)
        for layer in layers:
            result = hour["layers"][layer["id"]]
            lines.append(f"  {layer_label(layer, site)}: {format_layer_value(result)}")
        cloud_line = format_cloud_line(hour.get("cloud"))
        if cloud_line:
            lines.append(cloud_line)
        lines.append("")

    lines.append("Pronóstico automático de Open-Meteo — verificá siempre las condiciones en el lugar antes de volar.")
    lines.append("— Amigo del Viento 🪂")
    return "\n".join(lines)


def subject_line(site, date_str, n_hours, alert_name=None):
    place = f"{site['name']} ({alert_name})" if alert_name else site["name"]
    return f"Amigo del Viento — {place}: {n_hours} hora(s) volable(s) el {date_str}"


def send_email(subject, body, smtp_user, smtp_password, to_addr, smtp_host="smtp.gmail.com", smtp_port=587):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def build_telegram_text(subject, body):
    return f"{subject}\n\n{body}"


def send_telegram(bot_token, chat_id, text):
    resp = requests.post(
        TELEGRAM_API_URL.format(token=bot_token),
        json={"chat_id": chat_id, "text": text},
        timeout=30,
    )
    resp.raise_for_status()
