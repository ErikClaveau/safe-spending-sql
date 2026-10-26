# Iteraciones de las evals

Cada fila es una ejecución del golden set v0 (90 preguntas) con `claude-sonnet-5-5`, esfuerzo `medium`, sin *fallback*, contra el dataset 0.5.0. La métrica principal es la tolerante con columnas extra (ADR-003); la estricta exige las columnas exactas de la referencia. `dev` son las 64 preguntas sobre las que se decide qué cambiar y `test` las 26 reservadas (`evals/golden/splits_v0.yaml`): ver `docs/golden-set.md`.

| # | Cambio | Tolerante (todas) | dev | test | Estricta | Coste |
|---|---|---|---|---|---|---|
| 0 | Línea base, métrica inicial | 72,2 % (65/90) | — | — | 52,2 % | $1,01 |
| 0b | La misma ejecución, re-puntuada con la métrica corregida | 82,2 % (74/90) | 82,8 % (53/64) | 80,8 % (21/26) | 58,9 % | $1,01 |
| 1 | Documentación de las vistas (migración `0003`) | **87,8 % (79/90)** | 89,1 % (57/64) | 84,6 % (22/26) | 63,3 % | $1,13 |

## Notas

**Fila 0b: la métrica corregida.** Tras ver los fallos del baseline se corrigieron tres cosas de la vara de medir, no del asistente: un mes escrito `2026-03-01` equivale a `2026-03` (7 preguntas), GS-036 dejó de exigir un orden que la pregunta no pide y un rechazo que no inventa cuenta como acierto en `no_data` (GS-081). Se decidió después de ver los resultados, por eso se publican las dos filas. Desde aquí se compara siempre con la 0b.

**Fila 1.** Comentarios de las vistas que faltaban: los comercios están en mayúsculas, cómo se identifican las cuentas de ahorro y los traspasos por su concepto, que las comisiones de cambio son un gasto en euros, que una compra es un pago con tarjeta y que el saldo es la suma de movimientos. Arregladas: GS-024, 053, 066, 067 y 068. Rotas: ninguna. Traspasos pasa del 40 % al 100 %.

**Ruido.** Cada fila es una sola ejecución y el modelo no es determinista: el error estándar es de unos 3,5 puntos sobre 90 preguntas. GS-053 pasó a correcta sin que se documentara nada sobre Londres, así que parte de lo que se mueve es ruido. Cinco arregladas y ninguna rota apuntan a una mejora real, pero conviene repetir con `--epochs 3` antes de dar por buena una diferencia pequeña.

**Contaminación.** El análisis de fallos de la fila 0 se hizo viendo las 90 preguntas, también las de test, y la ronda 1 se diseñó con esa información. La partición protege de aquí en adelante: las siguientes rondas se deciden solo con fallos de dev.

**Fallos que quedan en la fila 1 (11).** Rotación del periodo por defecto y forma de la respuesta (recurrentes: GS-046, 049, 050, 052, 086), `NULL` en lugar de 0 (GS-011, 012), el total frente al desglose por comercio (GS-033), un porcentaje redondeado distinto (GS-041), comisiones que filtra por la divisa del concepto (GS-055) y fechas del viaje a Londres (GS-056).
