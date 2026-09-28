#!/usr/bin/env python3
"""Agente de contacto (Lucas — Pragmatic Code).

Lee los leads del agente buscador, arma el primer email personalizado,
hace un único seguimiento y mantiene leads_contactados.json.
Las respuestas de los clientes se manejan con prompts/agente_contacto.md.

Uso:
    python3 contactador.py procesar leads_2026-09-28_1030.json            # solo borradores
    python3 contactador.py procesar leads_2026-09-28_1030.json --enviar   # envía por SMTP
    python3 contactador.py seguimientos [--enviar]
    python3 contactador.py registrar <place_id> --estado respondió --resumen "..." \
        --proximo "mandar ejemplo" --fecha 2026-10-02
    python3 contactador.py brief <place_id>     # tras venta_cerrada: arma el brief del programador
    python3 contactador.py pendientes           # avisos del programador (faltantes / extras)
    python3 contactador.py estado
"""
import argparse
import datetime as dt
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
REGISTRO = os.path.join(BASE, "leads_contactados.json")
CONFIG = os.path.join(BASE, "config_contacto.json")
OUTBOX = os.path.join(BASE, "outbox")
VENTAS = os.path.join(BASE, "notificaciones_ventas.jsonl")
BRIEFS = os.path.join(BASE, "briefs")
LOG = os.path.join(BASE, "log_errores.txt")

ESTADOS = ["contactado", "respondió", "interesado", "propuesta_enviada", "venta_cerrada",
           "no_interesado", "sin_respuesta", "baja"]
FINALES = {"venta_cerrada", "no_interesado", "sin_respuesta", "baja"}

# Cómo busca la gente cada rubro (es, en). Claves = rubros de prospector.py.
RUBROS = {
    "Restaurante": ("un restaurante", "a restaurant"),
    "Cafetería": ("una cafetería", "a coffee shop"),
    "Peluquería / barbería": ("una peluquería", "a barber or hair salon"),
    "Taller mecánico": ("un taller mecánico", "an auto repair shop"),
    "Consultorio odontológico": ("un odontólogo", "a dentist"),
    "Kinesiología": ("un kinesiólogo", "a physical therapist"),
    "Gimnasio": ("un gimnasio", "a gym"),
    "Inmobiliaria": ("una inmobiliaria", "a real estate agency"),
    "Plomería": ("un plomero", "a plumber"),
    "Electricista": ("un electricista", "an electrician"),
    "Limpieza": ("un servicio de limpieza", "a cleaning service"),
    "Landscaping / jardinería": ("un jardinero", "a landscaper"),
    "Construcción": ("una empresa de construcción", "a contractor"),
    "Estudio contable": ("un contador", "an accountant"),
    "Estudio jurídico": ("un abogado", "a lawyer"),
    "Tienda de ropa": ("una tienda de ropa", "a clothing store"),
    "Veterinaria": ("una veterinaria", "a vet"),
}


def log_error(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}\n")
    print(f"[error] {msg}", file=sys.stderr)


def cargar_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def guardar_registro(reg):
    tmp = REGISTRO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, REGISTRO)


def ahora():
    return dt.datetime.now(dt.timezone.utc)


def variante(lead):
    """es-AR (vos), es-US (usted) o en."""
    if lead.get("idioma_contacto") == "en":
        return "en"
    return "es-AR" if lead.get("pais") == "AR" else "es-US"


