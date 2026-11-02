#!/usr/bin/env python3
"""Agente 2 — Playbook. Único que escribe playbook.json.

Corre cuando hay 30 conversaciones cerradas sin procesar, o cada 7 días (scheduler.py lo chequea cada hora).
    python agentes/playbook.py            # corre solo si se cumple la condición
    python agentes/playbook.py --forzar   # corre igual

Pasos 1 (contabilizar), 2 (podar) y la selección de qué mutar son código puro. La redacción de la mutación
(paso 3), las categorías nuevas (paso 4) y las ofertas alternativas (paso 5) usan el modelo; sin API usan un
respaldo determinista para que simular.py cierre el ciclo.
"""
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun as c  # noqa: E402

AGENTE = "playbook"
SISTEMA = c.leer_texto(os.path.join(c.PROMPTS, "playbook.md"))
MAX_MUTACIONES = 3


def grupos(pb):
    """Recorre todos los grupos (momento × segmento) como (nombre, lista_de_variantes)."""
    for seg, vs in pb["apertura"].items():
        yield f"apertura/{seg}", vs
    for seg, vs in pb["seguimiento_sin_respuesta"].items():
        yield f"seguimiento/{seg}", vs
    for cat, segs in pb["objeciones"].items():
        for seg, vs in segs.items():
            yield f"objecion:{cat}/{seg}", vs
    for seg, vs in pb["cierre"].items():
        yield f"cierre/{seg}", vs


def indice(pb):
    return {v["id"]: v for _, vs in grupos(pb) for v in vs}


def nuevo_id(grupo):
    base = max((v["id"] for v in grupo), key=lambda i: (len(i), i))
    m = re.match(r"(.*?)(\d+)$", base)
    return f"{m.group(1)}{int(m.group(2)) + 1}" if m else base + "-2"


def variante_nueva(grupo, texto, canal, mutacion=None, pendiente=False):
    return {"id": nuevo_id(grupo), "texto": texto, "canal": canal, "enviados": 0, "puntos": 0, "tasa": 0.0, "activa": True,
            "mutacion": mutacion, "creada": c.ahora().date().isoformat(), "motivo_baja": None, "pendiente_aprobacion": pendiente}


# ---------- 1. contabilizar ----------
def contabilizar(pb, cerradas):
    idx, por_segmento = indice(pb), {}
    for conv in cerradas:
        seg = conv["segmento"]["clave"]
        por_segmento[seg] = por_segmento.get(seg, 0) + 1
        for vid in {m["variante_id"] for m in conv["mensajes"] if m["rol"] == "bot" and m.get("variante_id")}:
            v = idx.get(vid)
            if v:
                v["enviados"] += 1
                v["puntos"] += conv["puntaje"] or 0
                v["tasa"] = round(v["puntos"] / v["enviados"], 3)
        conv["procesada"] = True
        c.escribir_json(os.path.join(c.CONVERSACIONES, f"{conv['lead_id']}.json"), conv)
    return por_segmento


# ---------- 2. podar ----------
def podar(pb):
    bajas = []
    for nombre, vs in grupos(pb):
        maduras = [v for v in vs if v["activa"] and not v["pendiente_aprobacion"] and v["enviados"] >= c.MIN_ENVIADOS_PODA]
        if len(maduras) < 2:
            continue
        mejor = max(v["tasa"] for v in maduras)
        for v in sorted(maduras, key=lambda v: v["tasa"]):
            activas = sum(1 for x in vs if x["activa"] and not x["pendiente_aprobacion"])
            if activas <= 2:
                break   # nunca dejar un grupo con menos de 2 activas
            if v["tasa"] < mejor / 2:
                v["activa"] = False
                v["motivo_baja"] = f"{c.ahora().date()}: tasa {v['tasa']} < mitad de la mejor del grupo ({mejor})"
                bajas.append((nombre, v))
    return bajas


# ---------- 3. mutar ----------
DIMENSIONES = ("gancho", "largo", "pregunta final", "tono", "orden de las ideas")


