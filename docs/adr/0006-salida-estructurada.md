# ADR-006: Salida estructurada con tool use y validación Pydantic

**Estado:** Aceptado
**Fecha:** 2026-10-21
**Decide:** Erik Claveau
**Relacionados:** ADR-004 (modelo), ADR-005 (capa semántica)

## Contexto

El pipeline necesita que el modelo devuelva datos, no prosa: el SQL, si hace falta aclarar, si la pregunta está fuera de dominio. Una salida mal formada no debe llegar al validador ni al executor. Además cada intento (incluidos los fallidos) debe quedar en la traza (plan §10).

## Decisión

- El modelo responde mediante **tool use** con un esquema JSON que lo obliga a rellenar campos tipados (por ejemplo `accion` ∈ {`consultar`, `aclarar`, `rechazar`}, `sql`, `mensaje`).
- La herramienta se declara con `strict: true`, de modo que si el modelo la llama, la entrada cumple el esquema. **No se puede forzar la llamada** (`tool_choice` `any`/`tool` devuelve un 400 en `claude-sonnet-5-5` y `claude-opus-5-5`): se usa `auto` y el sistema pide responder solo con la herramienta. Una respuesta sin llamada llega como `structured_output = None` y cuenta como intento fallido, igual que una entrada que no valida.
- La respuesta se **valida con Pydantic**. Si no valida, cuenta como intento fallido y se registra; el número de reintentos es configurable y limitado.
- El SQL que sale de este paso sigue siendo texto no confiable: pasa por sqlglot y se ejecuta bajo RLS (ADR-002). Pydantic valida la forma, nunca la seguridad.
- Los modelos Pydantic son el contrato del puerto `SQLGenerator`, independiente del proveedor. Los detalles de tool use se quedan en el adaptador de `LLMProvider`.
- Los números de la respuesta final los calcula el SQL, no el modelo (invariante del proyecto).

## Opciones consideradas

| Opción | Robustez | Trazabilidad | Dependencias | Control de reintentos |
|---|---|---|---|---|
| **Tool use + Pydantic** | Alta: esquema forzado por el proveedor | Alta: JSON crudo y errores de validación | Ninguna extra | Propio |
| Instructor | Alta | Media: oculta parte de los intentos | Una más | Delegado |
| Texto con parseo | Baja | Media | Ninguna | Propio |

## Consecuencias

**Más fácil**
- Salidas tipadas y fallos de formato visibles y medibles como categoría de error.
- Cada intento queda en la traza tal cual.

**Más difícil**
- El adaptador de cada proveedor debe traducir el esquema a su mecanismo de tool use.
- Hay que implementar los reintentos y su registro.

**A revisar**
- La acción `aclarar` depende del ADR-010 (qué hacer ante ambigüedad), todavía pendiente.

- El esquema de `GeneratorResponse` (campos opcionales con `anyOf` nulo y `$defs` para el enum) se probó el 2026-10-21 contra la API real con `strict: true` y `claude-sonnet-5-5`: la API lo aceptó y el modelo llamó a la herramienta en las dos preguntas de prueba (una de consulta y una fuera de dominio), con salidas que validaron con Pydantic.

## Próximos pasos

1. [ ] Modelos Pydantic de la respuesta del generador.
2. [ ] Reintentos con registro de cada intento en la traza.
3. [ ] Contar en las evals los fallos de formato por separado de los fallos de SQL.
