#!/usr/bin/env python3
"""Recibe los mensajes de WhatsApp (webhook de la Meta Cloud API) y los deja en respuestas/entrada/.

    python agentes/webhook_whatsapp.py            # escucha en el puerto 8787 (WEBHOOK_PUERTO)

Meta necesita una URL pública con HTTPS: exponé el puerto con Cloudflare Tunnel o ngrok y cargá esa URL en
Meta for Developers → tu app → WhatsApp → Configuration → Webhook, con el "Verify token" igual a WEBHOOK_VERIFY_TOKEN
y suscripción al campo "messages". Solo se guardan mensajes de números que ya tienen una conversación abierta.
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun as c  # noqa: E402

AGENTE = "webhook"


def conversacion_por_numero(numero):
    digitos = re.sub(r"\D", "", numero)
    for conv in c.listar_conversaciones():
        if re.sub(r"\D", "", conv["lead"].get("telefono") or "") in (digitos, digitos[-10:]):
            return conv
    return None


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):   # silencia el log por defecto del servidor
        pass

    def do_GET(self):   # verificación inicial de Meta
        q = parse_qs(urlparse(self.path).query)
        if q.get("hub.mode") == ["subscribe"] and q.get("hub.verify_token") == [os.environ.get("WEBHOOK_VERIFY_TOKEN", "")]:
            self.send_response(200); self.end_headers(); self.wfile.write(q["hub.challenge"][0].encode())
        else:
            self.send_response(403); self.end_headers()

    def do_POST(self):
        datos = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        self.send_response(200); self.end_headers()
        for entrada in datos.get("entry", []):
            for cambio in entrada.get("changes", []):
                for m in cambio.get("value", {}).get("messages", []):
                    if m.get("type") != "text":
                        continue
                    conv = conversacion_por_numero(m.get("from", ""))
                    if not conv:
                        c.log(AGENTE, f"mensaje de {m.get('from')} sin conversación conocida, se ignora")
                        continue
                    ts = c.iso()
                    c.escribir_json(os.path.join(c.RESPUESTAS_ENTRADA, f"wa_{conv['lead_id']}_{m.get('id', '')[-12:]}.json"),
                                    {"lead_id": conv["lead_id"], "canal": "whatsapp", "texto": m["text"]["body"], "ts": ts})
                    c.log(AGENTE, f"respuesta por WhatsApp de {conv['lead_id']}")


if __name__ == "__main__":
    puerto = int(os.environ.get("WEBHOOK_PUERTO", "8787"))
    c.log(AGENTE, f"escuchando en el puerto {puerto}")
    HTTPServer(("0.0.0.0", puerto), Manejador).serve_forever()
