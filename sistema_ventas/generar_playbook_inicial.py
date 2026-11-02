"""Genera playbook.json v1 desde cero. Solo para arrancar: una vez en uso, playbook.json lo escribe el Agente 2."""
import json, datetime, os
AQUI = os.path.dirname(os.path.abspath(__file__))
HOY = datetime.date.today().isoformat()
def V(i, texto, canal="ambos"):
    return {"id": i, "texto": texto, "canal": canal, "enviados": 0, "puntos": 0, "tasa": 0.0, "activa": True,
            "mutacion": None, "creada": HOY, "motivo_baja": None, "pendiente_aprobacion": False}
def grupo(prefijo, textos, canal="ambos"):
    return [V(f"{prefijo}{n}", t, canal) for n, t in enumerate(textos, 1)]

apertura = {
 # dimensión que varía: gancho/oferta (1 = pregunta sobre el problema, 2 = oferta rápida, 3 = oferta sin costo inicial)
 "AR_sin_web": grupo("AR-SW-A", [
  "Hola, vi {dato_observable} de {nombre}. Busqué su web y no encontré ninguna. ¿Hoy los clientes nuevos te llegan solo por Maps y boca en boca?",
  "Hola, vi {dato_observable} de {nombre}. Busqué su web y no encontré ninguna. Armamos páginas para {rubro} listas en una semana. ¿Te sirve tener una?",
  "Hola, vi {dato_observable} de {nombre}. Busqué su web y no encontré ninguna. Te la armamos sin costo inicial y solo pagás el mantenimiento mensual. ¿Te interesa?"]),
 "AR_con_web": grupo("AR-CW-A", [
  "Hola, vi {dato_observable} de {nombre} y entré a su web. ¿Te llegan consultas desde la página o la mayoría viene por otro lado?",
  "Hola, vi {dato_observable} de {nombre} y entré a su web. Hacemos rediseños para {rubro} listos en una semana. ¿Pensaste en renovarla?",
  "Hola, vi {dato_observable} de {nombre} y entré a su web. La rediseñamos sin costo inicial y solo pagás el mantenimiento mensual. ¿Te interesa?"]),
 "US_sin_web": grupo("US-SW-A", [
  "Hi, I saw {dato_observable} about {nombre} and couldn't find a website. Do new customers mostly find you through Google Maps and word of mouth?",
  "Hi, I saw {dato_observable} about {nombre} and couldn't find a website. We build sites for {rubro} businesses, ready in a week. Would one be useful for you?",
  "Hi, I saw {dato_observable} about {nombre} and couldn't find a website. We can build one with no upfront cost, you'd just pay monthly maintenance. Interested?"], "email"),
 "US_con_web": grupo("US-CW-A", [
  "Hi, I saw {dato_observable} about {nombre} and checked out your website. Do you get inquiries through it, or do most customers come from somewhere else?",
  "Hi, I saw {dato_observable} about {nombre} and checked out your website. We redesign sites for {rubro} businesses in a week. Have you thought about a refresh?",
  "Hi, I saw {dato_observable} about {nombre} and checked out your website. We can redesign it with no upfront cost, you'd just pay monthly maintenance. Interested?"], "email"),
}

