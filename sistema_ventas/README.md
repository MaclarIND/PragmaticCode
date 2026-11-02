# Sistema de ventas con aprendizaje — Pragmatic Code

Reemplaza al vendedor anterior (`contactador.py`) por tres agentes que comparten archivos y aprenden de los resultados.
Mantiene todas las reglas que ya tenía el vendedor (idioma, horarios, canales, precios, baja, honestidad, plantillas
personalizables, traspaso al programador): están en `agentes/prompts/ventas.md` y, las que son duras, en el código.

```
python scheduler.py          # lo deja corriendo: buzón+ventas cada 15 min · leads 1 vez/día · playbook cada hora (si corresponde) · auditor lunes 9:00
python simular.py            # prueba el ciclo completo con 50 leads falsos, sin red ni datos reales
python aprobar.py            # lista / aprueba / rechaza ofertas pendientes
python agentes/ventas.py     # cualquier agente también se corre a mano
```

Requisitos: Python 3.11+, sin librerías extra. Clave de Claude en la variable de entorno `ANTHROPIC_API_KEY` (o en el `.env`
del repo, igual que las demás). Modelo: `CLAUDE_MODEL` (por defecto `claude-sonnet-5-5`). Sin clave, los agentes corren
igual con respuestas de respaldo deterministas (útil para probar; no para vender).

## Cómo se envía solo (modo real)
Todo el envío real se activa con una sola variable en el `.env` del repo: `SV_MODO_REAL=1`. Sin ella, los conectores
solo loguean (es lo que usa `simular.py`). Con ella, `python scheduler.py` hace todo sin intervención:
busca leads una vez por día (si hay `GOOGLE_PLACES_API_KEY`), lee el buzón y manda aperturas, respuestas y seguimientos
cada 15 minutos, y aprende cada semana.

**Email (automático):** usa el SMTP de Gmail que ya configuraste para `contactador.py` (`SMTP_*`, contraseña de
aplicación). Las respuestas se leen solas por IMAP con las mismas credenciales (`agentes/buzon.py`): activá IMAP en
Gmail (Ver todos los ajustes → Reenvío y correo POP/IMAP → Habilitar IMAP). Se procesan solo los correos no leídos
de direcciones que tienen una conversación abierta; el resto no se toca. `python ../contactador.py probar-email --a-mi`
verifica el SMTP.

**WhatsApp:** hay dos situaciones.
- *Sin la API de Meta* (WhatsApp o WhatsApp Business común en el teléfono): no existe una forma permitida de que un
  programa mande mensajes desde ese número; las librerías que automatizan WhatsApp Web violan las condiciones de Meta y
  terminan con el número bloqueado, y escribir en frío a celulares es ilegal en EE.UU. (TCPA). Por eso el sistema abre
  siempre por email, y cuando un lead sigue por WhatsApp deja el mensaje listo en `whatsapp_pendientes.md` con un link
  `wa.me` que lo abre escrito en tu teléfono: un toque y sale. Es lo único que no es 100% automático.
- *Con la API oficial de Meta* (WhatsApp Business Platform, gratis hasta 1.000 conversaciones/mes): todo es automático.
  Variables: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, y para abrir conversaciones en Argentina `WHATSAPP_PLANTILLA_AR`
  (nombre de una plantilla aprobada por Meta con dos parámetros: {{1}} nombre del negocio, {{2}} dato observable).
  Las respuestas llegan por webhook: `python agentes/webhook_whatsapp.py` escucha en el puerto 8787; hay que exponerlo
  con HTTPS (Cloudflare Tunnel o ngrok) y cargar la URL en Meta for Developers → WhatsApp → Configuration → Webhook con
  `WEBHOOK_VERIFY_TOKEN`. Alta: business.facebook.com → WhatsApp Manager; podés migrar tu número actual de WhatsApp
  Business a la API (deja de funcionar en la app del teléfono).

