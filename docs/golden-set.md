# Golden set v0

El golden set es la especificación de lo que el asistente debe saber responder: preguntas en castellano sobre los usuarios de evaluación, cada una con el SQL que da la respuesta correcta sobre las vistas semánticas. Es la base de la métrica *execution accuracy* (plan §9) y de la línea base de la semana 3.

## Dónde está

| Fichero | Contenido |
|---|---|
| `evals/golden/golden_v0.yaml` | Las preguntas. Se editan a mano. |
| `evals/golden/expected_v0.json` | La respuesta esperada de cada pregunta con SQL. **Se genera, no se edita a mano.** |
| `src/safe_spending/evals/golden/` | Modelos, reglas del SQL, comparación de resultados y comando. |
| `tests/evals/` | Los tests que lo vigilan. |

## Composición (v0, dataset 0.5.0)

114 preguntas, 106 con SQL de referencia, todas sobre los usuarios funcionales 1-15. Las 90 primeras son el v0 original; GS-091 a GS-114 (semana 5) son 24 preguntas más de recurrentes, escritas con una cifra, una fecha o un nombre concretos y el periodo a la vista.

| Categoría | Preguntas | Comportamiento esperado |
|---|---|---|
| Agregado simple | 17 | SQL y una cifra (incluidos los ceros reales) |
| Comparativa temporal | 9 | SQL con dos periodos |
| Ranking | 8 | SQL con `ORDER BY` y `LIMIT` |
| Filtro compuesto | 8 | SQL con varios filtros |
| Ingresos frente a gastos | 9 | Agregado con signo, combinando las dos vistas |
| Recurrentes | 33 | Suscripciones, recibos, alquiler y nómina |
| Divisa | 6 | Pagos en libras, comisión y tipo de cambio (usuario 6) |
| Devoluciones | 7 | Compras menos devoluciones (usuario 7 y la población) |
| Traspasos entre cuentas propias | 5 | Que no cuentan como gasto ni como ingreso |
| Ambigua | 4 | `clarify`: pedir aclaración o explicitar el supuesto |
| Sin datos | 4 | `no_data`: decir que no hay datos, sin inventar |
| Fuera de dominio | 4 | `refuse`: rechazo educado |

Dificultad: 29 fáciles, 64 medias y 21 difíciles. 33 preguntas están ancladas a uno de los siete escenarios guionizados. Los usuarios 1-7 tienen escenario (suscripciones, cambio de trabajo, alta reciente, categoría a cero, mes anómalo, Londres y Amazon) y los 8-15 son usuarios normales; los que tienen cuenta de ahorro se usan para los traspasos.

Quedan fuera de v0, y son trabajo de las semanas siguientes: el set adversarial (aislamiento y datos con canarios, semana 4) y llegar a las 150-200 preguntas funcionales del plan.

## Convenciones

- **Gasto neto.** "Gasté" es `v_gastos.gasto_eur`, donde las devoluciones cuentan en negativo (ADR-005).
- **"Hoy" es 2026-09-15.** "Este año" es 2026, "el mes pasado" es agosto de 2026, "este trimestre" va de julio a hoy (a medias) y "el trimestre anterior" es abril-junio de 2026.
- **Periodos** escritos como `fecha >= primer día AND fecha < día siguiente al último`.
- **`fecha` es la fecha de cargo.** Qué fecha expone la vista lo decidirá el ADR-008.
- **Los traspasos entre cuentas propias no son gasto ni ingreso.** Solo salen en `v_movimientos`.
- **0 € no es "no hay datos".** Un periodo con movimientos pero sin gasto en una categoría da 0; un periodo sin ningún movimiento no tiene datos.
- **El SQL de referencia cumple las mismas reglas que el asistente:** una sola sentencia `SELECT`, solo `v_movimientos`, `v_gastos` o `v_ingresos`, con `LIMIT`, sin filtrar nunca por usuario (el aislamiento lo hace RLS) y sin funciones peligrosas.

