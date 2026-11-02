#!/usr/bin/env python3
"""Aprobar o rechazar variantes pendientes (ofertas alternativas que propuso el Agente 2).

    python aprobar.py                 # lista las pendientes
    python aprobar.py AR-SW-A4 US-SW-A4   # las activa
    python aprobar.py --rechazar AR-SW-A5 # la desactiva (queda en el playbook con motivo_baja)

Es la única edición manual prevista del playbook: solo cambia pendiente_aprobacion / activa, nunca el texto.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "agentes"))
import comun as c  # noqa: E402
from playbook import grupos  # noqa: E402


def main(args):
    pb = c.leer_json(c.PLAYBOOK)
    rechazar = "--rechazar" in args
    ids = [a for a in args if not a.startswith("--")]
    pendientes = [(n, v) for n, vs in grupos(pb) for v in vs if v["pendiente_aprobacion"]]
    if not ids:
        if not pendientes:
            print("No hay variantes pendientes de aprobación.")
        for n, v in pendientes:
            print(f"{v['id']}  [{n}]  {v.get('mutacion') or ''}\n    {v['texto']}\n")
        return
    for n, v in pendientes:
        if v["id"] in ids:
            v["pendiente_aprobacion"] = False
            if rechazar:
                v["activa"], v["motivo_baja"] = False, f"{c.ahora().date()}: rechazada por Lucas"
            print(f"{'rechazada' if rechazar else 'aprobada'}: {v['id']} [{n}]")
            ids.remove(v["id"])
    for i in ids:
        print(f"no encontrada o no estaba pendiente: {i}")
    c.escribir_json(c.PLAYBOOK, pb)


if __name__ == "__main__":
    main(sys.argv[1:])
