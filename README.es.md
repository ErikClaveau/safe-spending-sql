# safe-spending-sql

> 🇬🇧 English version: [README.md](README.md)

Asistente text-to-SQL sobre datos bancarios personales **sintéticos**, construido alrededor de dos preguntas que importan más que el chat: *¿puede la pregunta de un cliente llegar a los datos de otro?* y *¿se puede comprobar cada número de la respuesta?*

- **El aislamiento lo da la base de datos, no el modelo.** La seguridad a nivel de fila de Postgres (RLS) es lo único que separa a los usuarios. El SQL generado nunca se reescribe para añadir un filtro, y el modelo no elige de quién lee los datos.
- **Números trazables.** Todo número de una respuesta debe estar en el resultado de la consulta, la pregunta, los supuestos declarados o el SQL; si no, la respuesta se reintenta una vez y después se descarta.
- **Evals publicadas.** Un golden set de 152 preguntas, un set de 32 ataques de aislamiento y otro de 30 preguntas de inyección, versionados en este repositorio y ejecutados en CI contra el modelo real.

Solo datos sintéticos: ninguna transacción real, propia ni anonimizada en ningún paso.

## Resultados

Medidos en GitHub Actions (Linux) con `claude-sonnet-5-5`, esfuerzo `medium`, prompt `v4`, dataset `0.5.0`.

| Puerta de publicación | Resultado | Umbral |
|---|---|---|
| Acierto de ejecución, golden set (152 preguntas) | **98,0 %** (149/152) · dev 98,1 % · test 97,9 % | ≥ 85 % |
| Tasa de fuga entre usuarios, set de aislamiento (32 ataques) | **0 / 32** | 0 |
| Tasa de inyección exitosa, set de inyección (30 preguntas) | **0 / 30** | 0 |
| La trampa llegó a la entrada del modelo | 23 / 30 | ≥ 50 % (si no, un 0 no probaría nada) |
| Coincidencia estricta (columnas y orden exactos) | 75,7 % | se informa, no bloquea |

Coste: unos **13,6 $ por 1.000 consultas** (solo generación del SQL; el texto de la respuesta añade una segunda llamada).

Lo que esas cifras dicen y lo que no:

- El acierto es la métrica *tolerante* (un resultado vale si algún subconjunto ordenado de sus columnas coincide con la referencia). La estricta es más baja porque el modelo suele devolver columnas extra correctas.
- El golden set creció de 90 a 152 preguntas y tres referencias se corrigieron tras leer los fallos (cada corrección consta en las `notes` de la pregunta). 47 preguntas son un split de **test** congelado que no se usó para decidir qué cambiar. El error estándar es de unos 3 puntos por ejecución: una diferencia de uno o dos puntos es ruido.
- Los tres fallos que quedan son conocidos: dos piden comparar dos periodos y el modelo no lo hace, y uno es una pregunta de test que se deja sin tocar a propósito.
- «Cero inyecciones» es una afirmación sobre estas 30 preguntas y 5 familias de ataque, no sobre la inyección de prompts en general.

El detalle de cada cambio, mantenido o descartado, con la ejecución que lo justifica, está en [`docs/iteraciones-evals.md`](docs/iteraciones-evals.md). Resumen:

| Paso | Golden set | Acierto tolerante |
|---|---|---|
| Línea base, prompt v1 | 90 preguntas | 82,2 % |
| Documentación de las vistas en la base de datos (`COMMENT ON`) | 90 | 87,8 % |
| Prompt v2 («devuelve solo las columnas pedidas») | 90 | 83,3 % — **descartado**, arregló 2 y rompió 8 |
| Prompt v3 | 90 | 90,0 % |
| Lista blanca de funciones en el validador | 90 | 91,1 % — sin regresión, no es una mejora |
| Set ampliado a 152 preguntas | 152 | 92,1 % |
| Prompt v4 («un dato concreto, una fila»), decidido solo con fallos de dev | 152 | 94,7–96,1 % en dos ejecuciones |
| Tres referencias ambiguas corregidas | 152 | **98,0 %** |

| Modelo | Acierto | Coste por 1.000 consultas |
|---|---|---|
| `claude-sonnet-5-5` (por defecto) | 98,0 % (152 preguntas) | 13,6 $ |
| `claude-haiku-5-5` | 88,8–89,5 % (152 preguntas, dos ejecuciones) | 1,1 $ |
| `claude-opus-5-5` | 90,0 % frente a 91,1 % de Sonnet (90 preguntas) | 29,8 $ |

Haiku es 12 veces más barato y 9 puntos peor, y uno de sus fallos estables es una cifra equivocada con aspecto de respuesta. Opus no mejoró a Sonnet. Las puertas de aislamiento e inyección también se cumplen con Haiku. Detalle en el [ADR-004](docs/es/adr/0004-modelo-de-lenguaje.md).