## Partición dev / test

Mejorar prompts y documentación contra las mismas preguntas con las que se mide hace subir la cifra por ajustarse a esas preguntas. Por eso 34 de las 114 (`evals/golden/splits_v0.yaml`) son **test**: se puntúan en cada ronda y se publican junto al resto, pero ningún cambio se decide por una pregunta de test. Las 80 restantes son **dev**. Las 26 originales no se han movido: las 8 de test añadidas en la semana 5 (GS-093, 096, 099, 102, 105, 108, 111 y 114) son las que la misma regla deriva para las preguntas nuevas, y el fichero solo las añade al final.

La regla es mecánica, para que nadie elija: dentro de cada categoría, en orden de id, una de cada tres preguntas (la 3.ª, la 6.ª, la 9.ª…). `derive_test_ids` la implementa y `tests/evals/test_splits.py` comprueba que el fichero congelado sigue siendo exactamente lo que da la regla. Ampliar el set significa un set nuevo (v1), no editar este fichero. `-T split=dev` o `-T split=test` ejecutan solo una parte, y cada log desglosa el acierto por partición.

## Cada pregunta

`id` (GS-001…, estable y nunca reutilizado), `question`, `user_id`, `category`, `difficulty`, `behavior` (`answer`, `clarify`, `no_data` o `refuse`), `reference_sql`, `ordered` (si el orden de las filas forma parte de la respuesta), `scenario_id` y `notes`. La categoría fija el comportamiento: ambigua es `clarify`, sin datos es `no_data` y fuera de dominio es `refuse`; el resto responden. Las de `no_data` llevan un SQL que cuenta movimientos en el periodo y debe dar 0.

La comparación (`matches`) ignora el orden de las filas salvo que `ordered` sea `true`, ignora el nombre de las columnas y tolera un céntimo.

## Cómo se comprueba

1. **Estructura:** ids contiguos, categorías y dificultades repartidas, usuarios funcionales, anclajes a escenarios reales.
2. **Reglas del SQL:** con controles negativos (otra tabla, sin `LIMIT`, filtro por usuario, `pg_sleep`, varias sentencias…). Es la semilla del validador de la semana 4.
3. **Ejecución bajo RLS** como `app_reader`, con la misma semántica que tendrá el executor (`db/query.py`): transacción de solo lectura, `set_config` como primera sentencia y comprobación de que quedó fijado.
4. **Deriva:** el resultado debe coincidir con `expected_v0.json`, que guarda la versión del dataset y el hash de la configuración. Si cambian los datos, el generador o la capa semántica sin que nadie lo decida, falla.
5. **Verdad por otra vía (diseño del generador §6.3):** las respuestas de las preguntas con escenario se contrastan con `scenarios.params`, y otras con los movimientos crudos del generador sumados en Python. Una discrepancia indica un error en la capa semántica o en el SQL, no en el LLM.

## Cómo añadir o cambiar una pregunta

1. Escribe la pregunta en `golden_v0.yaml` con el siguiente id.
2. Mira el resultado: `uv run safe-spending-golden show GS-0XX`. Léelo con ojo crítico: que el SQL no falle no significa que responda bien (un mes a medias, un periodo sin datos o un resultado vacío por una razón equivocada son los errores típicos).
3. Regenera las respuestas esperadas: `uv run safe-spending-golden refresh`.
4. Comprueba todo: `uv run safe-spending-golden check` y `uv run pytest tests/evals`.
5. Commitea el YAML y `expected_v0.json` juntos.

Si cambias el generador o su configuración, sube `dataset_version` en `config.yaml` y en `golden_v0.yaml`, actualiza la huella del dataset con `uv run safe-spending-generate --update-reference-manifest` y repite el paso 3: el cambio de cifras queda a la vista en el diff de `expected_v0.json`, una línea por pregunta.