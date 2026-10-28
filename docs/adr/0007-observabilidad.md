# ADR-007: Observabilidad con un puerto `TraceSink` y trazas en fichero primero

**Estado:** Aceptado
**Fecha:** 2026-10-28
**Decide:** Erik Claveau
**Relacionados:** ADR-003 (evals), ADR-004 (modelo), ADR-006 (salida del LLM), plan §10

## Contexto

El plan (§10) pide una traza por petición con: identificador de la petición, usuario (pseudónimo), commit, modelo, versión del prompt y del esquema, SQL de todos los intentos, resultado de la validación, filas devueltas, latencia por etapa, tokens y coste, y resultado de la verificación numérica. La base del plan es Langfuse autoalojado; la alternativa, OpenTelemetry con Phoenix. El ADR queda pendiente desde el plan.

**Lo que ya existe.** `Assistant.ask` devuelve un `AssistantResult`: un modelo Pydantic inmutable con la pregunta, el resultado de cada etapa (generación, validación, ejecución, síntesis), los intentos anteriores en `corrections`, el coste y la latencia totales. Es ya la traza de una petición. Los logs de Inspect guardan ese objeto entero en `assistant_result` por muestra, y ese es hoy el único sitio donde se puede mirar por qué falló una pregunta. Lo que falta es el puerto `TraceSink` (plan §8), el identificador de petición, el commit y la latencia por etapa de la generación y la síntesis (se suma, no se desglosa).

**Restricciones del proyecto**
- «`docker compose up` levanta todo» es parte de la definición de hecho (plan §15). Cada servicio extra pesa en el arranque y en el CI.
- Una traza contiene filas de resultado y conceptos de terceros (texto no confiable, con las trampas de inyección). Son datos sintéticos, pero la traza no debe ser un camino de fuga de datos entre usuarios ni de canarios hacia un sistema que alguien pueda leer como instrucciones.
- Las evals (ADR-003) ya guardan sus trazas; la observabilidad de la API es un uso distinto (depurar una petición real) y no puede ser una condición de las evals.

## Decisión

1. **Se crea el puerto `TraceSink`** con un único método `emit(trace)`, donde `trace` es el `AssistantResult` más los metadatos de la petición (`request_id`, `user_id` pseudonimizado, `commit_sha`, versiones del modelo, del prompt y del esquema). El `Assistant` lo recibe opcional, como el sintetizador; sin sumidero, no cambia nada.
2. **Primer adaptador: fichero JSONL local** (una línea por petición, en `logs/traces/`, fuera de git). Sin dependencias ni servicios, sirve en tests y en CI, y cubre todos los campos del plan.
3. **Segundo adaptador, opcional y para más tarde: OpenTelemetry hacia Phoenix**, con un span por etapa (generación, validación, ejecución, síntesis, verificación numérica) y los atributos en el esquema semántico de GenAI de OpenTelemetry. Phoenix corre en un único contenedor, como un servicio más de Docker Compose bajo un perfil (`--profile observability`), no obligatorio para `docker compose up`.
4. **Langfuse queda descartado para este proyecto**, no para siempre: el puerto permite añadirlo como adaptador.
5. **Reglas de contenido de la traza**: el `user_id` se guarda como pseudónimo (hash con sal de configuración), no el número; las filas de resultado se guardan completas solo en el adaptador de fichero local; el adaptador de OpenTelemetry exporta cifras agregadas (número de filas, columnas, SQL, estado de cada etapa) pero no el contenido de las celdas.

## Opciones consideradas

| Opción | Arranque | Cubre el plan §10 | Encaje con las evals | Riesgo |
|---|---|---|---|---|
| Langfuse autoalojado | Pesado: según su documentación, la versión 3 pide Postgres, ClickHouse, Redis y almacenamiento S3 (a verificar al implementar) | Sí, con interfaz propia | Bueno (datasets y puntuaciones) | Mucha infraestructura para un proyecto de seis semanas; compite con `docker compose up` simple |
| OpenTelemetry + Phoenix | Un contenedor | Sí, por atributos de span | Bueno | Los atributos del esquema GenAI cambian; fijar la versión |
| OpenTelemetry sin interfaz | Nulo, pero hace falta un destino para leer las trazas | Sí | Regular | Sin visor, poco visible en un portfolio |
| **Puerto + JSONL, con Phoenix opcional** | Nulo por defecto | Sí | Directo: mismo objeto que ya guardan los logs de Inspect | Dos adaptadores que mantener |

## Consecuencias

**Más fácil**
- Depurar una petición sin volver a llamar al modelo: todo el recorrido está en una línea del fichero.
- Los tests del adaptador no necesitan red ni servicios. Cambiar de destino es un adaptador.
- `docker compose up` sigue siendo ligero.

**Más difícil**
- Hay que decidir el desglose de latencia por etapa (hoy `latency_s` suma generaciones, ejecuciones y síntesis). Para el span por etapa, cada resultado debe llevar su propia latencia; ya la tienen `GenerationResult`, `ExecutionResult` y `SynthesisResult`, falta usarla.
- El pseudónimo del usuario necesita una sal en configuración y una regla de rotación.
- Un fichero JSONL crece sin límite: rotación por día y tamaño máximo.

**A revisar**
- Si el volumen de depuración crece, mirar Langfuse como tercer adaptador.
- Si Phoenix no aporta frente al fichero en la demo (ADR-009), no se mantiene.

## Próximos pasos

1. [x] Puerto `TraceSink` y modelos `RequestTrace` y `TraceContext` (traza + metadatos), en `pipeline/assistant/` porque los define y consume el `Assistant`; los adaptadores viven en `pipeline/tracing/`.
2. [x] Adaptador JSONL, con test que comprueba que el `user_id` no llega al fichero y que la línea contiene el resultado completo. La línea no se vuelve a cargar en el modelo: incluye los campos calculados (coste, latencia, SQL), que el modelo rechaza al entrar. Es para leer, no para reconstruir.
3. [x] `Assistant` recibe `trace_sink` y `trace_context` (van juntos); añade `request_id` y el pseudónimo; un sumidero que falla se registra y no cambia la respuesta. El `commit_sha` sale de `COMMIT_SHA` o de git (con `-dirty` si hay cambios sin commitear) y la sal de `TRACE_USER_SALT` (`pipeline/tracing/trace_context.py`). Las tareas de Inspect ya trazan a `logs/traces/` con una sal fija, porque sus usuarios son sintéticos; la API, que aún no existe, deberá exigir la variable.
4. [ ] Adaptador OpenTelemetry/Phoenix y perfil de Docker Compose (opcional, solo si sobra tiempo tras la demo).
5. [x] §12, §11 y el changelog del plan actualizados.
