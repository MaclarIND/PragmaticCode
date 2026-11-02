"""Utilidades compartidas por los tres agentes: rutas, reloj, archivos JSON, configuración, logs y la API de Claude.

Sin dependencias externas: la API de Claude se llama con urllib. Clave en la variable de entorno ANTHROPIC_API_KEY.
Si no hay clave, o si SV_SIMULACION=1, `llamar_claude` devuelve None y cada agente usa su respuesta de respaldo
(determinista, sin red): así `simular.py` corre completo sin gastar ni un token.
"""
import datetime as dt
import json
import os
import random
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

AGENTES = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("SV_BASE") or os.path.dirname(AGENTES)   # sistema_ventas/ (simular.py lo apunta a una carpeta aparte)
RAIZ = os.environ.get("SV_RAIZ") or os.path.dirname(os.path.dirname(AGENTES))  # repo: .env, config_contacto.json, leads_contactados.json
sys.path.insert(0, os.path.dirname(os.path.dirname(AGENTES)))
try:
    import entorno  # noqa: F401  carga el .env del repo si existe
except ImportError:
    pass

PLAYBOOK = os.path.join(BASE, "playbook.json")
LEADS_ENTRADA = os.path.join(BASE, "leads", "entrada")
LEADS_PROCESADOS = os.path.join(BASE, "leads", "procesados")
RESPUESTAS_ENTRADA = os.path.join(BASE, "respuestas", "entrada")
RESPUESTAS_PROCESADAS = os.path.join(BASE, "respuestas", "procesadas")
CONVERSACIONES = os.path.join(BASE, "conversaciones")
HISTORIAL = os.path.join(BASE, "historial")
REPORTES = os.path.join(BASE, "reportes")
AUDITORIAS = os.path.join(BASE, "auditorias")
LOGS = os.path.join(BASE, "logs")
ALERTAS = os.path.join(BASE, "alertas.md")
BAJAS = os.path.join(BASE, "bajas.json")
REGISTRO_VIEJO = os.path.join(RAIZ, "leads_contactados.json")   # memoria del vendedor anterior: no se contacta a nadie que esté ahí
NOTIFICACIONES = os.path.join(RAIZ, "notificaciones_ventas.jsonl")
BRIEFS = os.path.join(RAIZ, "briefs")
PROMPTS = os.path.join(AGENTES, "prompts")

SEGMENTOS = ("AR_sin_web", "AR_con_web", "US_sin_web", "US_con_web")
CATEGORIAS_OBJECION = ("ya_tengo_web", "precio", "no_necesito", "desconfianza")
MIN_ENVIADOS_VARIANTE = int(os.environ.get("SV_MIN_ENVIADOS_VARIANTE", "10"))   # regla 4: hasta acá se usa para juntar datos
MIN_ENVIADOS_PODA = int(os.environ.get("SV_MIN_ENVIADOS_PODA", "30"))           # paso 2 del Agente 2
MODELO = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
TZ_AR = "America/Argentina/Buenos_Aires"

# Precios vigentes (los mismos que prompts/agente_contacto.md). Solo se mencionan si el lead pregunta.
PRECIOS = {
    "AR": {"moneda": "ARS", "basico": "$380.000", "profesional": "$850.000", "tienda": "$1.400.000",
           "mantenimiento": "$35.000/mes", "hosting_2do_anio": "$50.000/año", "pago": "50% de seña y 50% contra entrega; se puede en 2 o 3 cuotas"},
    "US": {"moneda": "USD", "basico": "USD 690", "profesional": "USD 1,690", "tienda": "USD 2,900",
           "mantenimiento": "USD 59/month", "hosting_2do_anio": "USD 120/year", "pago": "50% deposit and 50% on delivery"},
}


# ---------- reloj (simular.py lo adelanta con SV_OFFSET_DIAS) ----------
def ahora():
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=float(os.environ.get("SV_OFFSET_DIAS", "0")))


