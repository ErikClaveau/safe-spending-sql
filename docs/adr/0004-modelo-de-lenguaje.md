# ADR-004: Modelo frontera por API detrás del puerto `LLMProvider`

**Estado:** Aceptado
**Fecha:** 2026-10-21
**Decide:** Erik Claveau
**Relacionados:** ADR-003 (evals), ADR-006 (salida del LLM)

## Contexto

El baseline de la semana 3 fija el listón de calidad, latencia y coste. Se necesita una cifra fiable de execution accuracy en castellano sobre las vistas semánticas, no una cifra limitada por un modelo pequeño. El proyecto 3 (modelo local o afinado) usará este baseline como referencia (plan §2.3).

## Decisión

- El baseline usa un **modelo frontera por API** (Claude), detrás del puerto `LLMProvider`. El resto del pipeline no conoce al proveedor.
- El **modelo concreto es configuración**, no código. Para el baseline: `claude-sonnet-5-5`, como equilibrio entre calidad y coste. En la semana 5 se comparan `claude-haiku-5-5` y `claude-opus-5-5` con el mismo golden set para publicar la relación coste/calidad.
- Cada traza y cada log de evals registran el identificador exacto del modelo, tokens y coste.
- Los modelos locales (Ollama) quedan fuera del alcance de este proyecto. El puerto permite añadirlos como adaptador.
- Las claves de API se leen de variables de entorno y nunca se versionan. A la API solo se envían datos sintéticos.

## Opciones consideradas

| Opción | Calidad esperada | Coste | Reproducibilidad | Baseline para el proyecto 3 |
|---|---|---|---|---|
| **Frontera por API** | Alta | Por token | Depende de la versión del modelo | Sí |
| Local (Ollama) | Menor en castellano y SQL | Nulo por consulta | Alta | Mezcla dos variables |
| Dos modelos desde el inicio | Alta | Por token, doble | Media | Sí, más rico |

## Consecuencias

**Más fácil**
- Un baseline representativo con poco esfuerzo de despliegue.
- Cambiar de modelo es un cambio de configuración, medible con las mismas evals.

**Más difícil**
- El coste y la latencia dependen de un tercero. Las ejecuciones completas cuestan dinero, por lo que la CI usa el subconjunto smoke.
- Los alias de modelo pueden cambiar: hay que fijar la versión exacta en cada experimento.
- La reproducibilidad es estadística, no bit a bit. `claude-sonnet-5-5` rechaza `temperature`, `top_p` y `top_k` distintos del valor por defecto, así que la variación solo se controla con el modelo fijado y el `effort`, que se fija explícitamente en la configuración (adaptador: `medium` por defecto).
- Se activa la alternativa automática del proveedor ante un rechazo de seguridad (`fallbacks: "default"`). Si salta, el modelo que respondió no es el pedido: `LLMResponse.model` lo registra y el coste se calcula con el precio del modelo que respondió. Se puede desactivar por configuración para una medición limpia.

**A revisar**
- Si el coste de las evals completas resulta alto, ejecutar la completa solo de forma nocturna o manual.

## Próximos pasos

1. [ ] Adaptador `LLMProvider` para la API de Claude, con tokens y coste en la respuesta.
2. [ ] Modelo y parámetros en la configuración, y su registro en `TraceSink`.
3. [ ] Medir el coste por 1.000 consultas del modelo base (plan §2.3).
