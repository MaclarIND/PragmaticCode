"""Conectores de salida: email por SMTP (el mismo de ../contactador.py) y WhatsApp por la API oficial de Meta.

Se activan con la variable de entorno SV_MODO_REAL=1. Sin ella, todo es un stub que solo loguea (lo que usa simular.py).

Firmas que usa ventas.py:
    enviar_email(para, asunto, cuerpo, en_respuesta_a=None) -> str      # Message-ID
    enviar_whatsapp(numero, texto) -> str                                # id del mensaje (texto libre: solo dentro de las
                                                                         #   24 hs desde el último mensaje del lead)
    enviar_whatsapp_plantilla(numero, plantilla, idioma, parametros) -> str   # apertura con plantilla aprobada por Meta

Variables de entorno:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM               (ya las usa contactador.py)
    WHATSAPP_TOKEN            token permanente de la app de Meta (System User)
    WHATSAPP_PHONE_ID         "Phone number ID" del número en WhatsApp Manager
    WHATSAPP_PLANTILLA_AR     nombre de la plantilla de apertura aprobada por Meta (opcional; si falta, las aperturas van por email)
"""
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

from comun import RAIZ, log

MODO_REAL = os.environ.get("SV_MODO_REAL") == "1"
GRAPH = "https://graph.facebook.com/v21.0"


def _stub(canal, destino, texto):
    mid = f"<stub-{uuid.uuid4().hex[:12]}@pragmatic-code.com>" if canal == "email" else f"wa-stub-{uuid.uuid4().hex[:12]}"
    log("conector", f"[STUB {canal}] a {destino} | {len(texto)} caracteres | id {mid}")
    return mid


def enviar_email(para, asunto, cuerpo, en_respuesta_a=None):
    if not MODO_REAL:
        return _stub("email", para, f"{asunto}\n{cuerpo}")
    sys.path.insert(0, RAIZ)
    from contactador import enviar_email as smtp_enviar   # SMTP con STARTTLS, contraseña de aplicación de Gmail
    mid = smtp_enviar(para, asunto, cuerpo, en_respuesta_a)
    log("conector", f"email enviado a {para} | {asunto} | {mid}")
    return mid


def _graph(payload):
    token, phone_id = os.environ.get("WHATSAPP_TOKEN", "").strip(), os.environ.get("WHATSAPP_PHONE_ID", "").strip()
    if not token or not phone_id:
        raise RuntimeError("Faltan WHATSAPP_TOKEN / WHATSAPP_PHONE_ID")
    req = urllib.request.Request(f"{GRAPH}/{phone_id}/messages", data=json.dumps(payload).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["messages"][0]["id"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"WhatsApp API {e.code}: {e.read().decode(errors='replace')[:400]}") from e


def _numero(n):
    return "".join(ch for ch in n if ch.isdigit())


PENDIENTES_WA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "whatsapp_pendientes.md")


def hay_api_whatsapp():
    return bool(os.environ.get("WHATSAPP_TOKEN", "").strip() and os.environ.get("WHATSAPP_PHONE_ID", "").strip())


def _pendiente_manual(numero, texto):
    """Sin API de Meta no hay forma permitida de enviar solo: se deja el mensaje listo con un link wa.me para mandarlo
    desde el teléfono con un toque. (Automatizar WhatsApp Web con librerías no oficiales hace que Meta bloquee el número.)"""
    from urllib.parse import quote
    link = f"https://wa.me/{_numero(numero)}?text={quote(texto)}"
    with open(PENDIENTES_WA, "a", encoding="utf-8") as f:
        f.write(f"\n## {numero}\n{texto}\n\n[Enviar desde el teléfono]({link})\n")
    log("conector", f"whatsapp a {numero} quedó en whatsapp_pendientes.md (sin API de Meta)")
    return f"wa-manual-{uuid.uuid4().hex[:12]}"


def enviar_whatsapp(numero, texto):
    if not MODO_REAL:
        return _stub("whatsapp", numero, texto)
    if not hay_api_whatsapp():
        return _pendiente_manual(numero, texto)
    mid = _graph({"messaging_product": "whatsapp", "to": _numero(numero), "type": "text",
                  "text": {"preview_url": False, "body": texto}})
    log("conector", f"whatsapp enviado a {numero} | {mid}")
    return mid


def enviar_whatsapp_plantilla(numero, plantilla, idioma, parametros):
    """Apertura por WhatsApp. Meta solo permite iniciar una conversación con una plantilla que haya aprobado."""
    if not MODO_REAL:
        return _stub("whatsapp", numero, f"[plantilla {plantilla}] " + " | ".join(parametros))
    mid = _graph({"messaging_product": "whatsapp", "to": _numero(numero), "type": "template",
                  "template": {"name": plantilla, "language": {"code": idioma},
                               "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in parametros]}]}})
    log("conector", f"whatsapp plantilla {plantilla} a {numero} | {mid}")
    return mid


def plantilla_apertura_whatsapp():
    """Nombre de la plantilla aprobada para abrir por WhatsApp en AR; None si no hay API o no está configurada."""
    return (os.environ.get("WHATSAPP_PLANTILLA_AR", "").strip() or None) if hay_api_whatsapp() else None
