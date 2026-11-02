#!/usr/bin/env python3
"""Scheduler: python scheduler.py   (dejarlo corriendo; Ctrl+C para parar)

- Agente 1 (ventas):   cada 15 minutos.
- Agente 2 (playbook): chequeo cada hora; ejecuta solo si hay 30 cerradas sin procesar o pasaron 7 días.
- Agente 3 (auditor):  lunes 9:00 (America/Argentina/Buenos_Aires).
Cada corrida queda en logs/AAAA-MM-DD.log. Si un agente falla, se loguea y el scheduler sigue.
"""
import datetime as dt
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "agentes"))
import comun as c  # noqa: E402

ESTADO = os.path.join(c.LOGS, "estado_scheduler.json")


def correr(agente):
    c.log("scheduler", f"→ {agente}")
    r = subprocess.run([sys.executable, os.path.join(BASE, "agentes", f"{agente}.py")], capture_output=True, text=True)
    if r.returncode != 0:
        c.log("scheduler", f"{agente} falló:\n{r.stderr.strip()[-2000:]}")


def main():
    os.makedirs(c.LOGS, exist_ok=True)
    estado = c.leer_json(ESTADO, {}) or {}
    c.log("scheduler", "arrancó")
    while True:
        ahora = time.time()
        if ahora - estado.get("ventas", 0) >= 15 * 60:
            correr("ventas"); estado["ventas"] = ahora
        if ahora - estado.get("playbook", 0) >= 60 * 60:
            correr("playbook"); estado["playbook"] = ahora
        local = dt.datetime.now(ZoneInfo(c.TZ_AR))
        hoy = local.date().isoformat()
        if local.weekday() == 0 and local.hour >= 9 and estado.get("auditor_fecha") != hoy:
            correr("auditor"); estado["auditor_fecha"] = hoy
        c.escribir_json(ESTADO, estado)
        time.sleep(60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        c.log("scheduler", "detenido")