def mutar(pb, bajas):
    mutaciones = []
    for n, (nombre, baja) in enumerate(bajas[:MAX_MUTACIONES]):
        vs = dict(grupos(pb))[nombre]
        base = max((v for v in vs if v["activa"] and not v["pendiente_aprobacion"]), key=lambda v: v["tasa"])
        dim = DIMENSIONES[(len(vs) + n) % len(DIMENSIONES)]
        salida = c.extraer_json(c.llamar_claude(SISTEMA, (
            f'Tarea "mutar". Grupo: {nombre}. Canal: {base["canal"]}.\nVariante base (la mejor del grupo):\n{base["texto"]}\n'
            f"Cambiá exactamente una cosa: {dim}. Variantes que ya existen en el grupo (no las repitas):\n"
            + "\n".join("- " + v["texto"] for v in vs)), 500))
        if salida and salida.get("texto"):
            texto, mut = salida["texto"].strip(), salida.get("mutacion") or dim
        else:   # respaldo sin modelo: cambia la pregunta final
            partes = base["texto"].rsplit("?", 1)
            cola = " ¿Te lo cuento en dos líneas?" if nombre.split("/")[1].startswith("AR") else " Worth two lines on it?"
            texto, mut = (partes[0].rsplit(".", 1)[0] + "." + cola) if "." in partes[0] else base["texto"] + cola, "pregunta final (respaldo sin modelo)"
        nueva = variante_nueva(vs, texto, base["canal"], mutacion=f"desde {base['id']}: {mut}")
        vs.append(nueva)
        mutaciones.append((nombre, baja["id"], nueva))
    return mutaciones


# ---------- 4. huecos ----------
def huecos(pb, cerradas):
    sueltas = [conv["objecion_detectada"] for conv in cerradas
               if conv["puntaje"] == 1 and conv.get("objecion_detectada") and conv["objecion_detectada"] not in pb["objeciones"]]
    if len(sueltas) < 5:
        return []
    salida = c.extraer_json(c.llamar_claude(SISTEMA, (
        'Tarea "categoria". Estas objeciones no encajan en ya_tengo_web / precio / no_necesito / desconfianza:\n'
        + "\n".join("- " + s for s in sueltas[:40]) + "\nDefiní UNA categoría nueva y 2 variantes de respuesta por segmento."), 1500))
    if not salida or not salida.get("nombre") or not isinstance(salida.get("variantes"), dict):
        nombre = "otra_" + c.ahora().strftime("%Y%m%d")
        salida = {"nombre": nombre, "variantes": {seg: [
            "Entiendo. ¿Qué tendría que tener una web para que te sirva de verdad?" if seg.startswith("AR") else
            "Understood. What would a website need to have to be genuinely useful to you?",
            "Entiendo. ¿Querés que lo dejemos acá o te mando un ejemplo de tu rubro?" if seg.startswith("AR") else
            "Understood. Should we leave it here, or can I send one example from your industry?"] for seg in c.SEGMENTOS}}
    nombre = salida["nombre"]
    if nombre in pb["objeciones"]:
        return []
    pb["objeciones"][nombre] = {}
    for seg in c.SEGMENTOS:
        sig = seg.replace("_sin_web", "-SW").replace("_con_web", "-CW")
        canal = "email" if seg.startswith("US") else "ambos"
        lista = []
        for n, t in enumerate((salida["variantes"].get(seg) or [])[:2], 1):
            v = variante_nueva([{"id": f"{sig}-{nombre[:2].upper()}0"}], t, canal)
            v["id"] = f"{sig}-{nombre[:2].upper()}{n}"
            lista.append(v)
        pb["objeciones"][nombre][seg] = lista
    return [(nombre, sueltas[:5])]


# ---------- 5. alarma ----------
def alarma(pb, todas_cerradas):
    ultimas = sorted(todas_cerradas, key=lambda x: x.get("cerrada", ""))[-100:]
    if len(ultimas) < 100 or any((x["puntaje"] or 0) >= 3 for x in ultimas):
        return False
    salida = c.extraer_json(c.llamar_claude(SISTEMA, (
        'Tarea "ofertas". En las últimas 100 conversaciones cerradas ningún lead pidió demo ni precio. '
        "Ofertas actuales en apertura:\n" + "\n".join("- " + v["texto"] for vs in pb["apertura"].values() for v in vs)
        + "\nProponé 2 ofertas distintas (no cambios de texto) con una apertura por segmento."), 2000))
    ofertas = (salida or {}).get("ofertas") or [
        {"nombre": "Prueba gratis 14 días", "por_que": "Baja la barrera de entrada: ven la web antes de pagar.",
         "variantes": {seg: ("Vi {dato_observable} de {nombre}. Te armo la web y la ves 14 días gratis; si no te sirve, no pagás nada. ¿Te interesa?"
                             if seg.startswith("AR") else "I saw {dato_observable} about {nombre}. We build your site and you try it free for 14 days; if it's not useful, you pay nothing. Interested?") for seg in c.SEGMENTOS}},
        {"nombre": "Ficha de Google + web mínima", "por_que": "Ataca el problema que ya tienen (los encuentran mal en Google) con algo más chico.",
         "variantes": {seg: ("Vi {dato_observable} de {nombre}. Ordenamos tu ficha de Google y te armamos una página de una sola pantalla para que te escriban directo. ¿Te sirve?"
                             if seg.startswith("AR") else "I saw {dato_observable} about {nombre}. We clean up your Google listing and build a one-screen page so people contact you directly. Useful?") for seg in c.SEGMENTOS}},
    ]
    nuevas = []
    for of in ofertas[:2]:
        for seg in c.SEGMENTOS:
            texto = (of.get("variantes") or {}).get(seg)
            if texto:
                v = variante_nueva(pb["apertura"][seg], texto, "email" if seg.startswith("US") else "ambos",
                                   mutacion=f"oferta alternativa: {of.get('nombre')}", pendiente=True)
                pb["apertura"][seg].append(v)
                nuevas.append(v["id"])
    with open(c.ALERTAS, "a", encoding="utf-8") as f:
        f.write(f"\n## {c.ahora():%Y-%m-%d}\nLa oferta o el segmento no funcionan; optimizar texto no alcanza.\n"
                f"Ninguna de las últimas 100 conversaciones cerradas llegó a puntaje 3.\n\nOfertas propuestas (pendientes de aprobación, "
                f"activar con `python aprobar.py <id>`):\n" + "\n".join(f"- **{o.get('nombre')}**: {o.get('por_que')}" for o in ofertas[:2])
                + f"\n\nVariantes: {', '.join(nuevas)}\n")
    return True


