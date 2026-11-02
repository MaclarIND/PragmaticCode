# Playbook inicial v1 — para aprobar

Marcadores que el agente reemplaza: `{nombre}`, `{rubro}`, `{dato_observable}`, `{portfolio}`.

## Apertura
_Varía solo el gancho/oferta: 1 = pregunta sobre cómo les llegan clientes · 2 = lista en una semana · 3 = sin costo inicial + mantenimiento_

**AR_sin_web** (canal: ambos)

- `AR-SW-A1` Hola, vi {dato_observable} de {nombre}. Busqué su web y no encontré ninguna. ¿Hoy los clientes nuevos te llegan solo por Maps y boca en boca?
- `AR-SW-A2` Hola, vi {dato_observable} de {nombre}. Busqué su web y no encontré ninguna. Armamos páginas para {rubro} listas en una semana. ¿Te sirve tener una?
- `AR-SW-A3` (pendiente de aprobación) Hola, vi {dato_observable} de {nombre}. Busqué su web y no encontré ninguna. Te la armamos sin costo inicial y solo pagás el mantenimiento mensual. ¿Te interesa?

**AR_con_web** (canal: ambos)

- `AR-CW-A1` Hola, vi {dato_observable} de {nombre} y entré a su web. ¿Te llegan consultas desde la página o la mayoría viene por otro lado?
- `AR-CW-A2` Hola, vi {dato_observable} de {nombre} y entré a su web. Hacemos rediseños para {rubro} listos en una semana. ¿Pensaste en renovarla?
- `AR-CW-A3` (pendiente de aprobación) Hola, vi {dato_observable} de {nombre} y entré a su web. La rediseñamos sin costo inicial y solo pagás el mantenimiento mensual. ¿Te interesa?

**US_sin_web** (canal: email)

- `US-SW-A1` Hi, I saw {dato_observable} about {nombre} and couldn't find a website. Do new customers mostly find you through Google Maps and word of mouth?
- `US-SW-A2` Hi, I saw {dato_observable} about {nombre} and couldn't find a website. We build sites for {rubro} businesses, ready in a week. Would one be useful for you?
- `US-SW-A3` (pendiente de aprobación) Hi, I saw {dato_observable} about {nombre} and couldn't find a website. We can build one with no upfront cost, you'd just pay monthly maintenance. Interested?

**US_con_web** (canal: email)

- `US-CW-A1` Hi, I saw {dato_observable} about {nombre} and checked out your website. Do you get inquiries through it, or do most customers come from somewhere else?
- `US-CW-A2` Hi, I saw {dato_observable} about {nombre} and checked out your website. We redesign sites for {rubro} businesses in a week. Have you thought about a refresh?
- `US-CW-A3` (pendiente de aprobación) Hi, I saw {dato_observable} about {nombre} and checked out your website. We can redesign it with no upfront cost, you'd just pay monthly maintenance. Interested?

## Seguimiento sin respuesta (día 3 y día 7)
_Varía solo el gancho: 1 = pregunta directa · 2 = Google · 3 = plantilla adaptada a su gusto_

**AR_sin_web** (canal: ambos)

- `AR-SW-S1` Te escribo de nuevo por lo de la web de {nombre}. ¿Es algo que te interesa este año o lo dejamos acá?
- `AR-SW-S2` Te escribo de nuevo por lo de la web de {nombre}. Sin página, el que te busca en Google solo tiene la ficha de Maps para decidir. ¿Te interesa sumar una?
- `AR-SW-S3` Te escribo de nuevo por lo de la web de {nombre}. Partimos de una plantilla y la adaptamos a tu gusto: colores, fotos y textos. ¿Te interesa?

**AR_con_web** (canal: ambos)

- `AR-CW-S1` Te escribo de nuevo por lo de la web de {nombre}. ¿Es algo que querés renovar este año o lo dejamos acá?
- `AR-CW-S2` Te escribo de nuevo por lo de la web de {nombre}. La página suele ser lo primero que miran antes de escribirte. ¿Te interesa mejorarla?
- `AR-CW-S3` Te escribo de nuevo por lo de la web de {nombre}. Partimos de una plantilla y la adaptamos a tu gusto: colores, fotos y textos. ¿Te interesa?

**US_sin_web** (canal: email)

- `US-SW-S1` Following up on the website idea for {nombre}. Is it something you'd consider this year, or should I leave it here?
- `US-SW-S2` Following up on the website idea for {nombre}. Without a site, people who find you on Google only have your Maps listing to decide. Worth adding one?
- `US-SW-S3` Following up on the website idea for {nombre}. We start from a template and tailor it to your taste: colors, photos and copy. Interested?

