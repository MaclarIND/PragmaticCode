#!/usr/bin/env python3
"""Puente con el buscador: convierte los leads_*.json de ../prospector.py al formato de leads/entrada/.

    python agentes/importar_leads.py             # importa los leads_*.json nuevos del repo
    python agentes/importar_leads.py --buscar    # antes corre prospector.py (necesita GOOGLE_PLACES_API_KEY)

Los archivos ya importados se anotan en leads/importados.json para no repetirlos.
"""
import glob
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun as c  # noqa: E402

AGENTE = "importar"
IMPORTADOS = os.path.join(c.BASE, "leads", "importados.json")


def dato_observable(l):
    n, rating = l.get("cantidad_resenas"), l.get("rating_google")
    if l["pais"] == "AR":
        return f"las {n} reseñas con {str(rating).replace('.', ',')} estrellas en Google" if n and rating else (l.get("descripcion") or "su ficha en Google Maps")
    return f"the {n} Google reviews with a {rating} rating" if n and rating else (l.get("descripcion") or "your Google Maps listing")


def convertir(l):
    return {"lead_id": l["id"], "nombre": l["nombre_empresa"], "rubro": l.get("rubro", ""), "pais": l["pais"],
            "email": l.get("email"), "telefono": l.get("telefono"), "tiene_web": bool(l.get("web_actual")),
            "url_web": l.get("web_actual"), "dato_observable": dato_observable(l), "zona_horaria": l.get("zona_horaria"),
            "ciudad": l.get("ciudad"), "problema_detectado": l.get("problema_detectado")}


def main(buscar=False):
    if buscar:
        r = subprocess.run([sys.executable, os.path.join(c.RAIZ, "prospector.py")], capture_output=True, text=True, cwd=c.RAIZ)
        c.log(AGENTE, "prospector: " + (r.stdout.strip().splitlines() or ["sin salida"])[-1] if r.returncode == 0 else f"prospector falló: {r.stderr.strip()[-500:]}")
    hechos = set(c.leer_json(IMPORTADOS, []) or [])
    n = 0
    for ruta in sorted(glob.glob(os.path.join(c.RAIZ, "leads_*.json"))):
        nombre = os.path.basename(ruta)
        if nombre in hechos or nombre.startswith("leads_contactados"):
            continue
        for l in (c.leer_json(ruta, {}) or {}).get("leads", []):
            c.escribir_json(os.path.join(c.LEADS_ENTRADA, f"{l['id']}.json"), convertir(l))
            n += 1
        hechos.add(nombre)
    c.escribir_json(IMPORTADOS, sorted(hechos))
    if n:
        c.log(AGENTE, f"{n} leads importados a leads/entrada/")


if __name__ == "__main__":
    main(buscar="--buscar" in sys.argv)
