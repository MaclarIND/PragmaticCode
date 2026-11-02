#!/usr/bin/env python3
"""Agente 1 — Ventas. Corre cada 15 minutos (scheduler.py) o a mano: python agentes/ventas.py

Hace tres cosas, en este orden:
  1. Leads nuevos en leads/entrada/   → apertura (y mueve el archivo a leads/procesados/)
  2. Respuestas en respuestas/entrada/ → clasifica y contesta (y mueve el archivo a respuestas/procesadas/)
  3. Seguimientos vencidos            → día 3 y día 7; a los 14 días sin respuesta, cierra

Lo que decide el código (no el modelo): elección de variante, horarios, canal, límite por hora, días de
seguimiento, puntaje al cerrar, bajas, pie legal. El modelo solo adapta el texto de la variante al negocio,
clasifica la respuesta del lead en categorías cerradas y redacta la respuesta a una pregunta concreta.
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun as c  # noqa: E402
import conectores  # noqa: E402

AGENTE = "ventas"
SISTEMA = c.leer_texto(os.path.join(c.PROMPTS, "ventas.md"))


# ---------- helpers de texto ----------
def idioma_inicial(lead):
    return "es-AR" if lead["pais"] == "AR" else "en"


def firma_y_baja(conv, cfg):
    """La opción de baja nunca cierra el mensaje: AR como P.D. bajo la firma; US como pie CAN-SPAM."""
    idioma, canal = conv["idioma"], conv["segmento"]["canal"]
    if idioma == "es-AR":
        return f"\n\n{cfg['firma']}\n\nP.D.: si preferís no recibir más mensajes, respondé \"baja\"."
    pie_dir = f"{cfg['empresa']}" + (f" · {cfg['direccion_fisica']}" if cfg.get("direccion_fisica") else "")
    if idioma == "en":
        aviso = "To stop receiving messages from us, reply \"unsubscribe\"." if canal == "whatsapp" \
            else "To stop receiving emails from us, reply \"unsubscribe\"."
    else:
        aviso = "Para no recibir más mensajes, responda \"BAJA\"."
    return f"\n\n{cfg['firma']}\n\n{pie_dir}\n{aviso}"


def rellenar(texto, lead, cfg):
    datos = {"nombre": lead["nombre"], "rubro": lead.get("rubro") or "negocio", "portfolio": cfg["portfolio_link"],
             "dato_observable": lead.get("dato_observable") or ("sus reseñas en Google" if lead["pais"] == "AR" else "your Google reviews")}
    return re.sub(r"\{(\w+)\}", lambda m: str(datos.get(m.group(1), m.group(0))), texto)


def adaptar(variante, lead, conv, cfg):
    """Adapta la variante al negocio sin tocar estructura ni largo. Si el modelo se va de largo, se usa el relleno literal."""
    base = rellenar(variante["texto"], lead, cfg)
    salida = c.extraer_json(c.llamar_claude(SISTEMA, (
        f'Tarea "adaptar". Idioma: {conv["idioma"]}. Canal: {conv["segmento"]["canal"]}.\n'
        f"Negocio: {lead['nombre']} · rubro: {lead.get('rubro')} · país: {lead['pais']} · tiene web: {lead.get('tiene_web')} "
        f"· dato observable: {lead.get('dato_observable')}\nVariante:\n{base}"), 400))
    texto = (salida or {}).get("texto", "").strip()
    if not texto or not 0.7 <= len(texto) / max(len(base), 1) <= 1.3:
        return base
    return texto


# ---------- regla 4: elección de variante (código puro) ----------
def grupo_de(pb, momento, segmento, categoria=None):
    if momento == "apertura":
        return pb["apertura"].get(segmento, [])
    if momento == "seguimiento":
        return pb["seguimiento_sin_respuesta"].get(segmento, [])
    if momento == "objecion":
        return pb["objeciones"].get(categoria, {}).get(segmento, [])
    if momento == "cierre":
        return pb["cierre"].get(segmento, [])
    return []


USOS_EN_CURSO = {}   # variante_id -> envíos en conversaciones que el Agente 2 todavía no contabilizó


def cargar_usos_en_curso():
    USOS_EN_CURSO.clear()
    for conv in c.listar_conversaciones():
        if not conv.get("procesada"):
            for m in conv["mensajes"]:
                if m["rol"] == "bot" and m.get("variante_id"):
                    USOS_EN_CURSO[m["variante_id"]] = USOS_EN_CURSO.get(m["variante_id"], 0) + 1


def elegir_variante(grupo, canal, semilla):
    cands = [v for v in grupo if v["activa"] and not v["pendiente_aprobacion"] and v["canal"] in ("ambos", canal)]
    if not cands:
        return None
    usados = lambda v: v["enviados"] + USOS_EN_CURSO.get(v["id"], 0)  # noqa: E731
    pocas = [v for v in cands if usados(v) < c.MIN_ENVIADOS_VARIANTE]
    if pocas:
        elegida = min(pocas, key=usados)
        USOS_EN_CURSO[elegida["id"]] = USOS_EN_CURSO.get(elegida["id"], 0) + 1
        return elegida
    rnd = c.azar(semilla)
    if len({v["tasa"] for v in cands}) == 1:   # todavía no hay diferencias medidas: al azar
        return rnd.choice(cands)
    mejor = max(cands, key=lambda v: v["tasa"])
    otras = [v for v in cands if v is not mejor]
    return mejor if rnd.random() < 0.8 or not otras else rnd.choice(otras)


# ---------- registro ----------
def ruta_conv(lead_id):
    return os.path.join(c.CONVERSACIONES, f"{lead_id}.json")


def guardar(conv):
    conv["actualizada"] = c.iso()
    c.escribir_json(ruta_conv(conv["lead_id"]), conv)


def enviados_ultima_hora():
    return sum(1 for conv in c.listar_conversaciones() for m in conv["mensajes"]
               if m["rol"] == "bot" and c.dias_desde(m["ts"]) * 24 < 1)


def registrar_en_memoria_vieja(lead, estado):
    """leads_contactados.json es la memoria compartida con el buscador: así no vuelve a proponer a este negocio."""
    reg = c.leer_json(c.REGISTRO_VIEJO, []) or []
    for l in reg:
        if l.get("id") == lead["lead_id"]:
            l["estado"] = estado
            break
    else:
        reg.append({"id": lead["lead_id"], "nombre_empresa": lead["nombre"], "email": lead.get("email"),
                    "telefono": lead.get("telefono"), "pais": lead["pais"], "estado": estado,
                    "fecha_ultimo_contacto": c.iso(), "origen": "sistema_ventas"})
    c.escribir_json(c.REGISTRO_VIEJO, reg)


def enviar(conv, texto, momento, variante_id, cfg, asunto=None):
    lead, canal = conv["lead"], conv["segmento"]["canal"]
    completo = texto + firma_y_baja(conv, cfg)
    if canal == "whatsapp":
        mid = conectores.enviar_whatsapp(lead["telefono"], completo)
    else:
        if not asunto:
            asunto = f"Re: {conv.get('asunto') or ''}".strip()
        mid = conectores.enviar_email(lead["email"], asunto, completo, en_respuesta_a=conv.get("message_id"))
        conv["message_id"], conv["asunto"] = mid, conv.get("asunto") or asunto
    conv["mensajes"].append({"rol": "bot", "texto": texto, "variante_id": variante_id, "momento": momento, "ts": c.iso()})
    conv["inicio_silencio"] = c.iso()
    guardar(conv)
    c.log(AGENTE, f"{lead['lead_id']} ({conv['segmento']['pais']}/{canal}) {momento} {variante_id or '-'}")


def puntaje_de(conv):
    """0 sin respuesta · 1 negativo · 2 pregunta · 3 pidió demo/precio · 4 pagó."""
    valor = {"pago": 4, "interes": 3, "pregunta": 2}
    tipos = [m.get("tipo") for m in conv["mensajes"] if m["rol"] == "lead"]
    if not tipos:
        return 0
    return max([valor.get(t, 1) for t in tipos])


def cerrar(conv, motivo):
    conv["estado"], conv["puntaje"], conv["motivo_cierre"] = "cerrada", puntaje_de(conv), motivo
    conv["cerrada"] = c.iso()
    guardar(conv)
    registrar_en_memoria_vieja(conv["lead"], {"pago": "venta_cerrada", "baja": "baja", "sin_respuesta": "sin_respuesta"}.get(motivo, "no_interesado"))
    c.log(AGENTE, f"{conv['lead_id']} cerrada ({motivo}) puntaje {conv['puntaje']}")


def registrar_baja(lead):
    bajas = c.leer_json(c.BAJAS, []) or []
    bajas.append({"lead_id": lead["lead_id"], "email": lead.get("email"), "telefono": lead.get("telefono"), "fecha": c.iso()})
    c.escribir_json(c.BAJAS, bajas)


def traspaso_venta(conv, cfg):
    """Aviso al responsable de ventas + datos iniciales del brief para el programador (formato de prompts/agente_programador.md)."""
    lead = conv["lead"]
    os.makedirs(c.BRIEFS, exist_ok=True)
    with open(c.NOTIFICACIONES, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "fecha": c.iso(), "para": cfg["responsable_ventas"], "lead_id": lead["lead_id"], "empresa": lead["nombre"],
            "pais": lead["pais"], "mensaje": "El lead dice que pagó: verificar el pago en la cuenta y marcar pago_verificado.",
            "origen": "sistema_ventas"}, ensure_ascii=False) + "\n")
    c.escribir_json(os.path.join(c.BRIEFS, f"datos_brief_{lead['lead_id']}.json"), {
        "id": lead["lead_id"], "nombre_empresa": lead["nombre"], "rubro": lead.get("rubro", ""), "pais": lead["pais"],
        "idioma_sitio": "es" if conv["idioma"] != "en" else "en", "plan": "",
        "contacto_responsable": {"nombre": "", "email": lead.get("email", ""), "telefono": lead.get("telefono", "")},
        "descripcion_negocio": lead.get("dato_observable", ""), "objetivo_sitio": "", "secciones": [], "servicios_o_productos": [],
        "colores_y_estilo": "", "referencias": [], "dominio": lead.get("url_web"), "redes": {"instagram": "", "facebook": "", "whatsapp": ""},
        "direccion_y_horarios": "", "materiales": {"logo": "", "fotos": [], "textos": ""},
        "notas_venta": " | ".join(m["texto"] for m in conv["mensajes"] if m["rol"] == "lead")[:1500],
    })


# ---------- 1. leads nuevos ----------
def procesar_leads(pb, cfg):
    ex = c.excluidos()
    for nombre in sorted(os.listdir(c.LEADS_ENTRADA)):
        if not nombre.endswith(".json"):
            continue
        ruta = os.path.join(c.LEADS_ENTRADA, nombre)
        lead = c.leer_json(ruta)
        if not lead or not {"lead_id", "nombre", "pais"} <= set(lead):
            c.log(AGENTE, f"lead inválido {nombre}, se descarta")
            shutil.move(ruta, os.path.join(c.LEADS_PROCESADOS, nombre))
            continue
        claves = {lead["lead_id"], (lead.get("email") or "").lower(), lead.get("telefono")} - {"", None}
        if claves & ex or os.path.exists(ruta_conv(lead["lead_id"])):
            c.log(AGENTE, f"{lead['lead_id']} ya contactado o dado de baja, se saltea")
            shutil.move(ruta, os.path.join(c.LEADS_PROCESADOS, nombre))
            continue
        if not lead.get("email"):   # primer contacto siempre por email (TCPA / Ley 25.326)
            c.log(AGENTE, f"{lead['lead_id']} sin email, no se contacta")
            shutil.move(ruta, os.path.join(c.LEADS_PROCESADOS, nombre))
            continue
        if not c.en_horario(lead, cfg):
            continue   # queda en entrada para la próxima corrida
        if enviados_ultima_hora() >= cfg["max_mensajes_por_hora"]:
            c.log(AGENTE, "límite de mensajes por hora alcanzado")
            return
        segmento = c.segmento_de(lead)
        conv = {"lead_id": lead["lead_id"], "lead": lead, "idioma": idioma_inicial(lead),
                "segmento": {"pais": lead["pais"], "tiene_web": bool(lead.get("tiene_web")), "canal": "email", "clave": segmento},
                "mensajes": [], "estado": "abierta", "puntaje": None, "objecion_detectada": None, "procesada": False,
                "seguimientos": 0, "negativas": 0, "objeciones_respondidas": [], "derivado": False, "creada": c.iso()}
        var = elegir_variante(grupo_de(pb, "apertura", segmento), "email", lead["lead_id"])
        if not var:
            c.log(AGENTE, f"sin variantes activas de apertura para {segmento}")
            return
        asunto = f"Una idea para {lead['nombre']}" if conv["idioma"] != "en" else f"Quick idea for {lead['nombre']}"
        enviar(conv, adaptar(var, lead, conv, cfg), "apertura", var["id"], cfg, asunto=asunto)
        registrar_en_memoria_vieja(lead, "contactado")
        shutil.move(ruta, os.path.join(c.LEADS_PROCESADOS, nombre))


# ---------- 2. respuestas ----------
PALABRAS = {
    "baja": ["baja", "unsubscribe", "no me escribas", "no me escriban", "stop", "remove me", "dejen de", "sacame"],
    "pago": ["pagué", "pague", "transferí", "transferi", "ya hice el pago", "comprobante", "paid", "sent the deposit", "wired", "payment sent"],
    "interes": ["cuánto", "cuanto", "precio", "sale", "cuesta", "how much", "price", "cost", "demo", "ejemplo", "example",
                "mostrame", "show me", "ver algo", "me interesa", "interested", "contame más", "tell me more", "presupuesto", "quote"],
    "negativo": ["no me interesa", "not interested", "no gracias", "no, gracias", "no thanks", "no thank you", "paso"],
    "ya_tengo_web": ["ya tengo", "ya tenemos", "already have", "we have a site", "tengo página", "tengo pagina"],
    "precio": ["caro", "cara", "expensive", "budget", "no tengo plata", "mucha plata", "too much", "afford"],
    "no_necesito": ["no necesito", "no necesitamos", "don't need", "do not need", "no lo necesito", "no hace falta", "con instagram"],
    "desconfianza": ["quién sos", "quien sos", "quiénes son", "spam", "estafa", "scam", "who are you", "is this real", "legit", "de dónde sacaste", "how did you get"],
    "persona": ["hablar con una persona", "una persona real", "alguien real", "sos un bot", "are you a bot", "a human", "real person", "llamame", "call me"],
}


def clasificar_fallback(texto, conv):
    t = texto.lower()
    tiene = lambda k: any(p in t for p in PALABRAS[k])  # noqa: E731
    idioma = conv["idioma"]
    if conv["segmento"]["pais"] == "US" and re.search(r"\b(hola|gracias|precio|cuánto|cuanto|tengo|necesito|quiero)\b", t):
        idioma = "es-US"
    res = {"tipo": "otro", "objecion": None, "objecion_texto": None, "idioma": idioma, "pide_persona": tiene("persona")}
    if tiene("baja"):
        res["tipo"] = "baja"
    elif tiene("pago"):
        res["tipo"] = "pago"
    elif tiene("ya_tengo_web") or tiene("precio") or tiene("no_necesito") or tiene("desconfianza"):
        res["tipo"] = "objecion"
        res["objecion"] = next(k for k in c.CATEGORIAS_OBJECION if tiene(k))
    elif tiene("negativo"):
        res["tipo"] = "negativo"
    elif tiene("interes"):
        res["tipo"] = "interes"
    elif "?" in t or "¿" in t:
        res["tipo"] = "pregunta"
    return res


def clasificar(texto, conv):
    historial = "\n".join(f"{m['rol']}: {m['texto']}" for m in conv["mensajes"][-6:])
    salida = c.extraer_json(c.llamar_claude(SISTEMA, (
        f'Tarea "clasificar". País: {conv["segmento"]["pais"]}. Idioma actual: {conv["idioma"]}.\n'
        f"Conversación hasta ahora:\n{historial}\n\nÚltimo mensaje del lead:\n{texto}"), 300))
    fb = clasificar_fallback(texto, conv)
    if not salida or salida.get("tipo") not in ("pregunta", "interes", "objecion", "negativo", "pago", "baja", "otro"):
        return fb
    salida.setdefault("idioma", fb["idioma"])
    salida.setdefault("pide_persona", fb["pide_persona"])
    if salida.get("objecion") not in c.CATEGORIAS_OBJECION + ("otra",):
        salida["objecion"] = None
    return salida


def responder_libre(conv, texto_lead, cfg):
    """Respuesta a una pregunta concreta o a una objeción sin categoría. Solo eso, en su idioma, terminada en pregunta."""
    lead = conv["lead"]
    historial = "\n".join(f"{m['rol']}: {m['texto']}" for m in conv["mensajes"][-8:])
    salida = c.extraer_json(c.llamar_claude(SISTEMA, (
        f'Tarea "responder". Idioma: {conv["idioma"]}. País: {lead["pais"]} (moneda {c.PRECIOS[lead["pais"]]["moneda"]}).\n'
        f"Negocio: {lead['nombre']} · {lead.get('rubro')} · tiene web: {lead.get('tiene_web')}.\n"
        f"Persona para derivar: {cfg['derivacion_nombre']} {cfg.get('derivacion_telefono', '')}.\nPortfolio: {cfg['portfolio_link']}.\n"
        f"Conversación:\n{historial}\n\nÚltimo mensaje del lead:\n{texto_lead}"), 500))
    if salida and salida.get("texto"):
        return salida["texto"].strip(), bool(salida.get("derivar"))
    return {"es-AR": "Buena pregunta. Te la respondo con un ejemplo concreto de tu rubro, ¿te lo mando por acá?",
            "es-US": "Buena pregunta. Se la respondo con un ejemplo concreto de su rubro, ¿se lo envío por aquí?",
            "en": "Good question. Let me answer it with a concrete example for your industry. Can I send it here?"}[conv["idioma"]], False


def texto_fijo(clave, conv, cfg):
    i = conv["idioma"]
    nombre, tel = cfg["derivacion_nombre"], cfg.get("derivacion_telefono", "")
    return {
        "despedida": {"es-AR": "Dale, gracias por responder. Éxitos con el negocio.",
                      "es-US": "Entendido, gracias por responder. Mucho éxito con el negocio.",
                      "en": "Understood, thanks for getting back to me. Best of luck with the business."},
        "pago": {"es-AR": "Gracias. En cuanto confirmemos el pago te escribimos para pedirte logo, fotos y textos. ¿Quién va a ser el contacto para el proyecto?",
                 "es-US": "Gracias. En cuanto confirmemos el pago le escribimos para pedirle logo, fotos y textos. ¿Quién será el contacto para el proyecto?",
                 "en": "Thank you. As soon as we confirm the payment we'll reach out for your logo, photos and copy. Who will be the contact for the project?"},
        "derivar": {"es-AR": f"Claro. Te paso con {nombre}{(' (' + tel + ')') if tel else ''}, que te contacta directamente. ¿Qué horario te queda cómodo?",
                    "es-US": f"Claro. Lo comunico con {nombre}{(' (' + tel + ')') if tel else ''}, que lo contactará directamente. ¿Qué horario le queda cómodo?",
                    "en": f"Of course. I'll connect you with {nombre}{(' (' + tel + ')') if tel else ''}, who will reach out directly. What time works for you?"},
    }[clave][i]


def notificar_interno(cfg, lead, motivo):
    with open(c.NOTIFICACIONES, "a", encoding="utf-8") as f:
        f.write(json.dumps({"fecha": c.iso(), "para": cfg["derivacion_nombre"], "lead_id": lead["lead_id"],
                                          "empresa": lead["nombre"], "mensaje": motivo, "origen": "sistema_ventas"}, ensure_ascii=False) + "\n")


def procesar_respuestas(pb, cfg):
    for nombre in sorted(os.listdir(c.RESPUESTAS_ENTRADA)):
        if not nombre.endswith(".json"):
            continue
        ruta = os.path.join(c.RESPUESTAS_ENTRADA, nombre)
        r = c.leer_json(ruta)
        destino = os.path.join(c.RESPUESTAS_PROCESADAS, nombre)
        conv = c.leer_json(ruta_conv(r.get("lead_id", ""))) if r else None
        if not conv:
            c.log(AGENTE, f"respuesta {nombre} sin conversación conocida, se guarda sin procesar")
            shutil.move(ruta, destino)
            continue
        cl = clasificar(r["texto"], conv)
        conv["mensajes"].append({"rol": "lead", "texto": r["texto"], "variante_id": None, "momento": "respuesta",
                                 "ts": r.get("ts") or c.iso(), "tipo": cl["tipo"], "objecion": cl.get("objecion")})
        conv["idioma"] = cl.get("idioma") or conv["idioma"]
        if r.get("canal") == "whatsapp" and conv["segmento"]["canal"] != "whatsapp":
            conv["segmento"]["canal"] = "whatsapp"   # el lead eligió el canal: desde acá se le responde por ahí
        conv["seguimientos"] = 0
        guardar(conv)
        shutil.move(ruta, destino)
        if conv["estado"] == "cerrada":
            if cl["tipo"] == "baja":
                registrar_baja(conv["lead"])
            c.log(AGENTE, f"{conv['lead_id']} respondió con la conversación ya cerrada ({cl['tipo']}); no se contesta")
            continue
        atender(pb, cfg, conv, r["texto"], cl)


def atender(pb, cfg, conv, texto_lead, cl):
    lead, seg, canal = conv["lead"], conv["segmento"]["clave"], conv["segmento"]["canal"]
    tipo = cl["tipo"]
    if tipo == "baja":
        registrar_baja(lead)
        cerrar(conv, "baja")
        return
    if tipo == "pago":
        enviar(conv, texto_fijo("pago", conv, cfg), "cierre", None, cfg)
        traspaso_venta(conv, cfg)
        cerrar(conv, "pago")
        return
    if cl.get("pide_persona") or conv["derivado"]:
        if not conv["derivado"]:
            conv["derivado"] = True
            notificar_interno(cfg, lead, f"El lead pide hablar con una persona. Último mensaje: {texto_lead[:300]}")
            enviar(conv, texto_fijo("derivar", conv, cfg), "derivacion", None, cfg)
        return
    if tipo == "negativo" or (tipo == "objecion" and cl.get("objecion") in conv["objeciones_respondidas"]):
        conv["negativas"] += 1
        if conv["negativas"] >= 2 or conv["objeciones_respondidas"]:
            enviar(conv, texto_fijo("despedida", conv, cfg), "cierre", None, cfg)
            cerrar(conv, "segundo_no")
            return
        tipo, cl["objecion"] = "objecion", "no_necesito"   # primer "no" seco: una variante, una vez
    if tipo == "objecion":
        cat = cl.get("objecion") or "otra"
        conv["objecion_detectada"] = cl.get("objecion_texto") or cat
        conv["objeciones_respondidas"].append(cat)
        var = elegir_variante(grupo_de(pb, "objecion", seg, cat), canal, lead["lead_id"] + cat) if cat != "otra" else None
        if var:
            enviar(conv, adaptar(var, lead, conv, cfg), "objecion", var["id"], cfg)
        else:
            texto, derivar = responder_libre(conv, texto_lead, cfg)
            enviar(conv, texto, "objecion", None, cfg)
        return
    if tipo == "interes":
        var = elegir_variante(grupo_de(pb, "cierre", seg), canal, lead["lead_id"] + "cierre")
        if var:
            enviar(conv, adaptar(var, lead, conv, cfg), "cierre", var["id"], cfg)
            return
    texto, derivar = responder_libre(conv, texto_lead, cfg)   # pregunta / otro
    if derivar:
        conv["derivado"] = True
        notificar_interno(cfg, lead, f"Pedido fuera de los planes o para una persona: {texto_lead[:300]}")
        texto = texto_fijo("derivar", conv, cfg)
    enviar(conv, texto, "respuesta" if tipo in ("pregunta", "otro") else tipo, None, cfg)


# ---------- 3. seguimientos ----------
def procesar_seguimientos(pb, cfg):
    for conv in list(c.listar_conversaciones()):
        if conv["estado"] != "abierta" or conv.get("derivado") or not conv["mensajes"] or conv["mensajes"][-1]["rol"] != "bot":
            continue
        dias = c.dias_desde(conv.get("inicio_silencio") or conv["mensajes"][-1]["ts"])
        if conv["negativas"]:   # ya dijo que no una vez: no se lo persigue con seguimientos; a los 7 días se cierra
            if dias >= 7:
                cerrar(conv, "sin_respuesta")
            continue
        if conv["seguimientos"] >= 2:
            if dias >= 14:   # 7 días después del seguimiento del día 7
                cerrar(conv, "sin_respuesta")
            continue
        if dias < (3, 7)[conv["seguimientos"]]:   # día 3 y día 7 desde que empezó el silencio
            continue
        if not c.en_horario(conv["lead"], cfg):
            continue
        if enviados_ultima_hora() >= cfg["max_mensajes_por_hora"]:
            return
        var = elegir_variante(grupo_de(pb, "seguimiento", conv["segmento"]["clave"]), conv["segmento"]["canal"],
                              conv["lead_id"] + f"s{conv['seguimientos']}")
        if not var:
            continue
        inicio = conv.get("inicio_silencio") or conv["mensajes"][-1]["ts"]
        conv["seguimientos"] += 1
        enviar(conv, adaptar(var, conv["lead"], conv, cfg), "seguimiento", var["id"], cfg)
        conv["inicio_silencio"] = inicio   # los días se cuentan desde el último mensaje del lead, no desde el seguimiento
        guardar(conv)


def main():
    pb = c.leer_json(c.PLAYBOOK)
    if not pb:
        sys.exit("Falta playbook.json (python generar_playbook_inicial.py)")
    cfg = c.config()
    cargar_usos_en_curso()
    for d in (c.LEADS_ENTRADA, c.LEADS_PROCESADOS, c.RESPUESTAS_ENTRADA, c.RESPUESTAS_PROCESADAS, c.CONVERSACIONES):
        os.makedirs(d, exist_ok=True)
    procesar_respuestas(pb, cfg)
    procesar_leads(pb, cfg)
    procesar_seguimientos(pb, cfg)


if __name__ == "__main__":
    main()