def frase_problema(lead, v):
    p = (lead.get("problema_detectado") or "").lower()
    nombre, ciudad = lead["nombre_empresa"], lead["ciudad"]
    es, en = RUBROS.get(lead.get("rubro"), ("un negocio como el suyo", "a business like yours"))
    n = lead.get("cantidad_resenas")
    if p.startswith("solo"):
        red = lead["problema_detectado"].split(" ")[1]
        return {
            "es-AR": f"Vi que {nombre} tiene muy buenas reseñas en Google, pero el link de su web lleva a {red}. Eso hace más difícil que te encuentre quien busca {es} en {ciudad}.",
            "es-US": f"Vi que {nombre} tiene muy buenas reseñas en Google, pero el enlace de su web lleva a {red}. Eso hace más difícil que lo encuentre quien busca {es} en {ciudad}.",
            "en": f"I noticed {nombre} has great Google reviews, but your website link goes to {red}. That makes it harder for people looking for {en} in {ciudad} to find you.",
        }[v]
    if p.startswith("web"):
        detalles = {"es-AR": [], "es-US": [], "en": []}
        if "caída" in p:
            detalles["es-AR"].append("no está cargando"); detalles["es-US"].append("no está cargando")
            detalles["en"].append("it isn't loading")
        if "https" in p:
            detalles["es-AR"].append("el navegador la marca como \"no segura\"")
            detalles["es-US"].append("el navegador la marca como \"no segura\"")
            detalles["en"].append("browsers flag it as \"not secure\"")
        if "celular" in p:
            detalles["es-AR"].append("no se ve bien en el celular"); detalles["es-US"].append("no se ve bien en el celular")
            detalles["en"].append("it doesn't display well on phones")
        if "desactualizada" in p:
            detalles["es-AR"].append("parece desactualizada"); detalles["es-US"].append("parece desactualizada")
            detalles["en"].append("it looks outdated")
        d = " y ".join(detalles[v]) if v != "en" else " and ".join(detalles[v])
        return {
            "es-AR": f"Entré a la web de {nombre} y noté que {d}. Hoy casi todos buscan {es} en {ciudad} desde el celular, y ahí se pierden consultas.",
            "es-US": f"Entré a la web de {nombre} y noté que {d}. Hoy casi todos buscan {es} en {ciudad} desde el celular, y ahí se pierden consultas.",
            "en": f"I visited {nombre}'s website and noticed {d}. Most people look for {en} in {ciudad} on their phones, so that can cost you inquiries.",
        }[v]
    resenas = f" ({n})" if n else ""
    resenas_en = f" ({n})" if n else ""
    return {
        "es-AR": f"Vi que {nombre} tiene muy buenas reseñas en Google{resenas} pero no tiene web, entonces muchos de los que buscan {es} en {ciudad} terminan en la competencia.",
        "es-US": f"Vi que {nombre} tiene muy buenas reseñas en Google{resenas} pero no tiene página web, por lo que muchas personas que buscan {es} en {ciudad} terminan eligiendo a otro negocio.",
        "en": f"I noticed {nombre} has great Google reviews{resenas_en} but no website, so many people searching for {en} in {ciudad} end up going somewhere else.",
    }[v]


def pie_canspam(v, cfg):
    if v == "en":
        return f"{cfg['empresa']} · {cfg['direccion_fisica']}\nTo stop receiving emails from us, reply \"unsubscribe\"."
    return f"{cfg['empresa']} · {cfg['direccion_fisica']}\nPara no recibir más correos, responda \"BAJA\"."


def primer_mensaje(lead, cfg):
    v, nombre = variante(lead), lead["nombre_empresa"]
    problema = frase_problema(lead, v)
    if v == "es-AR":
        asunto = f"Una idea para {nombre}"
        cuerpo = [f"Hola, equipo de {nombre}:", "", problema,
                  "Te armamos una web simple y profesional, lista en una semana, para que te encuentren en Google y te escriban directo por WhatsApp.",
                  f"¿Te interesa que te muestre un ejemplo de cómo quedaría?",
                  "", cfg["firma"], "", "P.D.: si preferís no recibir más mensajes, respondé \"baja\"."]
    elif v == "es-US":
        asunto = f"Una idea para {nombre}"
        cuerpo = [f"Hola, equipo de {nombre}:", "", problema,
                  "Le podemos hacer una página sencilla y profesional, lista en una semana, para que lo encuentren en Google y lo contacten directamente.",
                  "¿Le interesa que le muestre un ejemplo de cómo quedaría?",
                  "", cfg["firma"],
                  "", pie_canspam(v, cfg)]
    else:
        asunto = f"Quick idea for {nombre}"
        cuerpo = [f"Hi {nombre} team,", "", problema,
                  "We build simple, professional websites, ready in about a week, so customers find you on Google and contact you directly.",
                  "Would you like me to show you a quick example of how yours could look?",
                  "", cfg["firma"],
                  "", pie_canspam(v, cfg)]
    return asunto, "\n".join(cuerpo)