**US_con_web** (canal: email)

- `US-CW-S1` Following up on your website for {nombre}. Is a refresh something you'd consider this year, or should I leave it here?
- `US-CW-S2` Following up on your website for {nombre}. It's usually the first thing people check before contacting you. Worth improving it?
- `US-CW-S3` Following up on your website for {nombre}. We start from a template and tailor it to your taste: colors, photos and copy. Interested?

## Objeción: ya_tengo_web
_Varía solo el argumento_

**AR_sin_web** (canal: ambos)

- `AR-SW-YW1` Bien, entonces no arrancás de cero. ¿Te trae clientes hoy o está más de presencia?
- `AR-SW-YW2` Bien. No hace falta tirarla: se puede renovar el diseño y dejar lo que funciona. ¿Qué es lo que menos te gusta de la actual?
- `AR-SW-YW3` Bien. Muchas veces el problema es que en el celular se ve mal y la gente se va. ¿La probaste desde el teléfono?

**AR_con_web** (canal: ambos)

- `AR-CW-YW1` Bien, entonces no arrancás de cero. ¿Te trae clientes hoy o está más de presencia?
- `AR-CW-YW2` Bien. No hace falta tirarla: se puede renovar el diseño y dejar lo que funciona. ¿Qué es lo que menos te gusta de la actual?
- `AR-CW-YW3` Bien. Muchas veces el problema es que en el celular se ve mal y la gente se va. ¿La probaste desde el teléfono?

**US_sin_web** (canal: ambos)

- `US-SW-YW1` Great, so you're not starting from scratch. Is it bringing you customers today, or is it more of a placeholder?
- `US-SW-YW2` Great. No need to throw it away: we can refresh the design and keep what works. What do you like least about the current one?
- `US-SW-YW3` Great. Often the issue is that it looks off on phones and people leave. Have you checked it from your phone lately?

**US_con_web** (canal: ambos)

- `US-CW-YW1` Great, so you're not starting from scratch. Is it bringing you customers today, or is it more of a placeholder?
- `US-CW-YW2` Great. No need to throw it away: we can refresh the design and keep what works. What do you like least about the current one?
- `US-CW-YW3` Great. Often the issue is that it looks off on phones and people leave. Have you checked it from your phone lately?

## Objeción: precio
_Varía solo el argumento_

**AR_sin_web** (canal: ambos)

- `AR-SW-PR1` Entiendo. Con un cliente nuevo por mes ya se paga sola. ¿Cuánto te deja un cliente promedio?
- `AR-SW-PR2` Entiendo. Hay una versión más simple, de una sola página, que sale bastante menos. ¿Te paso esa opción?
- `AR-SW-PR3` Entiendo. Se puede pagar en cuotas, o arrancar sin costo inicial y pagar solo el mantenimiento. ¿Alguna de las dos te sirve?

**AR_con_web** (canal: ambos)

- `AR-CW-PR1` Entiendo. Con un cliente nuevo por mes ya se paga sola. ¿Cuánto te deja un cliente promedio?
- `AR-CW-PR2` Entiendo. Hay una versión más simple, de una sola página, que sale bastante menos. ¿Te paso esa opción?
- `AR-CW-PR3` Entiendo. Se puede pagar en cuotas, o arrancar sin costo inicial y pagar solo el mantenimiento. ¿Alguna de las dos te sirve?

**US_sin_web** (canal: ambos)

- `US-SW-PR1` Understood. One new customer a month usually covers it. What's an average customer worth to you?
- `US-SW-PR2` Understood. There's a simpler one-page version that costs quite a bit less. Want me to send that option?
- `US-SW-PR3` Understood. You can start with no upfront cost and just pay monthly maintenance. Would that work better?

**US_con_web** (canal: ambos)

- `US-CW-PR1` Understood. One new customer a month usually covers it. What's an average customer worth to you?
- `US-CW-PR2` Understood. There's a simpler one-page version that costs quite a bit less. Want me to send that option?
- `US-CW-PR3` Understood. You can start with no upfront cost and just pay monthly maintenance. Would that work better?

## Objeción: no_necesito
_Varía solo el argumento_

**AR_sin_web** (canal: ambos)

- `AR-SW-NN1` Dale, lo respeto. ¿Hoy tenés todos los clientes que podés atender?
- `AR-SW-NN2` Dale. Solo te digo que la mayoría busca en Google antes de escribir a un negocio. ¿Te pasa que te pregunten si tenés página?
- `AR-SW-NN3` Dale, sin problema. ¿Te escribo en unos meses por si cambia algo?