seguimiento = {
 # dimensión: gancho (1 = pregunta directa, 2 = Google, 3 = plantilla a su gusto)
 "AR_sin_web": grupo("AR-SW-S", [
  "Te escribo de nuevo por lo de la web de {nombre}. ¿Es algo que te interesa este año o lo dejamos acá?",
  "Te escribo de nuevo por lo de la web de {nombre}. Sin página, el que te busca en Google solo tiene la ficha de Maps para decidir. ¿Te interesa sumar una?",
  "Te escribo de nuevo por lo de la web de {nombre}. Partimos de una plantilla y la adaptamos a tu gusto: colores, fotos y textos. ¿Te interesa?"]),
 "AR_con_web": grupo("AR-CW-S", [
  "Te escribo de nuevo por lo de la web de {nombre}. ¿Es algo que querés renovar este año o lo dejamos acá?",
  "Te escribo de nuevo por lo de la web de {nombre}. La página suele ser lo primero que miran antes de escribirte. ¿Te interesa mejorarla?",
  "Te escribo de nuevo por lo de la web de {nombre}. Partimos de una plantilla y la adaptamos a tu gusto: colores, fotos y textos. ¿Te interesa?"]),
 "US_sin_web": grupo("US-SW-S", [
  "Following up on the website idea for {nombre}. Is it something you'd consider this year, or should I leave it here?",
  "Following up on the website idea for {nombre}. Without a site, people who find you on Google only have your Maps listing to decide. Worth adding one?",
  "Following up on the website idea for {nombre}. We start from a template and tailor it to your taste: colors, photos and copy. Interested?"], "email"),
 "US_con_web": grupo("US-CW-S", [
  "Following up on your website for {nombre}. Is a refresh something you'd consider this year, or should I leave it here?",
  "Following up on your website for {nombre}. It's usually the first thing people check before contacting you. Worth improving it?",
  "Following up on your website for {nombre}. We start from a template and tailor it to your taste: colors, photos and copy. Interested?"], "email"),
}

def obj_ar(cw):
    return {
  # ya_tengo_web — dimensión: argumento
  "ya_tengo_web": [
   "Bien, entonces no arrancás de cero. ¿Te trae clientes hoy o está más de presencia?",
   "Bien. No hace falta tirarla: se puede renovar el diseño y dejar lo que funciona. ¿Qué es lo que menos te gusta de la actual?",
   "Bien. Muchas veces el problema es que en el celular se ve mal y la gente se va. ¿La probaste desde el teléfono?"],
  # precio — dimensión: argumento
  "precio": [
   "Entiendo. Con un cliente nuevo por mes ya se paga sola. ¿Cuánto te deja un cliente promedio?",
   "Entiendo. Hay una versión más simple, de una sola página, que sale bastante menos. ¿Te paso esa opción?",
   "Entiendo. Se puede pagar en cuotas, o arrancar sin costo inicial y pagar solo el mantenimiento. ¿Alguna de las dos te sirve?"],
  # no_necesito — dimensión: argumento
  "no_necesito": [
   "Dale, lo respeto. ¿Hoy tenés todos los clientes que podés atender?",
   "Dale. Solo te digo que la mayoría busca en Google antes de escribir a un negocio. ¿Te pasa que te pregunten si tenés página?",
   "Dale, sin problema. ¿Te escribo en unos meses por si cambia algo?"],
  # desconfianza — dimensión: argumento
  "desconfianza": [
   "Es lógico. Acá tenés trabajos nuestros: {portfolio}. ¿Querés que hablemos 10 minutos por teléfono?",
   "Es lógico. Pagás la mitad para arrancar y el resto recién cuando ves la página terminada y te gusta. ¿Así te queda más tranquilo?",
   "Es lógico. Somos Pragmatic Code, pragmatic-code.com, y la página queda a tu nombre con todos los accesos. ¿Qué te gustaría saber antes de decidir?"],
 }

def obj_us(cw):
    return {
  "ya_tengo_web": [
   "Great, so you're not starting from scratch. Is it bringing you customers today, or is it more of a placeholder?",
   "Great. No need to throw it away: we can refresh the design and keep what works. What do you like least about the current one?",
   "Great. Often the issue is that it looks off on phones and people leave. Have you checked it from your phone lately?"],
  "precio": [
   "Understood. One new customer a month usually covers it. What's an average customer worth to you?",
   "Understood. There's a simpler one-page version that costs quite a bit less. Want me to send that option?",
   "Understood. You can start with no upfront cost and just pay monthly maintenance. Would that work better?"],
  "no_necesito": [
   "Fair enough. Are you getting all the customers you can handle right now?",
   "Fair enough. Most people check Google before contacting a business. Do customers ever ask if you have a website?",
   "No problem at all. Mind if I check back in a few months in case things change?"],
  "desconfianza": [
   "Makes sense. Here's some of our work: {portfolio}. Would a quick 10-minute call help?",
   "Makes sense. You pay half to start and the rest only once you see the finished site and like it. Does that help?",
   "Makes sense. We're Pragmatic Code (pragmatic-code.com), and the site is registered in your name with full access. What would you like to know before deciding?"],
 }

