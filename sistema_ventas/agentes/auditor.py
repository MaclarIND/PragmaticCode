#!/usr/bin/env python3
"""Agente 3 — Auditor. Una vez por semana (lunes 9:00 de Buenos Aires) o a mano: python agentes/auditor.py

Lee las 20 conversaciones cerradas más recientes con puntaje 1 o 2 y escribe auditorias/auditoria_{fecha}.md.
No modifica ningún archivo del sistema.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun as c  # noqa: E402

AGENTE = "auditor"
SISTEMA = c.leer_texto(os.path.join(c.PROMPTS, "auditor.md"))


def main():
    convs = sorted((x for x in c.listar_conversaciones() if x["estado"] == "cerrada" and x["puntaje"] in (1, 2)),
                   key=lambda x: x.get("cerrada", ""))[-20:]
    if not convs:
        c.log(AGENTE, "sin conversaciones con puntaje 1 o 2 para auditar")
        return
    texto = []
    for x in convs:
        texto.append(f"### {x['lead_id']} · {x['segmento']['clave']} · {x['segmento']['canal']} · puntaje {x['puntaje']} · objeción: {x.get('objecion_detectada')}")
        texto += [f"[{m['rol']}{' ' + m['variante_id'] if m.get('variante_id') else ''}{' tipo=' + m['tipo'] if m.get('tipo') else ''}] {m['texto']}" for m in x["mensajes"]]
        texto.append("")
    salida = c.llamar_claude(SISTEMA, "Conversaciones a revisar:\n\n" + "\n".join(texto), 2500)
    if not salida:
        salida = ("_Sin API de Claude (o en simulación): esta auditoría es un marcador. Con ANTHROPIC_API_KEY el auditor "
                  "analiza las conversaciones de verdad._\n\n## Errores más repetidos\n- (pendiente)\n\n## Regla propuesta\n- (pendiente)\n\n"
                  "## Variante propuesta\n- (pendiente)")
    os.makedirs(c.AUDITORIAS, exist_ok=True)
    ruta = os.path.join(c.AUDITORIAS, f"auditoria_{c.ahora():%Y-%m-%d}.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(f"# Auditoría {c.ahora():%Y-%m-%d} — {len(convs)} conversaciones\n\n{salida.strip()}\n")
    c.log(AGENTE, f"auditoría escrita en {os.path.basename(ruta)}")


if __name__ == "__main__":
    main()