**Leads:** `agentes/importar_leads.py` convierte los `leads_*.json` del buscador al formato de `leads/entrada/`
(el scheduler lo corre una vez por día con `--buscar`, que ejecuta `prospector.py` antes). También podés dejar
archivos a mano en `leads/entrada/`:
```json
{ "lead_id": "...", "nombre": "...", "rubro": "...", "pais": "AR|US", "email": "...", "telefono": "...",
  "tiene_web": true, "url_web": "...|null", "dato_observable": "texto corto sobre el negocio visible públicamente" }
```
Sin `email` no se contacta (salvo AR con plantilla de WhatsApp aprobada). No se escribe a nadie que esté en
`bajas.json` ni en `leads_contactados.json` del repo, y cada lead contactado se agrega ahí.

Firma, portfolio, dirección física (pie CAN-SPAM), persona para derivar, horario y límite por hora se leen de
`../config_contacto.json`.

## Qué hace cada agente
- **ventas.py (Agente 1):** aperturas, respuestas y seguimientos (día 3 y 7; cierre a los 14 días sin respuesta; después
  de un "no" no hay seguimientos y se cierra a los 7 días). Elige la variante por código (regla 4), respeta horario
  comercial del lead, límite por hora y canal. Puntaje al cerrar: 0 sin respuesta · 1 negativo · 2 pregunta · 3 pidió
  demo/precio · 4 pagó. Escribe `conversaciones/{lead_id}.json`. Si el lead pide una persona o algo fuera de los
  planes, deriva y avisa en `../notificaciones_ventas.jsonl`. Si pagó: avisa al responsable de ventas y deja
  `../briefs/datos_brief_{lead_id}.json` para el programador (los pagos los verifica una persona; el bot nunca).
- **playbook.py (Agente 2):** único que escribe `playbook.json`. Corre con 30 cerradas sin procesar o cada 7 días.
  Contabiliza → poda (≥30 envíos, tasa < mitad de la mejor; nunca menos de 2 activas por grupo) → muta (máx. 3, una sola
  cosa cambiada) → categorías nuevas de objeción (≥5 sin encajar) → alarma. Antes de escribir guarda la versión en
  `historial/`; deja `reportes/reporte_{fecha}.md`.
- **auditor.py (Agente 3):** lunes 9:00 lee las 20 cerradas más recientes con puntaje 1 o 2 y escribe
  `auditorias/auditoria_{fecha}.md` con los 3 errores más repetidos, 1 regla propuesta y 1 variante propuesta.
  No modifica nada: lo que proponga se aplica a mano en `prompts/ventas.md` o con el Agente 2.

## Ofertas pendientes de aprobación
Las variantes con `"pendiente_aprobacion": true` no se envían. Hoy son las 4 aperturas de "sin costo inicial, pagás
mantenimiento" (esa oferta no existe en la lista de precios: aprobarlas implica poder cumplirla). El Agente 2 también
deja ofertas pendientes cuando dispara la alarma (`alertas.md`).
```
python aprobar.py                      # lista
python aprobar.py AR-SW-A3 AR-CW-A3    # activa
python aprobar.py --rechazar US-SW-A3  # desactiva
```

## Dónde mirar
- `reportes/`: tabla de tasas por grupo, bajas, mutaciones, categorías nuevas, alertas (cada corrida del Agente 2).
- `alertas.md`: cuando ninguna de las últimas 100 conversaciones llegó a puntaje 3.
- `auditorias/`: la revisión semanal.
- `logs/AAAA-MM-DD.log`: cada envío (o stub), cierre y error.
- `../notificaciones_ventas.jsonl`: avisos para una persona (pagos a verificar, leads que piden hablar con alguien).

## Si algo no cierra
- Variables para pruebas: `SV_SIMULACION=1` (sin modelo, sin horario), `SV_MIN_ENVIADOS_PODA`, `SV_MIN_ENVIADOS_VARIANTE`,
  `SV_OFFSET_DIAS` (adelanta el reloj). `simular.py` las usa y escribe todo en `simulacion/` (ignorada por git).
- `generar_playbook_inicial.py` regenera el playbook v1 desde cero (pisa el actual: solo para arrancar).