cierre = {
 # dimensión: pregunta final
 "AR": ["Buenísimo. ¿Arrancamos? Te paso el link para la seña y te pido logo y fotos.",
        "Buenísimo. ¿Preferís que arranquemos esta semana o la próxima?",
        "Buenísimo. ¿Te armo la propuesta con lo que hablamos para que la veas tranquilo?"],
 "US": ["Great. Shall we get started? I'll send the deposit link and ask for your logo and photos.",
        "Great. Would you rather start this week or next?",
        "Great. Want me to put together a proposal with what we discussed so you can review it?"],
}

pb = {"version": 1, "apertura": apertura, "seguimiento_sin_respuesta": seguimiento,
      "objeciones": {k: {} for k in ("ya_tengo_web", "precio", "no_necesito", "desconfianza")}, "cierre": {}}
for seg in ("AR_sin_web", "AR_con_web", "US_sin_web", "US_con_web"):
    pais, cw = seg[:2], seg.endswith("con_web")
    ob = (obj_ar if pais == "AR" else obj_us)(cw)
    sig = seg.replace("_sin_web", "-SW").replace("_con_web", "-CW")
    for cat, textos in ob.items():
        pre = {"ya_tengo_web": "YW", "precio": "PR", "no_necesito": "NN", "desconfianza": "DF"}[cat]
        pb["objeciones"][cat][seg] = grupo(f"{sig}-{pre}", textos)
    pb["cierre"][seg] = grupo(f"{sig}-C", cierre[pais])

out = os.path.join(AQUI, "playbook.json")
for seg, vs in pb["apertura"].items():
    for v in vs:
        if "sin costo inicial" in v["texto"] or "no upfront cost" in v["texto"]:
            v["pendiente_aprobacion"] = True
json.dump(pb, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
# vista legible
L = ["# Playbook inicial v1 — para aprobar", "",
     "Marcadores que el agente reemplaza: `{nombre}`, `{rubro}`, `{dato_observable}`, `{portfolio}`.", ""]
def sec(titulo, d, nota=""):
    L.append(f"## {titulo}"); 
    if nota: L.append(f"_{nota}_")
    L.append("")
    for seg, vs in d.items():
        L.append(f"**{seg}** (canal: {vs[0]['canal']})"); L.append("")
        for v in vs: L.append(f"- `{v['id']}`{' (pendiente de aprobación)' if v['pendiente_aprobacion'] else ''} {v['texto']}")
        L.append("")
sec("Apertura", apertura, "Varía solo el gancho/oferta: 1 = pregunta sobre cómo les llegan clientes · 2 = lista en una semana · 3 = sin costo inicial + mantenimiento")
sec("Seguimiento sin respuesta (día 3 y día 7)", seguimiento, "Varía solo el gancho: 1 = pregunta directa · 2 = Google · 3 = plantilla adaptada a su gusto")
for cat in pb["objeciones"]:
    sec(f"Objeción: {cat}", pb["objeciones"][cat], "Varía solo el argumento")
sec("Cierre", pb["cierre"], "Varía solo la pregunta final")
open(os.path.join(AQUI, "playbook_inicial_para_aprobar.md"), "w", encoding="utf-8").write("\n".join(L))
n = sum(len(v) for g in [apertura, seguimiento, pb["cierre"]] for v in g.values()) + sum(len(v) for c in pb["objeciones"].values() for v in c.values())
print("variantes", n)
