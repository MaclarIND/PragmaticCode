#!/usr/bin/env python3
"""Lee las respuestas de los leads del buzón (IMAP) y las deja en respuestas/entrada/ para ventas.py.

Corre antes de cada corrida de ventas (scheduler.py) o a mano: python agentes/buzon.py
Gmail: IMAP en imap.gmail.com con la misma contraseña de aplicación que el SMTP. Hay que tener IMAP habilitado
en la configuración de Gmail (Ver todos los ajustes → Reenvío y correo POP/IMAP → Habilitar IMAP).

Variables: IMAP_HOST (por defecto imap.gmail.com), IMAP_USER / IMAP_PASS (por defecto SMTP_USER / SMTP_PASS).
Solo procesa correos no leídos cuyo remitente coincide con el email de una conversación abierta; los demás los deja
como estaban. Marca como leídos los que procesó.
"""
import email
import email.policy
import imaplib
import os
import re
import sys
from email.utils import parseaddr, parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun as c  # noqa: E402

AGENTE = "buzon"


def cuerpo_texto(msg):
    parte = msg.get_body(preferencelist=("plain", "html"))
    if not parte:
        return ""
    texto = parte.get_content()
    if parte.get_content_type() == "text/html":
        texto = re.sub(r"<[^>]+>", " ", texto)
    # saca el texto citado del mensaje anterior
    lineas = []
    for l in texto.splitlines():
        if l.strip().startswith(">") or re.match(r"^(El .* escribió:|On .* wrote:|-----Original Message-----)", l.strip()):
            break
        lineas.append(l)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()


def main():
    host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    usuario = os.environ.get("IMAP_USER") or os.environ.get("SMTP_USER", "")
    clave = (os.environ.get("IMAP_PASS") or os.environ.get("SMTP_PASS", "")).replace(" ", "")
    if not usuario or not clave:
        c.log(AGENTE, "sin IMAP_USER/IMAP_PASS (ni SMTP_USER/SMTP_PASS): no se lee el buzón")
        return
    por_email = {}
    for conv in c.listar_conversaciones():
        mail = (conv["lead"].get("email") or "").lower()
        if mail:
            por_email[mail] = conv["lead_id"]
    if not por_email:
        return
    with imaplib.IMAP4_SSL(host) as imap:
        imap.login(usuario, clave)
        imap.select("INBOX")
        ok, datos = imap.search(None, "UNSEEN")
        if ok != "OK":
            return
        n = 0
        for num in datos[0].split():
            ok, partes = imap.fetch(num, "(BODY.PEEK[])")
            if ok != "OK":
                continue
            msg = email.message_from_bytes(partes[0][1], policy=email.policy.default)
            remitente = parseaddr(msg.get("From", ""))[1].lower()
            lead_id = por_email.get(remitente)
            if not lead_id:
                continue
            texto = cuerpo_texto(msg) or msg.get("Subject", "")
            try:
                ts = parsedate_to_datetime(msg.get("Date")).isoformat(timespec="seconds")
            except (TypeError, ValueError):
                ts = c.iso()
            nombre = f"email_{re.sub(r'[^A-Za-z0-9]', '', lead_id)}_{re.sub(r'[^0-9]', '', ts)[:14]}.json"
            c.escribir_json(os.path.join(c.RESPUESTAS_ENTRADA, nombre),
                            {"lead_id": lead_id, "canal": "email", "texto": texto, "ts": ts, "message_id": msg.get("Message-ID")})
            imap.store(num, "+FLAGS", "\\Seen")
            n += 1
        if n:
            c.log(AGENTE, f"{n} respuestas nuevas del buzón")


if __name__ == "__main__":
    main()
