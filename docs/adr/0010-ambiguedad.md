# ADR-010: Qué hacer ante una pregunta ambigua

**Estado:** Aceptado, con puntos a revisar
**Fecha:** 2026-10-28
**Decide:** Erik Claveau
**Relacionados:** ADR-006 (acciones `query`, `clarify` y `refuse`), ADR-003 (evals)

## Contexto

Hay preguntas que no fijan lo que piden: «¿Cuánto gasté en comida?» no dice si es supermercado, restaurantes o todo el grupo Alimentación, ni en qué periodo. Cuando no se indica un periodo, ¿se pregunta o se elige uno?

El asistente tiene dos salidas: preguntar o contestar diciendo qué ha supuesto. Y hoy **no tiene conversación**: `Assistant.ask(user_id, question)` es una llamada sin historial, así que una pregunta de aclaración devuelve el control a la persona, que tiene que escribir de nuevo la pregunta entera.

## Decisión

**Asumir y explicitar por defecto; preguntar solo cuando no hay una interpretación razonable.**

- **Hay una interpretación razonable:** se ejecuta la consulta y el supuesto se dice en una frase en `message` (por ejemplo, «No indicas un periodo: uso todo el historial»). Ese supuesto llega al sintetizador como `assumptions` y la respuesta final lo menciona.
  - Sin periodo, se usa todo el historial disponible, sin filtro de fecha.
  - Una categoría vaga se resuelve por la interpretación más probable, y se dice cuál.
- **No la hay** (no se sabe de qué movimiento se habla, o con qué se quiere comparar): acción `clarify`, con **una sola** pregunta concreta.
- **Rechazar** es otra cosa: una pregunta fuera del dominio de gastos.

La regla vive en el prompt del generador de SQL: «si basta con elegir la interpretación más razonable, hazlo con `query` y dila en `message` en lugar de preguntar».

**Cómo se evalúa.** El golden marca esas preguntas como `clarify` y acepta las dos conductas: pedir la aclaración, o responder diciendo el supuesto. Responder sin decir nada no vale. Hay cuatro preguntas (GS-074 a GS-077) y la categoría `ambigua` salió al 100 % en la última medición.

## Opciones consideradas

| Opción | Experiencia | Evaluabilidad | Riesgo |
|---|---|---|---|
| Preguntar siempre | Un turno perdido por cada pregunta ambigua; hoy, además, la persona repite la pregunta entera | Solo se puede comprobar que pregunta | Cansa y no ayuda |
| Asumir siempre | Respuesta inmediata | Se compara con una referencia | Una cifra equivocada sin que la persona lo note, si no se dice el supuesto |
| **Asumir y explicitar; preguntar solo sin interpretación razonable** | Respuesta útil en un turno | Se evalúa contra una referencia, y los casos sin salida, por la conducta | El criterio de «razonable» lo pone el modelo |

## Consecuencias

**Más fácil**
- Una respuesta útil en un turno, sin necesitar estado de conversación.
- Una respuesta con supuesto se puede comparar con una referencia: no hace falta simular diálogos para evaluar.
- El supuesto queda en el resultado del asistente (`message`) y en el texto final.

**Más difícil**
- La persona puede no leer la frase del supuesto y quedarse con una cifra que no era la que quería.
- «Razonable» no está formalizado y la frontera es borrosa. Lo muestra el viaje a Londres (GS-053 y GS-056): la referencia responde con un periodo y el modelo a veces pide las fechas; es la única pregunta cuya conducta cambia entre ejecuciones del golden.
- Cuatro preguntas son una muestra pequeña de la categoría `ambigua`.

**A revisar**
- Con la API (semana 5) habrá conversación: entonces `clarify` debería conservar la pregunta original y responderse en el turno siguiente. Hoy no.
- Ampliar la categoría `ambigua` cuando el golden pase a 150-200 preguntas, con casos de frontera como el de Londres.
- Medir cuántas veces el supuesto del modelo no es el que la persona quería. Con datos sintéticos y sin usuarios no se puede medir; solo se sabe que el supuesto se dice.

## Próximos pasos

1. [x] Regla en el prompt del generador (periodo por defecto y `clarify` con una sola pregunta).
2. [x] El supuesto llega al sintetizador y se menciona en la respuesta.
3. [x] El golden acepta pedir la aclaración o decir el supuesto.
4. [ ] Más preguntas `ambigua`, con casos de frontera.
5. [ ] Conservar la pregunta original al pedir una aclaración, cuando haya conversación.
