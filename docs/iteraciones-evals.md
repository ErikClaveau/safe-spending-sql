# Iteraciones de las evals

Cada fila es una ejecución del golden set v0 (90 preguntas) con `claude-sonnet-5-5`, esfuerzo `medium`, sin *fallback*, contra el dataset 0.5.0. La métrica principal es la tolerante (ADR-003): una respuesta vale si algún subconjunto ordenado de sus columnas coincide con la referencia; la estricta exige las columnas exactas y su orden. `dev` son las 64 preguntas sobre las que se decide qué cambiar y `test` las 26 reservadas (`evals/golden/splits_v0.yaml`, ver `docs/golden-set.md`).

Todas las filas se muestran con la **métrica vigente (M3)**, volviendo a puntuar los logs guardados, sin llamar a la API.

| # | Cambio | Tolerante (todas) | dev | test | Estricta | Coste |
|---|---|---|---|---|---|---|
| 0 | Línea base (prompt v1) | 82,2 % (74/90) | 82,8 % | 80,8 % | 58,9 % | $1,01 |
| 1 | Documentación de las vistas (migración `0003`) | 87,8 % (79/90) | 89,1 % | 84,6 % | 63,3 % | $1,13 |
| 2 | Prompt v2: `COALESCE`, periodo por defecto y solo las columnas pedidas | 83,3 % (75/90) | 84,4 % | 80,8 % | 74,4 % | $1,15 |
| 3 | Prompt v3: como v2 sin la regla de las columnas | **90,0 % (81/90)** | 89,1 % (57/64) | 92,3 % (24/26) | 70,0 % | $1,16 |
| 4 | Autocorrección: una pasada si el validador o la base de datos rechazan el SQL | 90,0 % (81/90) | 89,1 % (57/64) | 92,3 % (24/26) | 70,0 % | $1,17 |
| 5 | Validador con lista blanca de funciones (sin cambio de prompt) | 91,1 % (82/90) | 90,6 % (58/64) | 92,3 % (24/26) | 68,9 % | $1,16 |
| 6 | Documentación de `divisa_original`: un viaje al extranjero son los pagos en otra divisa (migración `0004`) | 91,1 % (82/90) | 92,2 % (59/64) | 88,5 % (23/26) | 70,0 % | $1,19 |

## Versiones de la métrica

- **M1**, la inicial. La línea base daba 72,2 % tolerante y 52,2 % estricta.
- **M2**: un mes escrito `2026-03-01` equivale a `2026-03` (7 preguntas), GS-036 deja de exigir un orden que la pregunta no pide y un rechazo que no inventa cuenta como acierto en `no_data` (GS-081). La línea base pasa a 82,2 %.
- **M3**: la métrica tolerante tampoco penaliza que las mismas columnas salgan en otro orden. Solo cambia la fila 2 (de 80,0 % a 83,3 %): el modelo devolvía las cifras de GS-014, 040 y 062 en otro orden que la referencia.

M2 y M3 se decidieron viendo resultados, por eso se conservan las cifras anteriores y todas las filas se recalculan con la misma métrica.

## Notas por fila

**1. Documentación de las vistas.** Los comercios están en mayúsculas, cómo se identifican la cuenta de ahorro y los traspasos por el concepto, que las comisiones de cambio son un gasto en euros, que una compra es un pago con tarjeta y que el saldo es la suma de movimientos. Arregladas GS-024, 053, 066, 067 y 068; rotas, ninguna. Traspasos pasa del 40 % al 100 %.

**2. Prompt v2.** Tres reglas: `COALESCE(SUM(...), 0)`, todo el historial si no se indica periodo y «devuelve solo las columnas que la pregunta pide». Arregló GS-011 y 012 y rompió ocho más. La regla de las columnas hizo que el modelo quitara columnas que la referencia incluye (los dos meses en una diferencia, el total, la cuenta). La estricta sube once puntos y la tolerante baja: la regla es buena para esa métrica y mala para la respuesta. **Descartada**; la v2 se conserva como registro.

**3. Prompt v3.** La v1 con solo las dos reglas buenas. Arregla GS-011 y 012 (el `COALESCE`, un mecanismo claro). GS-055 pasa a correcta sin que ninguna regla lo explique: ruido. Rompe GS-043 porque el validador rechaza `generate_series(...)` en el `FROM`, una función de tabla inofensiva (ver abajo).