def iso(t=None):
    return (t or ahora()).isoformat(timespec="seconds")


def dias_desde(ts):
    return (ahora() - dt.datetime.fromisoformat(ts)).total_seconds() / 86400


def zona_horaria(lead):
    return lead.get("zona_horaria") or (TZ_AR if lead.get("pais") == "AR" else "America/New_York")


def en_horario(lead, cfg):
    """Solo lunes a viernes, de hora_inicio a hora_fin, en la zona horaria del cliente."""
    if os.environ.get("SV_SIMULACION") == "1":
        return True
    local = ahora().astimezone(ZoneInfo(zona_horaria(lead)))
    return local.weekday() < 5 and cfg["hora_inicio"] <= local.hour < cfg["hora_fin"]


# ---------- archivos ----------
def leer_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def escribir_json(path, datos):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def leer_texto(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def config():
    """config_contacto.json del repo (firma, portfolio, dirección, derivación, horarios) con valores por defecto."""
    cfg = {"firma": "Lucas — Pragmatic Code", "empresa": "Pragmatic Code", "portfolio_link": "https://www.pragmatic-code.com",
           "direccion_fisica": "", "derivacion_nombre": "Lucas", "derivacion_telefono": "", "canal_interno": "",
           "responsable_ventas": "Lucas", "max_mensajes_por_hora": 20, "hora_inicio": 9, "hora_fin": 18}
    cfg.update({k: v for k, v in (leer_json(os.path.join(RAIZ, "config_contacto.json"), {}) or {}).items()
                if v not in (None, "") and not (isinstance(v, str) and v.startswith("["))})
    return cfg


def log(agente, msg):
    os.makedirs(LOGS, exist_ok=True)
    linea = f"{iso()} [{agente}] {msg}"
    with open(os.path.join(LOGS, f"{ahora():%Y-%m-%d}.log"), "a", encoding="utf-8") as f:
        f.write(linea + "\n")
    print(linea)


def segmento_de(lead):
    return f"{lead['pais']}_{'con' if lead.get('tiene_web') else 'sin'}_web"


def listar_conversaciones():
    for n in sorted(os.listdir(CONVERSACIONES)) if os.path.exists(CONVERSACIONES) else []:
        if n.endswith(".json"):
            yield leer_json(os.path.join(CONVERSACIONES, n))


def excluidos():
    """IDs, emails y teléfonos a los que no se escribe: bajas del sistema nuevo + todo el registro del vendedor anterior."""
    ex = set()
    for b in leer_json(BAJAS, []) or []:
        ex.update(x for x in (b.get("lead_id"), b.get("email"), b.get("telefono")) if x)
    for l in leer_json(REGISTRO_VIEJO, []) or []:
        ex.update(x.lower() if isinstance(x, str) else x for x in (l.get("id"), l.get("email"), l.get("telefono")) if x)
    return ex


# ---------- API de Claude ----------
def llamar_claude(system, usuario, max_tokens=1200):
    """Devuelve el texto de la respuesta, o None si no hay clave / estamos en simulación / falla la red."""
    clave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not clave or os.environ.get("SV_SIMULACION") == "1":
        return None
    cuerpo = json.dumps({"model": MODELO, "max_tokens": max_tokens, "system": system,
                         "messages": [{"role": "user", "content": usuario}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=cuerpo, headers={
        "x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                datos = json.load(r)
            return "".join(b.get("text", "") for b in datos.get("content", []))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            log("claude", f"error en la API (intento {intento + 1}): {e}")
    return None


def extraer_json(texto):
    """Saca el primer objeto JSON de una respuesta del modelo (tolera ```json ... ```)."""
    if not texto:
        return None
    i, j = texto.find("{"), texto.rfind("}")
    if i < 0 or j < 0:
        return None
    try:
        return json.loads(texto[i:j + 1])
    except json.JSONDecodeError:
        return None


def azar(semilla):
    return random.Random(str(semilla))