def seguimiento(lead, asunto_original, cfg):
    v, nombre, link = variante(lead), lead["nombre_empresa"], cfg["portfolio_link"]
    asunto = f"Re: {asunto_original}"
    if v == "es-AR":
        cuerpo = ["Hola, te escribo de nuevo por si se te pasó el mensaje anterior.",
                  f"Acá podés ver algunos trabajos nuestros: {link}",
                  f"¿Querés que te arme un ejemplo para {nombre}?",
                  "", cfg["firma"], "", "P.D.: si preferís no recibir más mensajes, respondé \"baja\"."]
    elif v == "es-US":
        cuerpo = ["Hola, le escribo de nuevo por si no vio el mensaje anterior.",
                  f"Aquí puede ver algunos de nuestros trabajos: {link}",
                  f"¿Le gustaría que le prepare un ejemplo para {nombre}?",
                  "", cfg["firma"],
                  "", pie_canspam(v, cfg)]
    else:
        cuerpo = ["Hi, just following up in case my last email got buried.",
                  f"You can see some of our work here: {link}",
                  f"Would you like me to put together an example for {nombre}?",
                  "", cfg["firma"],
                  "", pie_canspam(v, cfg)]
    return asunto, "\n".join(cuerpo)


def en_horario(tz, cfg):
    local = ahora().astimezone(ZoneInfo(tz))
    return local.weekday() < 5 and cfg["hora_inicio"] <= local.hour < cfg["hora_fin"]


def enviados_ultima_hora(reg):
    limite = ahora() - dt.timedelta(hours=1)
    return sum(1 for l in reg for h in l.get("historial", [])
               if h.get("direccion") == "saliente" and dt.datetime.fromisoformat(h["fecha"]) > limite)