**4. Autocorrección.** Si el validador rechaza el SQL, o la base de datos devuelve un error, el modelo ve su respuesta anterior y el motivo y la escribe de nuevo (máximo una vez; un *timeout* no se corrige). El SQL corregido pasa por el mismo validador y la misma ejecución bajo RLS. En las 90 preguntas solo una necesitó corrección: GS-043, que el modelo había escrito con `generate_series(...)` en el `FROM` y el validador rechazaba; al corregirla, acierta. El total no cambia porque GS-053 (Londres) pasó de correcta a «pide las fechas», que es ruido (en la fila 1 había pasado al revés). Coste: $0,01 más en total. Se mide con `-T max_corrections=0` frente al valor por defecto.

**5. Lista blanca de funciones.** El validador pasa de una lista negra a una lista blanca de funciones (ADR-005). No es una mejora de acierto y no se presenta como tal: 82 frente a 81 aciertos está dentro del ruido (error estándar de unos 3 puntos) y la fila se mide para comprobar que **no hay regresión**. Se hizo en el CI de GitHub (Linux), no en la máquina de las filas anteriores. Antes de medir, las 444 sentencias que el modelo escribió en los logs seguían pasando por el validador; el acierto no prueba que el modelo no haya tropezado con la lista: una función rechazada y autocorregida también acaba en acierto. Contadas las correcciones: en la ejecución completa de la fila 6, que ya usa la lista blanca, ninguna de las 90 preguntas necesitó corrección (`corrections` = 0 en todas) y ninguna consulta se rechazó con `is not allowed`; los tres logs parciales de ese día tampoco. El log de la fila 5 está en el CI de GitHub y no se ha descargado, así que la comprobación se hizo con la fila 6, que es el mismo validador. Con el modelo actual la lista no se interpone en el camino de las preguntas del golden set. No se han vuelto a analizar los fallos que quedan: la lista de abajo es la de la fila 4.

**6. Documentación de la divisa de un viaje.** Los comentarios de `divisa_original` dicen que un viaje al extranjero se reconoce por los pagos en una divisa distinta del euro y que no hace falta preguntar las fechas (ADR-010: asumir y explicitar). Arregla GS-053 y GS-056, que pedían las fechas del viaje a Londres (con `--epochs 3` sobre esas dos, 6/6 correctas con la métrica tolerante). Rompe GS-055 (*test*): el modelo filtra las comisiones por `concepto ILIKE '%GBP%'` y suma 0, porque el concepto de la comisión no menciona la divisa. Repetida con `--epochs 3`, acierta las tres veces (la consulta incluye las comisiones de los días de pagos en libras): es ruido, como GS-053 en la fila 1, y no se cambia nada. El total no cambia (82 frente a 81 en la fila 4) y queda dentro del ruido.

## Comparación de modelos (ADR-004)

Misma configuración que la fila 6 (prompt v3, documentación `0004`, esfuerzo `medium`, una autocorrección) con otro modelo. Una ejecución completa por modelo, sin repeticiones: el error estándar es de unos 3 puntos.

| Modelo | Tolerante (todas) | dev | test | Estricta | Coste | Por 1.000 consultas |
|---|---|---|---|---|---|---|
| `claude-haiku-5-5` | 84,4 % (76/90) | 82,8 % (53/64) | 88,5 % (23/26) | 66,7 % | $0,08 | $0,9 |
| `claude-sonnet-5-5` (fila 6) | **91,1 % (82/90)** | 92,2 % (59/64) | 88,5 % (23/26) | 70,0 % | $1,19 | $13,2 |
| `claude-opus-5-5` | 90,0 % (81/90) | 89,1 % (57/64) | 92,3 % (24/26) | 52,2 % | $2,68 | $29,8 |

- **Opus no mejora a Sonnet** (81 frente a 82, dentro del ruido) y cuesta 2,3 veces más. Su estricta es mucho más baja porque devuelve más columnas de las que la referencia espera; la tolerante lo absorbe. Un fallo nuevo es GS-081 (`generation_failed`): responde `action: query` sin `sql` tres veces seguidas y el validador de la salida lo rechaza.
- **Haiku pierde 6 puntos y cuesta 15 veces menos.** Sus fallos nuevos son consultas incorrectas (GS-004, 025, 038, 045, 058, 069), una aclaración donde debía consultar (GS-081) y GS-085, una respuesta donde debía rechazar. Para una asistente sobre datos bancarios, ese último tipo de error pesa más que su frecuencia.
- Los fallos de referencia estricta (GS-033, 046, 049, 050, 052, 086) son los mismos en los tres modelos: no dependen del modelo.
- Coste por 1.000 consultas: coste de la ejecución de 90 preguntas × 1.000/90, sin síntesis de respuesta.

## Set ampliado: 114 preguntas (semana 5)

