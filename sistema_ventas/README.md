# Sistema de ventas con aprendizaje — Pragmatic Code

Reemplaza al vendedor anterior (`contactador.py`) por tres agentes que comparten archivos y aprenden de los resultados.
Mantiene todas las reglas que ya tenía el vendedor (idioma, horarios, canales, precios, baja, honestidad, plantillas
personalizables, traspaso al programador): están en `agentes/prompts/ventas.md` y, las que son duras, en el código.

```
python scheduler.py          # lo deja corriendo: ventas cada 15 min · playbook cada hora (si corresponde) · auditor lunes 9:00
python simular.py            # prueba el ciclo completo con 50 leads falsos, sin red ni datos reales
python aprobar.py            # lista / aprueba / rechaza ofertas pendientes
python agentes/ventas.py     # cualquier agente también se corre a mano
```

Requisitos: Python 3.11+, sin librerías extra. Clave de Claude en la variable de entorno `ANTHROPIC_API_KEY` (o en el `.env`
del repo, igual que las demás). Modelo: `CLAUDE_MODEL` (por defecto `claude-sonnet-5-5`). Sin clave, los agentes corren
igual con respuestas de respaldo deterministas (útil para probar; no para vender).

## Cómo entran los leads
El buscador deja un archivo por lead en `leads/entrada/`:
```json
{ "lead_id": "...", "nombre": "...", "rubro": "...", "pais": "AR|US", "email": "...", "telefono": "...",
  "tiene_web": true, "url_web": "...|null", "dato_observable": "texto corto sobre el negocio visible públicamente" }
```
`zona_horaria` es opcional (si falta: Buenos Aires para AR, Nueva York para US). Sin `email` no se contacta: el primer
contacto es siempre por email (TCPA en EE.UU., Ley 25.326 en AR). No se escribe a nadie que esté en `bajas.json` ni en
`leads_contactados.json` del repo (la memoria del vendedor anterior); cada lead contactado se agrega ahí para que el
buscador no lo vuelva a proponer.

## Cómo conectar email y WhatsApp
Todo está en `agentes/conectores.py`. Hoy son stubs que loguean en `logs/` y devuelven un id falso.
1. **Email:** el repo ya tiene SMTP probado en `../contactador.py` (`enviar_email`, Gmail con contraseña de aplicación,
   variables `SMTP_*`). En `conectores.enviar_email` descomentá las tres líneas marcadas y poné `MODO_REAL = True`.
   `python ../contactador.py probar-email --a-mi` verifica la configuración SMTP.
2. **WhatsApp:** solo por la API oficial de WhatsApp Business (Meta Cloud API). Implementá `enviar_whatsapp(numero, texto)`
   con tu token y el id del número. El sistema nunca abre una conversación por WhatsApp: pasa a ese canal únicamente
   cuando el lead responde o pide por ahí.
3. **Respuestas de los leads:** el sistema las lee de `respuestas/entrada/*.json`:
   ```json
   { "lead_id": "...", "canal": "email|whatsapp", "texto": "...", "ts": "2026-11-02T10:00:00-03:00" }
   ```
   Un lector del buzón (IMAP) o el webhook de WhatsApp tienen que dejar esos archivos; `ventas.py` hace el resto.
   Para relacionar un email con su `lead_id`, buscá la dirección del remitente en `conversaciones/*.json` (`lead.email`)
   o usá el `In-Reply-To` (cada conversación guarda `message_id`).

Firma, portfolio, dirección física (pie CAN-SPAM), persona para derivar, horario y límite por hora se leen de
`../config_contacto.json` (los mismos campos que usaba el vendedor anterior).

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