# ---------- reporte ----------
def reporte(pb, por_segmento, bajas, mutaciones, categorias, alarma_disparada, n_cerradas):
    os.makedirs(c.REPORTES, exist_ok=True)
    L = [f"# Reporte del playbook v{pb['version']} — {c.ahora():%Y-%m-%d}", "",
         f"Conversaciones procesadas: {n_cerradas}", ""]
    L += ["## Por segmento", ""] + [f"- {s}: {n}" for s, n in sorted(por_segmento.items())] + [""]
    L += ["## Tasas por grupo", "", "| Grupo | Variante | Enviados | Puntos | Tasa | Estado |", "|---|---|---|---|---|---|"]
    for nombre, vs in grupos(pb):
        for v in vs:
            estado = "pendiente" if v["pendiente_aprobacion"] else ("activa" if v["activa"] else "baja")
            L.append(f"| {nombre} | {v['id']} | {v['enviados']} | {v['puntos']} | {v['tasa']} | {estado} |")
    L += ["", "## Bajas", ""] + ([f"- {n} · {v['id']}: {v['motivo_baja']}" for n, v in bajas] or ["- ninguna"])
    L += ["", "## Mutaciones", ""] + ([f"- {n} · reemplaza a {b} → {v['id']}: {v['mutacion']}\n  > {v['texto']}" for n, b, v in mutaciones] or ["- ninguna"])
    L += ["", "## Categorías nuevas", ""] + ([f"- {n} (ejemplos: {'; '.join(ej)})" for n, ej in categorias] or ["- ninguna"])
    L += ["", "## Alertas", "", "- ver alertas.md" if alarma_disparada else "- ninguna", ""]
    ruta = os.path.join(c.REPORTES, f"reporte_{c.ahora():%Y-%m-%d_%H%M}.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return ruta


def debe_correr(pendientes):
    if len(pendientes) >= 30:
        return True
    ultimos = sorted(os.listdir(c.HISTORIAL)) if os.path.exists(c.HISTORIAL) else []
    ultimos = [u for u in ultimos if u.endswith(".json")]
    if not ultimos:
        return bool(pendientes)
    fecha = ultimos[-1].split("_")[-1][:10]
    return c.dias_desde(fecha + "T00:00:00+00:00") >= 7 and bool(pendientes)


def main(forzar=False):
    pb = c.leer_json(c.PLAYBOOK)
    cerradas = [x for x in c.listar_conversaciones() if x["estado"] == "cerrada"]
    pendientes = [x for x in cerradas if not x.get("procesada")]
    if not forzar and not debe_correr(pendientes):
        return
    os.makedirs(c.HISTORIAL, exist_ok=True)
    shutil.copy(c.PLAYBOOK, os.path.join(c.HISTORIAL, f"playbook_v{pb['version']}_{c.ahora():%Y-%m-%d_%H%M}.json"))
    por_segmento = contabilizar(pb, pendientes)
    bajas = podar(pb)
    mutaciones = mutar(pb, bajas)
    categorias = huecos(pb, cerradas)
    disparo = alarma(pb, cerradas)
    pb["version"] += 1
    c.escribir_json(c.PLAYBOOK, pb)
    ruta = reporte(pb, por_segmento, bajas, mutaciones, categorias, disparo, len(pendientes))
    c.log(AGENTE, f"v{pb['version']}: {len(pendientes)} conversaciones, {len(bajas)} bajas, {len(mutaciones)} mutaciones, "
                  f"{len(categorias)} categorías nuevas, alarma={'sí' if disparo else 'no'} → {os.path.basename(ruta)}")


if __name__ == "__main__":
    main(forzar="--forzar" in sys.argv)
