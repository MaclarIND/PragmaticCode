#!/usr/bin/env python3
"""Simulación de punta a punta, sin red y sin tocar los datos reales:  python simular.py

Crea la carpeta simulacion/ (copia del playbook, leads falsos, conversaciones) y recorre hasta 45 días simulados:
venta → respuestas inventadas → seguimientos → cierre → contabilizar → podar → mutar → reporte → auditoría.
Los leads falsos responden según la variante que recibieron (las que terminan en 1 responden mucho, las que terminan
en 3 casi nada), así se ve la poda y la mutación funcionando. Los umbrales se bajan (poda a 4 envíos) para que
alcance con 50 leads.
"""
import json
import os
import random
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(AQUI, "simulacion")
shutil.rmtree(SIM, ignore_errors=True)
os.makedirs(os.path.join(SIM, "raiz"))
pb = json.load(open(os.path.join(AQUI, "playbook.json"), encoding="utf-8"))
for vs in pb["apertura"].values():          # en la simulación se prueban también las ofertas pendientes de aprobación
    for v in vs:
        v["pendiente_aprobacion"] = False
json.dump(pb, open(os.path.join(SIM, "playbook.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
os.environ.update({"SV_SIMULACION": "1", "SV_BASE": SIM, "SV_RAIZ": os.path.join(SIM, "raiz"),
                   "SV_MIN_ENVIADOS_PODA": "4", "SV_MIN_ENVIADOS_VARIANTE": "3", "SV_OFFSET_DIAS": "0"})
sys.path.insert(0, os.path.join(AQUI, "agentes"))
import comun as c  # noqa: E402
import ventas, playbook, auditor  # noqa: E402

rnd = random.Random(7)
RUBROS = {"AR": ["Peluquería", "Dentista", "Ferretería", "Pizzería", "Gimnasio"], "US": ["Plumber", "Bakery", "Dental clinic", "Auto repair", "Yoga studio"]}
DATOS = {"AR": ["las 120 reseñas con 4,8 estrellas", "que abrieron un segundo local", "las fotos del local en Maps", "que tienen 15 años en el barrio"],
         "US": ["the 200+ five-star reviews", "the new location you opened", "your photos on Google Maps", "that you've been open since 2009"]}


def leads_falsos(n=50):
    for i in range(1, n + 1):
        pais = "AR" if i % 2 else "US"
        con_web = i % 4 in (0, 3)
        lead = {"lead_id": f"SIM{i:03d}", "nombre": f"{rnd.choice(RUBROS[pais])} {['Sol', 'Norte', 'Central', 'Luna', 'Rio'][i % 5]} {i}",
                "rubro": rnd.choice(RUBROS[pais]), "pais": pais, "email": f"sim{i}@ejemplo.test", "telefono": f"+54911{i:07d}" if pais == "AR" else f"+1305{i:07d}",
                "tiene_web": con_web, "url_web": f"https://sim{i}.test" if con_web else None, "dato_observable": rnd.choice(DATOS[pais])}
        c.escribir_json(os.path.join(c.LEADS_ENTRADA, f"lead_{i:03d}.json"), lead)


RESPUESTAS = {
    "AR": {"pregunta": "¿Y ustedes qué hacen exactamente?", "interes": "¿Cuánto sale algo así?", "negativo": "No me interesa, gracias.",
           "ya_tengo_web": "Ya tengo página, la hizo mi sobrino.", "precio": "Me parece caro para lo que necesito.", "no_necesito": "No lo necesito, con Instagram me alcanza.",
           "desconfianza": "¿Quién sos? ¿De dónde sacaste mi mail?", "baja": "Baja por favor.", "pago": "Listo, ya transferí la seña."},
    "US": {"pregunta": "What exactly do you guys do?", "interes": "How much would something like that cost?", "negativo": "Not interested, thanks.",
           "ya_tengo_web": "We already have a site.", "precio": "Sounds expensive for what we need.", "no_necesito": "We don't need one right now.",
           "desconfianza": "Who are you and how did you get this email?", "baja": "Please unsubscribe me.", "pago": "Done, I just sent the deposit."},
}


def calidad(variante_id):
    """La simulación hace que las variantes terminadas en 1 funcionen bien y las terminadas en 3 mal."""
    return {"1": 0.85, "2": 0.45, "3": 0.08}.get(variante_id[-1], 0.4)


def responder(dia):
    """Los leads 'contestan' según el último mensaje del bot."""
    n = 0
    for conv in c.listar_conversaciones():
        if conv["estado"] != "abierta" or conv["mensajes"][-1]["rol"] != "bot" or conv.get("derivado"):
            continue
        ultimo = conv["mensajes"][-1]
        q = calidad(ultimo.get("variante_id") or "x2")
        if rnd.random() > q * 0.3:
            continue
        pais = conv["segmento"]["pais"]
        if ultimo["momento"] == "cierre":
            tipo = "pago" if rnd.random() < 0.5 else "negativo"
        elif ultimo["momento"] == "objecion":
            tipo = rnd.choice(["interes", "negativo", "negativo", "pregunta"])
        else:
            tipo = rnd.choices(["pregunta", "interes", "negativo", "ya_tengo_web", "precio", "no_necesito", "desconfianza", "baja"],
                               [3, 3, 2, 1, 2, 2, 1, 0.5])[0]
            if tipo == "ya_tengo_web" and not conv["segmento"]["tiene_web"]:
                tipo = "precio"
        c.escribir_json(os.path.join(c.RESPUESTAS_ENTRADA, f"r_{dia}_{conv['lead_id']}.json"),
                        {"lead_id": conv["lead_id"], "canal": "email", "texto": RESPUESTAS[pais][tipo], "ts": c.iso()})
        n += 1
    return n


def main():
    leads_falsos(50)
    print("Día 0: aperturas")
    ventas.main()
    for dia in range(1, 46):
        os.environ["SV_OFFSET_DIAS"] = str(dia)
        n = responder(dia)
        ventas.main()
        abiertas = sum(1 for x in c.listar_conversaciones() if x["estado"] == "abierta")
        print(f"Día {dia:2d}: {n:2d} respuestas · {abiertas:2d} abiertas")
        if abiertas == 0:
            break
    convs = list(c.listar_conversaciones())
    cerradas = [x for x in convs if x["estado"] == "cerrada"]
    print(f"\nConversaciones: {len(convs)} · cerradas: {len(cerradas)}")
    print("Puntajes:", {p: sum(1 for x in cerradas if x["puntaje"] == p) for p in range(5)})
    print("Motivos:", {m: sum(1 for x in cerradas if x.get("motivo_cierre") == m) for m in sorted({x.get("motivo_cierre") for x in cerradas})})

    print("\nAgente 2 (playbook)")
    playbook.main(forzar=True)
    pb = c.leer_json(c.PLAYBOOK)
    bajas = [(n, v["id"], v["tasa"]) for n, vs in playbook.grupos(pb) for v in vs if not v["activa"]]
    mutadas = [(n, v["id"], v["mutacion"]) for n, vs in playbook.grupos(pb) for v in vs if v.get("mutacion")]
    print(f"Playbook v{pb['version']} · bajas: {len(bajas)} · mutaciones: {len(mutadas)}")
    for b in bajas:
        print("  baja:", b)
    for m in mutadas:
        print("  nueva:", m)
    print("Procesadas:", sum(1 for x in c.listar_conversaciones() if x.get("procesada")), "de", len(cerradas))

    print("\nAgente 3 (auditor)")
    auditor.main()

    problemas = []
    if len(cerradas) != 50 or len(convs) != 50:
        problemas.append("no se cerraron las 50 conversaciones")
    if pb["version"] != 2:
        problemas.append("el playbook no subió de versión")
    if not bajas or not mutadas:
        problemas.append("no hubo poda o mutación (revisar umbrales)")
    if not os.listdir(c.REPORTES) or not os.listdir(c.AUDITORIAS) or not os.listdir(c.HISTORIAL):
        problemas.append("faltan reporte, auditoría o historial")
    ventas_sim = json.load(open(c.REGISTRO_VIEJO, encoding="utf-8"))
    print(f"Registro compartido (leads_contactados.json simulado): {len(ventas_sim)} entradas")
    print("\nRESULTADO:", "OK — el ciclo completo funciona" if not problemas else "PROBLEMAS: " + "; ".join(problemas))
    print(f"Todo quedó en {SIM} (se borra en la próxima corrida).")


if __name__ == "__main__":
    main()
