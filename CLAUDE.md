# Pragmatic Code — agentes comerciales

Tres agentes que trabajan en cadena:

1. **buscador-leads** (`prospector.py`): busca comercios en AR y EE.UU. con la Google Places API y genera `leads_*.json`.
2. **vendedor** (`contactador.py` + `prompts/agente_contacto.md`): primer email, seguimiento, respuestas, registro en
   `leads_contactados.json`, cierre de venta y brief en `briefs/`.
3. **programador** (`prompts/agente_programador.md`): programa el sitio desde `briefs/brief_[id].json`.

Comandos: `/buscar-leads`, `/contactar`, `/seguimientos`, `/responder`, `/brief`, `/programar`, `/estado`.

## Reglas del proyecto
- En Windows se usa `python`; en Linux/Mac, `python3`.
- Claves solo por variables de entorno: `GOOGLE_PLACES_API_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`.
  Nunca en archivos del repo.
- Ningún email real sale sin confirmación explícita del usuario (`--enviar`).
- `leads_contactados.json` es la memoria de a quién ya se contactó y quién pidió la baja: no borrarlo ni editarlo a mano
  salvo para marcar `pago_verificado` / `pago_final_verificado`, que solo marca una persona.