Se añaden 24 preguntas de `recurrentes` (GS-091 a GS-114, 8 de ellas de *test*). Las filas de arriba son del set de 90 y no se recalculan; esta es la primera medición del set nuevo, con la misma configuración que la fila 6.

| Set | Tolerante (todas) | dev | test | Estricta | Coste |
|---|---|---|---|---|---|
| 114 preguntas | 89,5 % (102/114) | 87,5 % (70/80) | 94,1 % (32/34) | 68,4 % | $1,50 |
| Las 90 originales dentro de esa ejecución | 92,2 % (83/90) | | | | |
| Las 24 nuevas | 79,2 % (19/24) | | 100 % (8/8) | | |

- **Las 8 nuevas de *test* salen bien; las 5 que fallan son de *dev*** (GS-091, 097, 100, 106 y 109). Las cinco tienen la misma forma: el modelo devuelve el detalle en vez de la cifra única que pide la pregunta (36 meses de alquiler con 790 cada uno, el día de cobro con tres filas y más columnas, todas las suscripciones, todos los cargos de Amazon Prime, los dos empleadores por fecha). La respuesta sintetizada puede estar bien, pero la consulta no entrega el dato directo.
- **Las 90 originales dan 83/90**, una más que en la fila 6: GS-055 acertó (era ruido). Los 7 fallos son los de referencia estricta de siempre.
- **Cinco de veinticuatro es una señal, no un problema de referencia**: las preguntas se escribieron para tener una respuesta inequívoca. Es un candidato a la siguiente ronda (se decide solo con las de *dev*), por ejemplo una regla de prompt «si la pregunta pide un dato, responde con una fila». Ya hubo una regla parecida en la fila 2 («devuelve solo las columnas pedidas») y rompió ocho preguntas, así que habría que medirla con `--epochs 3`.
- Cada respuesta nueva se contrastó con una vía que no usa las vistas (parámetros de escenario y movimientos crudos) en `tests/evals/test_golden_truth.py`.

### Segunda tanda: 133 preguntas

Se añaden 19 de `filtro_compuesto` (GS-115 a GS-133, 7 de ellas de *test*), con varios filtros a la vez.

| Set | Tolerante (todas) | dev | test | Estricta | Coste |
|---|---|---|---|---|---|
| 133 preguntas | 91,0 % (121/133) | 89,1 % (82/92) | 95,1 % (39/41) | 71,4 % | $1,74 |
| Filtro compuesto (27) | 92,6 % (25/27) | | | | |

- **18 de las 19 nuevas aciertan.** La que falla, GS-125 («compras de más de 100 euros de lunes a viernes»), era un **error de mi referencia**: contaba también el alquiler y los recibos (15), mientras que una compra es un pago con tarjeta según la documentación de la vista (6). El modelo aplicó la definición del proyecto. La referencia se corrigió después de ver el fallo y la nota de la pregunta lo dice; no se ha vuelto a medir porque la API alcanzó su límite de uso (hasta el 2026-11-01). Con la referencia corregida la respuesta del modelo (6) coincide, es decir, 122/133 (91,7 %), pero la cifra medida es 121/133.
- Los 11 fallos restantes son los 7 de referencia estricta de siempre (GS-033, 041, 046, 049, 050, 052, 086) y los 4 de forma de recurrentes de la tanda anterior (GS-091, 097, 106, 109); GS-100 acertó esta vez.
- Las pruebas contra movimientos crudos cubren cuatro de las nuevas (GS-121, 122, 123 y 130).
## Ruido y contaminación

Cada fila es una ejecución y el modelo no es determinista: el error estándar es de unos 3 puntos sobre 90 preguntas, y cada fila tiene entre uno y tres cambios que son ruido (GS-053 en la fila 1, GS-055 en la 3). Las diferencias de uno o dos puntos no son concluyentes. Para fiarse de una mejora pequeña hay que repetir con `--epochs 3`.

El análisis de fallos del baseline se hizo viendo las 90 preguntas, también las de test, y la ronda 1 se diseñó con esa información. Desde la ronda 2 las decisiones se toman solo con fallos de dev.

## Fallos que quedan en la fila 4 (9)

- **Recurrentes (GS-046, 049, 050, 052, 086).** La referencia espera una forma concreta (tramos de precio, historial completo) que la pregunta no define.
- **GS-033.** Total conjunto frente a desglose por comercio.
- **GS-041.** Un porcentaje redondeado a dos decimales frente a uno.
- **GS-053** (Londres) alterna entre correcta y «pide las fechas» de una ejecución a otra.
- **GS-056.** Pide las fechas del viaje a Londres.
