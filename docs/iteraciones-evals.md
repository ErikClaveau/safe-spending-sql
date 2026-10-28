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

**5. Lista blanca de funciones.** El validador pasa de una lista negra a una lista blanca de funciones (ADR-005). No es una mejora de acierto y no se presenta como tal: 82 frente a 81 aciertos está dentro del ruido (error estándar de unos 3 puntos) y la fila se mide para comprobar que **no hay regresión**. Se hizo en el CI de GitHub (Linux), no en la máquina de las filas anteriores. Antes de medir, las 444 sentencias que el modelo escribió en los logs seguían pasando por el validador; el acierto no prueba que el modelo no haya tropezado con la lista: una función rechazada y autocorregida también acaba en acierto. Falta contar en el log (`corrections` con `is not allowed`) cuántas veces ocurrió. No se han vuelto a analizar los fallos que quedan: la lista de abajo es la de la fila 4.

## Ruido y contaminación

Cada fila es una ejecución y el modelo no es determinista: el error estándar es de unos 3 puntos sobre 90 preguntas, y cada fila tiene entre uno y tres cambios que son ruido (GS-053 en la fila 1, GS-055 en la 3). Las diferencias de uno o dos puntos no son concluyentes. Para fiarse de una mejora pequeña hay que repetir con `--epochs 3`.

El análisis de fallos del baseline se hizo viendo las 90 preguntas, también las de test, y la ronda 1 se diseñó con esa información. Desde la ronda 2 las decisiones se toman solo con fallos de dev.

## Fallos que quedan en la fila 4 (9)

- **Recurrentes (GS-046, 049, 050, 052, 086).** La referencia espera una forma concreta (tramos de precio, historial completo) que la pregunta no define.
- **GS-033.** Total conjunto frente a desglose por comercio.
- **GS-041.** Un porcentaje redondeado a dos decimales frente a uno.
- **GS-053** (Londres) alterna entre correcta y «pide las fechas» de una ejecución a otra.
- **GS-056.** Pide las fechas del viaje a Londres.