## Cómo funciona

Generar SQL (tool use + Pydantic) → validar (sqlglot) → ejecutar en solo lectura bajo RLS → redactar la respuesta → comprobar cada número → respuesta con SQL y filas. Si el validador o la base de datos rechazan el SQL, el modelo lo reescribe una vez, pasando otra vez por el mismo validador y la misma RLS.

1. **Generar.** El modelo solo ve tres vistas con nombres en español y su documentación (`COMMENT ON`), y responde con una acción estructurada: `query`, `clarify` o `refuse`.
2. **Validar.** `sqlglot` admite un `SELECT`, solo las tres vistas, un `LIMIT` y solo funciones de una **lista blanca** (una lista negra dejó pasar `query_to_xml` y `dblink_exec`). Nunca reescribe el SQL.
3. **Ejecutar.** `BEGIN READ ONLY` explícito, `set_config('app.user_id', …, true)` como primera sentencia y la consulta tal cual. La política falla cerrada: sin identidad, sin filas.
4. **Responder y comprobar.** El modelo redacta la respuesta con el resultado completo. La comprobación es por valor, no por procedencia: una cuenta que coincide con alguna celda pasa.
5. **Trazar.** Una línea JSONL por petición, con el usuario como pseudónimo con sal, detrás del puerto `TraceSink`.

Las decisiones están en los ADR: [001](docs/es/adr/0001-motor-de-base-de-datos.md) PostgreSQL · [002](docs/es/adr/0002-aislamiento-entre-usuarios.md) aislamiento solo con RLS · [003](docs/es/adr/0003-framework-de-evals.md) evals · [004](docs/es/adr/0004-modelo-de-lenguaje.md) modelo · [005](docs/es/adr/0005-capa-semantica.md) capa semántica · [006](docs/es/adr/0006-salida-estructurada.md) salida estructurada · [007](docs/es/adr/0007-observabilidad.md) observabilidad · [008](docs/es/adr/0008-fechas-y-divisas.md) fechas y divisas · [009](docs/es/adr/0009-demo.md) demo · [010](docs/es/adr/0010-ambiguedad.md) ambigüedad.

## Probarlo

Necesitas Docker y una clave de API de Anthropic. Cada pregunta cuesta dinero real de API.

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
docker compose up --build        # Postgres, carga del dataset y la app
```

Abre <http://localhost:8501>. Elige un usuario sintético en la barra lateral (sustituye a la autenticación: el asistente sabe quién pregunta por ese selector, nunca por el texto de la pregunta) y pregunta, por ejemplo, *¿Cuánto gasté en supermercados el mes pasado?*

La pestaña **Try to break it** lanza las preguntas del set adversarial como el usuario para el que se escribió cada una. El veredicto usa las mismas reglas que las puertas de publicación.

Los comandos de desarrollo (Docker y [`uv`](https://docs.astral.sh/uv/)), las evals y el CI están en la [versión en inglés](README.md#development) y en [`docs/es/ci.md`](docs/es/ci.md).

## Los datos

25 usuarios, 36 cuentas y 29.234 movimientos en dos años, generados, nunca recogidos. El dataset es reproducible byte a byte: un test lo regenera y compara filas y SHA-256 de cada fichero con el manifiesto versionado. Ver la [ficha del dataset](docs/es/dataset-card.md).

## Limitaciones conocidas

- **Un arquetipo y 25 usuarios.** Todos son jóvenes profesionales. El diseño habla de 100 usuarios y más perfiles.
- **Las estadísticas son verosímiles, no validadas.** El reparto del gasto no se comparó con una encuesta de presupuestos familiares.
- **Un solo turno.** No hay conversación: una aclaración devuelve el control y la persona escribe la pregunta de nuevo (ADR-010).
- **El selector de usuario de la demo no es autenticación.** No hay API ni capa de auth, y la demo no tiene límite de gasto propio.
- **Solo en español.** Preguntas, capa semántica y prompts, a propósito: es lo que lee el modelo.
- **Comprobación numérica por valor.** Detecta números inventados, no un número real atribuido a algo que no es.
- **Un benchmark sintético.** Los resultados dicen cómo se comporta el sistema con este dataset y estilo de pregunta, no con preguntas de clientes reales.

## Idioma de la documentación

Todos los documentos están en inglés con un espejo en español en la misma ruta bajo [`docs/es/`](docs/es/), enlazados entre sí; un test (`tests/docs/test_language_parity.py`) falla si falta un par o se rompe un enlace. Tres están a propósito en un solo idioma: el plan de trabajo y el [registro de iteraciones](docs/iteraciones-evals.md) solo en español, y el [diccionario de datos](docs/data-dictionary.md) solo en inglés (es la capa en inglés sobre las vistas en español).

## Licencia

MIT. Ver [LICENSE](LICENSE).
