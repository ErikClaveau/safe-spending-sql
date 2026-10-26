# ADR-003: Inspect AI para medir y pytest como puerta de CI

**Estado:** Aceptado
**Fecha:** 2026-10-21
**Decide:** Erik Claveau
**Relacionados:** ADR-002 (aislamiento), ADR-004 (modelo), ADR-006 (salida del LLM)

## Contexto

El proyecto se juzga por sus métricas: execution accuracy, fuga entre usuarios, inyecciones con éxito, trazabilidad numérica y coste (plan §2.3). Hacen falta dos cosas distintas:

- **Medir y analizar.** Ejecutar el golden set con cada cambio de modelo o de prompt, comparar ejecuciones, ver pregunta por pregunta qué SQL se generó y por qué falló (análisis de errores de la semana 5) y publicar una tabla de iteraciones.
- **Bloquear.** Una puerta binaria en CI: fuga = 0, canarios = 0 y precisión por encima del umbral.

Ya existen el golden set v0 (`evals/golden/`, 90 preguntas con SQL de referencia), un runner por usuario (`run_as_user`) y una comprobación de la verdad por una ruta que no usa las vistas (`scenarios.params`).

## Decisión

- **Inspect AI** ejecuta las evals. El golden set se expone como tarea; el pipeline es el *solver* y el *scorer* compara el resultado de la consulta con la verdad. Cada ejecución deja un log por muestra, con visor y comparación entre ejecuciones.
- **pytest** es solo la puerta de CI. Lee el resultado de la última ejecución (o ejecuta el subconjunto smoke) y falla si la fuga o los canarios no son 0 o si la precisión baja del umbral.
- Cada ejecución se ancla al commit SHA, el modelo, la versión del prompt, la del dataset y la del esquema semántico (plan §9.3), en los metadatos del log.
- Los scorers de seguridad (fuga, canarios) son código propio con acceso a Postgres; Inspect no impone cómo se puntúa.

## Protocolo de medición

Fijado el 2026-10-22 al construir la primera tarea:

- **Métrica principal, tolerante con columnas extra.** Una respuesta es correcta si algún subconjunto ordenado de sus columnas coincide con el resultado de referencia (mismas filas, tolerancia de un céntimo). Una columna que nadie pidió, como una diferencia o un porcentaje, no penaliza. Se publica además la **métrica estricta** (columnas exactamente iguales, como en los benchmarks), para poder comparar con la literatura y ver cuánto se pierde por forma.
- **Comportamientos.** `refuse` exige un rechazo; `clarify` acepta una pregunta o una respuesta que explicite su supuesto (hasta que el ADR-010 decida); `no_data` exige una consulta cuyo resultado esté vacío o a cero.
- **Un solo modelo por medición.** En las evals el *fallback* ante rechazos del proveedor está desactivado: todas las respuestas vienen del modelo medido y un rechazo cuenta como fallo de generación. En la aplicación y la demo sigue activado.
- **Logs.** Cada ejecución deja un log de Inspect en `logs/` (ignorado por Git) con el SQL, el resultado y la traza completa de cada pregunta. Los resultados que se publiquen se resumen en el README y en la tabla de iteraciones.
- **Ejecución:** `uv run --env-file .env inspect eval src/safe_spending/evals/harness/golden_task.py --max-samples 4`.

## Opciones consideradas

| Opción | Métricas custom | Historial y comparación | Visor de errores | Esfuerzo esta semana | Portfolio |
|---|---|---|---|---|---|
| **Inspect AI** | Sí (scorers en Python) | Sí, logs versionables | Sí | Medio: adaptar el golden set | Alto |
| pytest propio | Sí | A construir | A construir | Bajo | Bajo |
| promptfoo | Limitado contra Postgres con RLS | Sí | Sí | Medio | Medio |

pytest propio puede registrar métricas en JSON, pero historial, comparación y visor tendrían que construirse a mano, y son justo lo que más pesa en el análisis de errores. promptfoo encaja mal con scorers que consultan una base de datos con RLS.

## Consecuencias

**Más fácil**
- Tabla de iteraciones con métricas (semana 5) a partir de los logs.
- Inspeccionar fallos por muestra sin construir herramientas.

**Más difícil**
- Una dependencia más y un modelo de tareas que aprender.
- Hay que fijar el formato de la salida de Inspect que lee pytest.
- Los logs deben tratarse como artefactos (qué se versiona y qué no).

**A revisar**
- Si adaptar el golden set resulta desproporcionado, se recorta alcance antes que retrasar el baseline (regla del plan §14).

## Próximos pasos

1. [x] Añadir `inspect-ai` como dependencia de desarrollo.
2. [x] Tarea Inspect sobre `golden_v0.yaml` con scorer de execution accuracy.
3. [ ] Test pytest que lee el resultado y aplica los umbrales.
