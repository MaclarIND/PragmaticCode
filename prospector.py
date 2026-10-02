#!/usr/bin/env python3
"""Agente de prospección: busca comercios en AR y US que necesiten una web
y genera leads_AAAA-MM-DD_HHMM.json para el agente de contacto.

Uso:
    GOOGLE_PLACES_API_KEY=... python3 prospector.py            # 5 AR + 5 US
    GOOGLE_PLACES_API_KEY=... python3 prospector.py --pais AR  # 10 AR
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import entorno  # noqa: F401  carga .env si existe

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip().strip("\"'")  # comillas o espacios pegados al copiar
PLACES = "https://places.googleapis.com/v1"
PAUSA_API = 1.0  # segundos entre requests a Places
PAUSA_WEB = 1.5  # segundos entre requests a webs de negocios
MAX_LEADS = 10
MIN_RESENAS = 10
BASE = os.path.dirname(os.path.abspath(__file__))
CONTACTADOS = os.path.join(BASE, "leads_contactados.json")
LOG = os.path.join(BASE, "log_errores.txt")
UA = "Mozilla/5.0 (compatible; LeadProspector/1.0)"

CIUDADES = {
    "AR": [
        ("CABA", "America/Argentina/Buenos_Aires"),
        ("Gran Buenos Aires", "America/Argentina/Buenos_Aires"),
        ("Córdoba", "America/Argentina/Cordoba"),
        ("Rosario", "America/Argentina/Buenos_Aires"),
        ("Mendoza", "America/Argentina/Mendoza"),
        ("La Plata", "America/Argentina/Buenos_Aires"),
        ("Mar del Plata", "America/Argentina/Buenos_Aires"),
        ("San Miguel de Tucumán", "America/Argentina/Tucuman"),
    ],
    "US": [
        ("Miami", "America/New_York"),
        ("Houston", "America/Chicago"),
        ("Dallas", "America/Chicago"),
        ("Phoenix", "America/Phoenix"),
        ("Orlando", "America/New_York"),
        ("Atlanta", "America/New_York"),
        ("Los Angeles", "America/Los_Angeles"),
        ("New York", "America/New_York"),
        ("Chicago", "America/Chicago"),
        ("San Antonio", "America/Chicago"),
    ],
}
# Ciudades con fuerte comunidad hispana: también se busca en español.
HISPANAS = {"Miami", "Houston", "Dallas", "Phoenix", "Orlando", "Los Angeles", "San Antonio"}

RUBROS = [
    # (rubro, query ES, query EN)
    ("Restaurante", "restaurante", "restaurant"),
    ("Cafetería", "cafetería", "coffee shop"),
    ("Peluquería / barbería", "peluquería", "barber shop"),
    ("Taller mecánico", "taller mecánico", "auto repair shop"),
    ("Consultorio odontológico", "odontólogo", "dentist"),
    ("Kinesiología", "kinesiólogo", "physical therapy clinic"),
    ("Gimnasio", "gimnasio", "gym"),
    ("Inmobiliaria", "inmobiliaria", "real estate agency"),
    ("Plomería", "plomero", "plumber"),
    ("Electricista", "electricista", "electrician"),
    ("Limpieza", "empresa de limpieza", "cleaning service"),
    ("Landscaping / jardinería", "jardinería y paisajismo", "landscaping company"),
    ("Construcción", "empresa de construcción", "construction contractor"),
    ("Estudio contable", "estudio contable", "accounting firm"),
    ("Estudio jurídico", "estudio jurídico", "law firm"),
    ("Tienda de ropa", "tienda de ropa", "clothing store"),
    ("Veterinaria", "veterinaria", "veterinarian"),
]

SOCIAL = ("instagram.com", "facebook.com", "fb.com", "linktr.ee", "linktree", "wa.me",
          "whatsapp.com", "tiktok.com", "business.site")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")
EMAIL_BASURA = ("example.", "sentry", "wixpress", "domain.com", "email.com", "yourdomain",
                "godaddy", "@2x", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", "u003e")


def log_error(msg):
    ts = dt.datetime.now().isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{ts} {msg}\n")
    print(f"[error] {msg}", file=sys.stderr)


def http(url, data=None, headers=None, timeout=15):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read(2_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        cuerpo = e.read(20_000).decode("utf-8", "replace")
        try:  # Google devuelve {"error": {"message": ...}}: mostrar el motivo real
            cuerpo = json.loads(cuerpo)["error"]["message"]
        except Exception:
            cuerpo = cuerpo[:300]
        raise RuntimeError(f"HTTP {e.code}: {cuerpo}") from None


def places_search(query, lang, region):
    body = json.dumps({"textQuery": query, "languageCode": lang, "regionCode": region,
                       "pageSize": 20}).encode()
    _, _, txt = http(f"{PLACES}/places:searchText", data=body, headers={
        "Content-Type": "application/json", "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.id,places.userRatingCount,places.businessStatus,places.websiteUri",
    })
    time.sleep(PAUSA_API)
    return json.loads(txt).get("places", [])


def place_details(pid, lang):
    fields = ("id,displayName,formattedAddress,internationalPhoneNumber,websiteUri,rating,"
              "userRatingCount,businessStatus,primaryTypeDisplayName,editorialSummary,reviews")
    _, _, txt = http(f"{PLACES}/places/{pid}?languageCode={lang}", headers={
        "X-Goog-Api-Key": API_KEY, "X-Goog-FieldMask": fields})
    time.sleep(PAUSA_API)
    return json.loads(txt)


def fetch(url):
    try:
        st, final, body = http(url)
        time.sleep(PAUSA_WEB)
        return st, final, body
    except Exception as e:  # caída, DNS, SSL, timeout
        time.sleep(PAUSA_WEB)
        return None, url, str(e)


def evaluar_web(url):
    """Devuelve el problema detectado o None si la web parece aceptable."""
    if not url:
        return "no tiene web"
    host = urllib.parse.urlparse(url).netloc.lower()
    if any(s in host for s in SOCIAL):
        red = ("Instagram" if "instagram" in host else "Facebook" if "fb" in host or "facebook" in host
               else "Linktree" if "linktr" in host else "WhatsApp" if "wa" in host
               else "Google Business Site" if "business.site" in host else "TikTok")
        return f"solo {red} como web"
    st, final, body = fetch(url)
    if st is None or st >= 400:
        return "web caída o con error"
    problemas = []
    if not final.lower().startswith("https://"):
        problemas.append("sin HTTPS")
    if not re.search(r'<meta[^>]+name=["\']viewport', body, re.I):
        problemas.append("no adaptada a celular")
    anios = [int(y) for y in re.findall(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(20\d{2}|19\d{2})",
                                        body, re.I)]
    if anios and max(anios) <= dt.date.today().year - 5:
        problemas.append(f"desactualizada (copyright {max(anios)})")
    return "web " + ", ".join(problemas) if problemas else None


def extraer_emails(texto, dominio=None):
    texto = html.unescape(urllib.parse.unquote(texto))
    encontrados = []
    for e in EMAIL_RE.findall(texto):
        e = e.strip(".").lower()
        if any(b in e for b in EMAIL_BASURA) or e in encontrados:
            continue
        encontrados.append(e)
    if dominio:  # preferir emails del propio dominio del negocio
        encontrados.sort(key=lambda e: 0 if e.endswith(dominio) else 1)
    return encontrados


def buscar_email(web):
    """Busca un email publicado por el propio negocio. Nunca lo adivina."""
    if not web:
        return None, None
    parsed = urllib.parse.urlparse(web)
    host = parsed.netloc.lower()
    if any(s in host for s in SOCIAL):
        candidatos = [web]  # perfil público de Instagram/Facebook/Linktree
    else:
        raiz = f"{parsed.scheme}://{parsed.netloc}"
        candidatos = [web] + [raiz + p for p in ("/contacto", "/contact", "/contact-us", "/contactanos")]
    dominio = host.removeprefix("www.")
    for url in candidatos:
        st, _, body = fetch(url)
        if st and st < 400:
            emails = extraer_emails(body, dominio)
            if emails:
                return emails[0], url
    return None, None


def idioma_us(det, query_es):
    nombre = det.get("displayName", {}).get("text", "")
    langs = [r.get("originalText", {}).get("languageCode", "") for r in det.get("reviews", [])]
    es = sum(1 for l in langs if l.startswith("es"))
    if (langs and es / len(langs) >= 0.5) or re.search(
            r"\b(el|la|los|las|taller|peluquer[ií]a|panader[ií]a|taquer[ií]a|servicios|limpieza)\b",
            nombre, re.I):
        return "es"
    return "en"


def cargar_excluidos():
    if not os.path.exists(CONTACTADOS):
        return set()
    try:
        with open(CONTACTADOS, encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("leads", data) if isinstance(data, dict) else data
        ids = set()
        for it in items:
            ids.add(it if isinstance(it, str) else it.get("id"))
        return ids
    except Exception as e:
        log_error(f"no se pudo leer leads_contactados.json: {e}")
        sys.exit(1)  # sin la lista de exclusión no es seguro seguir


def prospectar(pais, cupo, excluidos, vistos):
    leads, errores_seguidos = [], 0
    for ciudad, tz in CIUDADES[pais]:
        for rubro, q_es, q_en in RUBROS:
            consultas = []
            if pais == "AR":
                consultas.append((f"{q_es} en {ciudad}", "es", False))
            else:
                consultas.append((f"{q_en} in {ciudad}", "en", False))
                if ciudad in HISPANAS:
                    consultas.append((f"{q_es} en {ciudad}", "es", True))
            for query, lang, query_es in consultas:
                try:
                    resultados = places_search(query, lang, pais)
                    errores_seguidos = 0
                except Exception as e:
                    log_error(f"searchText '{query}': {e}")
                    errores_seguidos += 1
                    if errores_seguidos >= 3:  # casi siempre es la key o la API: no tiene sentido seguir
                        sys.exit("Google rechazó 3 búsquedas seguidas. Revisá el mensaje de arriba "
                                 "(API key, Places API (New) habilitada, facturación).")
                    continue
                for r in resultados:
                    pid = r.get("id")
                    if not pid or pid in vistos or pid in excluidos:
                        continue
                    vistos.add(pid)
                    # Prefiltro barato con los datos del search.
                    if r.get("businessStatus") != "OPERATIONAL" or r.get("userRatingCount", 0) < MIN_RESENAS:
                        continue
                    try:
                        lead = calificar(pid, lang, pais, ciudad, tz, rubro, query_es)
                    except Exception as e:
                        log_error(f"place {pid}: {e}")
                        continue
                    if lead:
                        leads.append(lead)
                        print(f"[{pais} {len(leads)}/{cupo}] {lead['nombre_empresa']} — {lead['problema_detectado']}")
                        if len(leads) >= cupo:
                            return leads
    return leads


def calificar(pid, lang, pais, ciudad, tz, rubro, query_es):
    det = place_details(pid, lang)
    if det.get("businessStatus") != "OPERATIONAL" or det.get("userRatingCount", 0) < MIN_RESENAS:
        return None
    telefono = (det.get("internationalPhoneNumber") or "").replace(" ", "").replace("-", "")
    if not telefono:
        return None
    web = det.get("websiteUri")
    problema = evaluar_web(web)
    if not problema:
        return None  # web aceptable: no califica
    email, fuente = buscar_email(web)
    if not email:
        return None  # sin email publicado: se descarta
    nombre = det.get("displayName", {}).get("text", "")
    tipo = det.get("primaryTypeDisplayName", {}).get("text", rubro)
    resumen = det.get("editorialSummary", {}).get("text")
    return {
        "id": pid,
        "nombre_empresa": nombre,
        "rubro": rubro,
        "descripcion": resumen or f"{tipo} en {ciudad}.",
        "pais": pais,
        "ciudad": ciudad,
        "direccion": det.get("formattedAddress", ""),
        "telefono": telefono,
        "email": email,
        "fuente_email": fuente,
        "web_actual": web or None,
        "problema_detectado": problema,
        "rating_google": det.get("rating"),
        "cantidad_resenas": det.get("userRatingCount"),
        "idioma_contacto": "es" if pais == "AR" else idioma_us(det, query_es),
        "zona_horaria": tz,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", choices=["AR", "US"], help="traer los 10 leads de un solo país")
    args = ap.parse_args()
    if not API_KEY:
        log_error("falta la variable de entorno GOOGLE_PLACES_API_KEY")
        sys.exit(1)

    cupos = {args.pais: MAX_LEADS} if args.pais else {"AR": 5, "US": 5}
    excluidos, vistos, leads = cargar_excluidos(), set(), []
    for pais, cupo in cupos.items():
        leads += prospectar(pais, cupo, excluidos, vistos)
    leads = leads[:MAX_LEADS]

    ahora = dt.datetime.now().astimezone()
    salida = os.path.join(BASE, f"leads_{ahora:%Y-%m-%d_%H%M}.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump({"fecha": ahora.isoformat(timespec="seconds"), "leads": leads}, f,
                  ensure_ascii=False, indent=2)
    print(f"{len(leads)} leads guardados en {salida}")
    if len(leads) < MAX_LEADS:
        log_error(f"solo se encontraron {len(leads)} leads calificados de {MAX_LEADS}")


if __name__ == "__main__":
    main()