def validar_envio(cfg):
    faltan = [k for k, val in cfg.items() if isinstance(val, str) and val.startswith("[")]
    if faltan:
        sys.exit(f"Completá config_contacto.json antes de enviar: {', '.join(faltan)}")
    if not cfg.get("max_mensajes_por_hora"):
        sys.exit("Definí max_mensajes_por_hora en config_contacto.json antes de enviar.")
    faltan_env = [k for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_FROM") if not os.environ.get(k)]
    if faltan_env:
        sys.exit(f"Faltan variables de entorno para SMTP: {', '.join(faltan_env)}")


def enviar_email(para, asunto, cuerpo, en_respuesta_a=None):
    msg = EmailMessage()
    remitente = os.environ["SMTP_FROM"]
    msg["From"], msg["To"], msg["Subject"] = remitente, para, asunto
    direccion = parseaddr(remitente)[1]
    msg["Message-ID"] = make_msgid(domain=direccion.split("@")[-1])
    msg["List-Unsubscribe"] = f"<mailto:{direccion}?subject=unsubscribe>"
    if en_respuesta_a:
        msg["In-Reply-To"] = msg["References"] = en_respuesta_a
    msg.set_content(cuerpo)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587")), timeout=30) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)
    return msg["Message-ID"]


def guardar_borrador(borradores, lead, asunto, cuerpo, tipo):
    borradores.append(f"## {lead['nombre_empresa']} ({lead['pais']}, {tipo})\n\n"
                      f"**Para:** {lead['email']}  \n**Asunto:** {asunto}\n\n```\n{cuerpo}\n```\n")


def escribir_borradores(borradores):
    if not borradores:
        print("No hay mensajes para generar.")
        return
    os.makedirs(OUTBOX, exist_ok=True)
    path = os.path.join(OUTBOX, f"borradores_{dt.datetime.now():%Y-%m-%d_%H%M}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Borradores de email — revisar antes de enviar\n\n" + "\n".join(borradores))
    print(f"{len(borradores)} borradores en {path}")


def cmd_procesar(args, cfg):
    if args.enviar:
        validar_envio(cfg)
    reg = cargar_json(REGISTRO, [])
    ya_ids = {l["id"] for l in reg}
    ya_emails = {l.get("email", "").lower() for l in reg}
    leads = cargar_json(args.archivo, {}).get("leads", [])
    borradores = []
    for lead in leads:
        if lead["id"] in ya_ids or lead.get("email", "").lower() in ya_emails:
            print(f"- {lead['nombre_empresa']}: ya está en el registro, se saltea")
            continue
        if not lead.get("email"):
            log_error(f"lead {lead['id']} sin email, se saltea")
            continue
        asunto, cuerpo = primer_mensaje(lead, cfg)
        if not args.enviar:
            guardar_borrador(borradores, lead, asunto, cuerpo, "primer contacto")
            continue
        if not en_horario(lead["zona_horaria"], cfg):
            print(f"- {lead['nombre_empresa']}: fuera de horario comercial, queda para la próxima corrida")
            continue
        if enviados_ultima_hora(reg) >= cfg["max_mensajes_por_hora"]:
            print("Límite de mensajes por hora alcanzado; el resto queda para la próxima corrida.")
            break
        try:
            mid = enviar_email(lead["email"], asunto, cuerpo)
        except Exception as e:
            log_error(f"envío a {lead['id']} falló: {e}")
            continue
        fecha = ahora().isoformat(timespec="seconds")
        reg.append({
            "id": lead["id"], "nombre_empresa": lead["nombre_empresa"], "email": lead["email"],
            "telefono": lead.get("telefono"), "pais": lead["pais"], "ciudad": lead["ciudad"],
            "rubro": lead.get("rubro"), "idioma_contacto": lead.get("idioma_contacto"),
            "zona_horaria": lead["zona_horaria"], "estado": "contactado",
            "fecha_ultimo_contacto": fecha, "canal": "email",
            "resumen": f"Primer email enviado ({lead.get('problema_detectado')}).",
            "proximo_paso": "seguimiento si no responde",
            "fecha_proximo_paso": (ahora() + dt.timedelta(days=cfg["dias_para_seguimiento"])).date().isoformat(),
            "mensajes_sin_respuesta": 1, "asunto": asunto, "message_id": mid,
            "historial": [{"fecha": fecha, "direccion": "saliente", "canal": "email", "tipo": "primer_contacto"}],
        })
        guardar_registro(reg)
        print(f"+ {lead['nombre_empresa']}: enviado")
    if not args.enviar:
        escribir_borradores(borradores)


def cmd_seguimientos(args, cfg):
    if args.enviar:
        validar_envio(cfg)
    reg = cargar_json(REGISTRO, [])
    borradores, cambios = [], False
    for l in reg:
        if l["estado"] != "contactado":
            continue
        dias = (ahora() - dt.datetime.fromisoformat(l["fecha_ultimo_contacto"])).days
        if l["mensajes_sin_respuesta"] >= 2 and dias >= cfg["dias_para_sin_respuesta"]:
            l.update(estado="sin_respuesta", proximo_paso="ninguno", fecha_proximo_paso=None,
                     resumen=l["resumen"] + " Sin respuesta tras el seguimiento.")
            cambios = True
            print(f"- {l['nombre_empresa']}: marcado sin_respuesta")
            continue
        if l["mensajes_sin_respuesta"] != 1 or dias < cfg["dias_para_seguimiento"]:
            continue
        asunto, cuerpo = seguimiento(l, l["asunto"], cfg)
        if not args.enviar:
            guardar_borrador(borradores, l, asunto, cuerpo, "seguimiento")
            continue
        if not en_horario(l["zona_horaria"], cfg) or enviados_ultima_hora(reg) >= cfg["max_mensajes_por_hora"]:
            continue
        try:
            enviar_email(l["email"], asunto, cuerpo, en_respuesta_a=l.get("message_id"))
        except Exception as e:
            log_error(f"seguimiento a {l['id']} falló: {e}")
            continue
        fecha = ahora().isoformat(timespec="seconds")
        l["historial"].append({"fecha": fecha, "direccion": "saliente", "canal": "email", "tipo": "seguimiento"})
        l.update(fecha_ultimo_contacto=fecha, mensajes_sin_respuesta=2, resumen=l["resumen"] + " Seguimiento enviado.",
                 proximo_paso="marcar sin_respuesta si no contesta",
                 fecha_proximo_paso=(ahora() + dt.timedelta(days=cfg["dias_para_sin_respuesta"])).date().isoformat())
        cambios = True
        print(f"+ {l['nombre_empresa']}: seguimiento enviado")
    if cambios:
        guardar_registro(reg)
    if not args.enviar:
        escribir_borradores(borradores)


def cmd_registrar(args, cfg):
    reg = cargar_json(REGISTRO, [])
    lead = next((l for l in reg if l["id"] == args.id), None)
    if not lead:
        sys.exit(f"No existe el lead {args.id} en el registro")
    if lead["estado"] == "baja" and args.estado != "baja":
        sys.exit("Este lead pidió la baja: no se puede reactivar.")
    fecha = ahora().isoformat(timespec="seconds")
    lead.update(estado=args.estado, fecha_ultimo_contacto=fecha, mensajes_sin_respuesta=0)
    if args.canal:
        lead["canal"] = args.canal
    if args.resumen:
        lead["resumen"] = args.resumen
    lead["proximo_paso"] = args.proximo or ("ninguno" if args.estado in FINALES else lead.get("proximo_paso"))
    lead["fecha_proximo_paso"] = args.fecha if args.estado not in FINALES else None
    lead["historial"].append({"fecha": fecha, "direccion": "evento", "canal": lead["canal"], "tipo": args.estado})
    if args.estado == "venta_cerrada":
        if not (args.plan and args.precio and args.pago):
            sys.exit("Para venta_cerrada indicá --plan, --precio y --pago")
        aviso = {"fecha": fecha, "para": cfg["responsable_ventas"], "canal": cfg["canal_interno"],
                 "cliente": {k: lead.get(k) for k in ("id", "nombre_empresa", "email", "telefono", "pais", "ciudad")},
                 "responsable_cliente": args.responsable, "plan": args.plan, "precio_final": args.precio,
                 "forma_pago": args.pago}
        with open(VENTAS, "a", encoding="utf-8") as f:
            f.write(json.dumps(aviso, ensure_ascii=False) + "\n")
        lead.setdefault("pago_verificado", False)        # lo marca una persona, nunca un agente
        lead.setdefault("pago_final_verificado", False)
        lead["venta"] = {"plan": args.plan, "precio_final": args.precio, "forma_pago": args.pago,
                         "responsable_cliente": args.responsable, "fecha": fecha}
        lead["proximo_paso"] = "juntar materiales y generar el brief"
        print(f"Venta registrada. Avisar a {cfg['responsable_ventas']} por {cfg['canal_interno']}:\n"
              + json.dumps(aviso, ensure_ascii=False, indent=2))
        print(f"\nSiguiente: python3 contactador.py brief {lead['id']}")
    guardar_registro(reg)
    print(f"{lead['nombre_empresa']}: {args.estado}")


def tipo_plan(plan):
    p = (plan or "").lower()
    if "tienda" in p or "store" in p:
        return "tienda"
    if "profes" in p:
        return "profesional"
    return "basico"


# Lo que incluye cada plan según el agente programador (prompts/agente_programador.md).
SECCIONES = {
    "basico": ["Inicio", "Servicios", "Sobre nosotros", "Ubicación", "Contacto"],
    "profesional": ["Inicio", "Nosotros", "Servicios", "Galería", "Contacto"],
    "tienda": ["Inicio", "Catálogo", "Carrito", "Nosotros", "Contacto"],
}


def plantilla_brief(lead):
    """Formato de entrada del agente programador.
    Convención: "" o [] = todavía no se le pidió al cliente; null = el cliente confirmó que no tiene."""
    venta = lead.get("venta", {})
    plan = tipo_plan(venta.get("plan"))
    return {
        "id": lead["id"],
        "nombre_empresa": lead["nombre_empresa"],
        "rubro": lead.get("rubro") or "",
        "pais": lead["pais"],
        "idioma_sitio": lead.get("idioma_contacto") or ("es" if lead["pais"] == "AR" else "en"),
        "plan": plan,
        "contacto_responsable": {"nombre": venta.get("responsable_cliente") or "",
                                 "email": lead.get("email") or "", "telefono": lead.get("telefono") or ""},
        "descripcion_negocio": "",
        "objetivo_sitio": "",
        "secciones": SECCIONES[plan],
        "servicios_o_productos": [{"nombre": "", "descripcion": "", "precio": ""}],
        "colores_y_estilo": "",
        "referencias": [],
        "dominio": "",
        "redes": {"instagram": "", "facebook": "", "whatsapp": ""},
        "direccion_y_horarios": "",
        "materiales": {"logo": "", "fotos": [], "textos": None},
        "notas_venta": lead.get("resumen") or "",
    }


def faltantes_brief(b):
    """Lo que hay que pedirle al cliente antes de cerrar el brief."""
    falta = []
    if b.get("plan") not in SECCIONES:
        falta.append("plan (basico / profesional / tienda)")
    if b.get("idioma_sitio") not in ("es", "en", "ambos"):
        falta.append("idioma del sitio (es / en / ambos)")
    c = b.get("contacto_responsable", {})
    for k, texto in [("nombre", "nombre del responsable"), ("email", "email del responsable"),
                     ("telefono", "teléfono del responsable")]:
        if not str(c.get(k) or "").strip():
            falta.append(texto)
    for campo, texto in [("descripcion_negocio", "descripción del negocio"), ("objetivo_sitio", "objetivo del sitio"),
                         ("colores_y_estilo", "colores y estilo"),
                         ("direccion_y_horarios", "dirección y horarios de atención")]:
        if not str(b.get(campo) or "").strip():
            falta.append(texto)
    if b.get("dominio") == "":
        falta.append("dominio (el que tiene o quiere registrar; null si lo elegimos nosotros)")
    if not b.get("secciones"):
        falta.append("secciones")
    elif b.get("plan") == "profesional" and len(b["secciones"]) > 5:
        falta.append("el Plan Profesional incluye hasta 5 secciones: ajustar o cotizar extra")
    redes = b.get("redes") or {}
    sin_pedir = [k for k in ("instagram", "facebook", "whatsapp") if redes.get(k) == ""]
    if sin_pedir:
        falta.append("redes: " + ", ".join(sin_pedir) + " (null si no tiene)")
    items = [i for i in b.get("servicios_o_productos", []) if str(i.get("nombre") or "").strip()]
    tienda = b.get("plan") == "tienda"
    if not items:
        falta.append("lista de productos con precio" if tienda else "lista de servicios")
    elif tienda:
        if any(not str(i.get("precio") or "").strip() for i in items):
            falta.append("precio de todos los productos")
        if len(items) > 50:
            falta.append(f"el Plan Tienda incluye hasta 50 productos (hay {len(items)}): ajustar o cotizar extra")
    mat = b.get("materiales") or {}
    if mat.get("logo") == "":
        falta.append("logo (null si no tiene)")
    if mat.get("fotos") == []:
        falta.append("fotos (null si no tiene)")
    return falta


def cmd_brief(args, cfg):
    reg = cargar_json(REGISTRO, [])
    lead = next((l for l in reg if l["id"] == args.id), None)
    if not lead:
        sys.exit(f"No existe el lead {args.id} en el registro")
    if lead["estado"] != "venta_cerrada":
        sys.exit("El brief se genera solo para ventas cerradas.")
    os.makedirs(BRIEFS, exist_ok=True)
    datos = os.path.join(BRIEFS, f"datos_brief_{args.id}.json")
    if not os.path.exists(datos):
        with open(datos, "w", encoding="utf-8") as f:
            json.dump(plantilla_brief(lead), f, ensure_ascii=False, indent=2)
        print(f"Plantilla creada en {datos}. Completala con lo que mande el cliente y volvé a correr este comando.")
    with open(datos, encoding="utf-8") as f:
        brief = json.load(f)
    falta = faltantes_brief(brief)
    if falta:
        print("Falta pedirle al cliente:\n- " + "\n- ".join(falta))
        lead["proximo_paso"] = "pedir al cliente: " + ", ".join(falta)
        guardar_registro(reg)
        return
    salida = os.path.join(BRIEFS, f"brief_{args.id}.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)
    lead.update(proximo_paso="desarrollo del sitio (agente programador)", fecha_proximo_paso=None)
    lead["historial"].append({"fecha": ahora().isoformat(timespec="seconds"), "direccion": "evento",
                              "canal": "interno", "tipo": "brief_generado"})
    guardar_registro(reg)
    print(f"Brief listo para el programador: {salida}")
    if not lead.get("pago_verificado"):
        print("Ojo: el programador no arranca hasta que una persona marque pago_verificado = true.")


def cmd_pendientes(args, cfg):
    """Avisos del programador (faltantes_/extras_) que hay que gestionar con el cliente."""
    reg = {l["id"]: l for l in cargar_json(REGISTRO, [])}
    avisos = sorted(f for f in os.listdir(BRIEFS) if f.startswith(("faltantes_", "extras_"))) \
        if os.path.isdir(BRIEFS) else []
    if not avisos:
        print("No hay avisos del programador.")
    for f in avisos:
        pid = f.split("_", 1)[1].rsplit(".", 1)[0]
        nombre = reg.get(pid, {}).get("nombre_empresa", pid)
        tipo = "Faltan materiales" if f.startswith("faltantes_") else "Pedido fuera del plan (cotizar)"
        with open(os.path.join(BRIEFS, f), encoding="utf-8") as fh:
            print(f"## {nombre} — {tipo}\n{fh.read().strip()}\n")

def cmd_estado(args, cfg):
    for l in cargar_json(REGISTRO, []):
        print(f"{l['estado']:<18} {l['pais']}  {l['nombre_empresa'][:35]:<35} próximo: "
              f"{l.get('proximo_paso')} ({l.get('fecha_proximo_paso')})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("procesar"); p.add_argument("archivo"); p.add_argument("--enviar", action="store_true")
    s = sub.add_parser("seguimientos"); s.add_argument("--enviar", action="store_true")
    r = sub.add_parser("registrar")
    r.add_argument("id"); r.add_argument("--estado", required=True, choices=ESTADOS)
    r.add_argument("--resumen"); r.add_argument("--proximo"); r.add_argument("--fecha")
    r.add_argument("--canal", choices=["email", "whatsapp", "llamada"])
    r.add_argument("--plan"); r.add_argument("--precio"); r.add_argument("--pago"); r.add_argument("--responsable")
    b = sub.add_parser("brief"); b.add_argument("id")
    sub.add_parser("pendientes")
    sub.add_parser("estado")
    args = ap.parse_args()
    cfg = cargar_json(CONFIG, None)
    if cfg is None:
        sys.exit("Falta config_contacto.json")
    {"procesar": cmd_procesar, "seguimientos": cmd_seguimientos,
     "registrar": cmd_registrar, "brief": cmd_brief, "pendientes": cmd_pendientes, "estado": cmd_estado}[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
