"""Conectores de salida. Son stubs que solo loguean: acá se conectan las APIs reales.

Firmas que usa ventas.py (no cambiarlas):
    enviar_email(para, asunto, cuerpo, en_respuesta_a=None) -> str   # devuelve el Message-ID
    enviar_whatsapp(numero, texto) -> str                             # devuelve el id del mensaje

Email: el repo ya tiene un envío SMTP probado en ../contactador.py (enviar_email); para activarlo,
descomentá el bloque marcado. WhatsApp: solo por la API oficial de WhatsApp Business (Meta Cloud API)
con una plantilla aprobada para el primer mensaje; después de que el lead responde se puede escribir libre.

Entrada: las respuestas de los leads se dejan como archivos en respuestas/entrada/{cualquier_nombre}.json con
    {"lead_id": "...", "canal": "email|whatsapp", "texto": "...", "ts": "2026-11-02T10:00:00-03:00"}
El webhook de WhatsApp o el lector del buzón (IMAP) tienen que escribir esos archivos; ventas.py hace el resto.
"""
import uuid

from comun import log

MODO_REAL = False   # pasar a True cuando los conectores de abajo estén conectados


def enviar_email(para, asunto, cuerpo, en_respuesta_a=None):
    if MODO_REAL:
        # import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        # from contactador import enviar_email as smtp_enviar
        # return smtp_enviar(para, asunto, cuerpo, en_respuesta_a)
        raise NotImplementedError("Conectar el envío de email en conectores.enviar_email")
    mid = f"<stub-{uuid.uuid4().hex[:12]}@pragmatic-code.com>"
    log("conector", f"[STUB email] a {para} | asunto: {asunto} | {len(cuerpo)} caracteres | id {mid}")
    return mid


def enviar_whatsapp(numero, texto):
    if MODO_REAL:
        raise NotImplementedError("Conectar la WhatsApp Business API en conectores.enviar_whatsapp")
    mid = f"wa-stub-{uuid.uuid4().hex[:12]}"
    log("conector", f"[STUB whatsapp] a {numero} | {len(texto)} caracteres | id {mid}")
    return mid