**AR_con_web** (canal: ambos)

- `AR-CW-NN1` Dale, lo respeto. ¿Hoy tenés todos los clientes que podés atender?
- `AR-CW-NN2` Dale. Solo te digo que la mayoría busca en Google antes de escribir a un negocio. ¿Te pasa que te pregunten si tenés página?
- `AR-CW-NN3` Dale, sin problema. ¿Te escribo en unos meses por si cambia algo?

**US_sin_web** (canal: ambos)

- `US-SW-NN1` Fair enough. Are you getting all the customers you can handle right now?
- `US-SW-NN2` Fair enough. Most people check Google before contacting a business. Do customers ever ask if you have a website?
- `US-SW-NN3` No problem at all. Mind if I check back in a few months in case things change?

**US_con_web** (canal: ambos)

- `US-CW-NN1` Fair enough. Are you getting all the customers you can handle right now?
- `US-CW-NN2` Fair enough. Most people check Google before contacting a business. Do customers ever ask if you have a website?
- `US-CW-NN3` No problem at all. Mind if I check back in a few months in case things change?

## Objeción: desconfianza
_Varía solo el argumento_

**AR_sin_web** (canal: ambos)

- `AR-SW-DF1` Es lógico. Acá tenés trabajos nuestros: {portfolio}. ¿Querés que hablemos 10 minutos por teléfono?
- `AR-SW-DF2` Es lógico. Pagás la mitad para arrancar y el resto recién cuando ves la página terminada y te gusta. ¿Así te queda más tranquilo?
- `AR-SW-DF3` Es lógico. Somos Pragmatic Code, pragmatic-code.com, y la página queda a tu nombre con todos los accesos. ¿Qué te gustaría saber antes de decidir?

**AR_con_web** (canal: ambos)

- `AR-CW-DF1` Es lógico. Acá tenés trabajos nuestros: {portfolio}. ¿Querés que hablemos 10 minutos por teléfono?
- `AR-CW-DF2` Es lógico. Pagás la mitad para arrancar y el resto recién cuando ves la página terminada y te gusta. ¿Así te queda más tranquilo?
- `AR-CW-DF3` Es lógico. Somos Pragmatic Code, pragmatic-code.com, y la página queda a tu nombre con todos los accesos. ¿Qué te gustaría saber antes de decidir?

**US_sin_web** (canal: ambos)

- `US-SW-DF1` Makes sense. Here's some of our work: {portfolio}. Would a quick 10-minute call help?
- `US-SW-DF2` Makes sense. You pay half to start and the rest only once you see the finished site and like it. Does that help?
- `US-SW-DF3` Makes sense. We're Pragmatic Code (pragmatic-code.com), and the site is registered in your name with full access. What would you like to know before deciding?

**US_con_web** (canal: ambos)

- `US-CW-DF1` Makes sense. Here's some of our work: {portfolio}. Would a quick 10-minute call help?
- `US-CW-DF2` Makes sense. You pay half to start and the rest only once you see the finished site and like it. Does that help?
- `US-CW-DF3` Makes sense. We're Pragmatic Code (pragmatic-code.com), and the site is registered in your name with full access. What would you like to know before deciding?

## Cierre
_Varía solo la pregunta final_

**AR_sin_web** (canal: ambos)

- `AR-SW-C1` Buenísimo. ¿Arrancamos? Te paso el link para la seña y te pido logo y fotos.
- `AR-SW-C2` Buenísimo. ¿Preferís que arranquemos esta semana o la próxima?
- `AR-SW-C3` Buenísimo. ¿Te armo la propuesta con lo que hablamos para que la veas tranquilo?

**AR_con_web** (canal: ambos)

- `AR-CW-C1` Buenísimo. ¿Arrancamos? Te paso el link para la seña y te pido logo y fotos.
- `AR-CW-C2` Buenísimo. ¿Preferís que arranquemos esta semana o la próxima?
- `AR-CW-C3` Buenísimo. ¿Te armo la propuesta con lo que hablamos para que la veas tranquilo?

**US_sin_web** (canal: ambos)

- `US-SW-C1` Great. Shall we get started? I'll send the deposit link and ask for your logo and photos.
- `US-SW-C2` Great. Would you rather start this week or next?
- `US-SW-C3` Great. Want me to put together a proposal with what we discussed so you can review it?

**US_con_web** (canal: ambos)

- `US-CW-C1` Great. Shall we get started? I'll send the deposit link and ask for your logo and photos.
- `US-CW-C2` Great. Would you rather start this week or next?
- `US-CW-C3` Great. Want me to put together a proposal with what we discussed so you can review it?
