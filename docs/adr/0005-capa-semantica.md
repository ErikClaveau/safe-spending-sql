# ADR-005: El LLM solo consulta una capa semántica de vistas a nivel de movimiento

**Estado:** Aceptado (enmendado el 2026-10-03, ver sección "Enmiendas")
**Fecha:** 2026-10-01
**Decide:** Erik Claveau
**Relacionados:** ADR-001 (PostgreSQL), ADR-002 (aislamiento con RLS), ADR-008 (fechas y divisas)

## Contexto

En text-to-SQL, buena parte de los errores no son sintácticos sino semánticos: sumar sin tener en cuenta el signo, olvidar restar devoluciones, mezclar divisas, contar transferencias entre cuentas propias como gasto o inventar el nombre de una categoría. Si el LLM consulta las tablas base, tiene que acertar esas reglas de negocio en cada consulta. Además, un error semántico produce una cifra plausible pero incorrecta, que es el peor fallo posible en un asistente financiero.

Restricciones heredadas:

- **ADR-002.** El aislamiento lo impone RLS y el LLM no conoce el `user_id`. Las vistas deben usar `security_invoker = true`, lo que obliga a que `app_reader` tenga `SELECT` sobre las tablas base.
- **Público.** Las preguntas llegan en castellano, pero el repositorio debe ser comprensible para lectores en inglés.
- **Metodología.** La métrica principal es la execution accuracy, y el proyecto sigue una metodología de mejora guiada por análisis de errores.

## Decisión

### 1. Solo vistas

El LLM trabaja exclusivamente sobre una capa semántica de vistas. Las tablas base no se le describen ni puede referenciarlas. La restricción se impone así:

- El `SchemaProvider` solo describe las vistas semánticas.
- El validador (sqlglot) rechaza cualquier consulta que referencie un objeto fuera de la allowlist de vistas. sqlglot **solo valida, nunca reescribe** el SQL (ADR-002).
- `app_reader` mantiene `SELECT` sobre las tablas base porque `security_invoker` lo exige. La restricción a vistas **no** la imponen los `GRANT`.

Si el validador fallara y una consulta sobre una tabla base llegara a ejecutarse, RLS seguiría filtrando por usuario. El impacto sería de calidad de respuesta, no de aislamiento.

### 2. Granularidad a nivel de movimiento

Todas las vistas iniciales tienen una fila por movimiento. No se crean vistas agregadas (por ejemplo, gasto mensual por categoría) salvo que el análisis de errores muestre una categoría de fallo recurrente que una vista agregada resolvería. Cada vista que se añada debe ir acompañada de la métrica que la justifica.

### 3. Tres vistas con convenciones de signo explícitas

| Vista | Contenido | Columna de importe | Convención |
|---|---|---|---|
| `v_movimientos` | Todos los movimientos | `importe_eur` | Signo natural: negativo sale, positivo entra |
| `v_gastos` | Todos los cargos no internos (compras, recibos, comisiones, Bizum y transferencias enviadas, retiradas de efectivo) y las devoluciones | `gasto_eur` | Positivo para gastos y negativo para devoluciones; `SUM(gasto_eur)` es el gasto neto |
| `v_ingresos` | Todos los abonos no internos excepto las devoluciones (nóminas, Bizum y transferencias recibidas, otros ingresos) | `ingreso_eur` | Positivo |

- Los traspasos entre cuentas propias (`counterparty_account_id` informado) son los únicos movimientos excluidos de `v_gastos` y `v_ingresos`.
- **Invariante:** todo movimiento no interno pertenece exactamente a una de las dos vistas. Por tanto, `SUM(ingreso_eur) - SUM(gasto_eur)` coincide con la variación real del saldo. Se verifica con un test de SQL.
- La columna de importe tiene un nombre distinto en cada vista para que la convención de signo se lea en el propio nombre y no se confunda al combinar vistas.

### 4. Idioma: tablas en inglés, vistas en castellano

- **Tablas base en inglés** (capa de ingeniería, alineada con los nombres de NextGenPSD2).
- **Vistas y columnas semánticas en castellano** (capa de producto, en el idioma de las preguntas). Las vistas funcionan también como capa de traducción.
- **Diccionario de datos en inglés** en `docs/data-dictionary.md`, con cada vista y columna, su tipo y su significado. Un test de CI comprueba que todas las columnas de las vistas semánticas aparecen en el diccionario.

Columnas previstas (versión inicial, ajustable tras el análisis de errores):

| Columna | Significado |
|---|---|
| `id_movimiento` | Identificador del movimiento; necesario para trazabilidad y verificación numérica |
| `fecha` | Fecha del movimiento; provisionalmente la fecha de cargo (se decide en ADR-008) |
| `importe_eur` / `gasto_eur` / `ingreso_eur` | Importe en euros según la convención de cada vista |
| `importe_original`, `divisa_original` | Importe y divisa originales de la operación (todas las cuentas son en euros) |
| `categoria`, `grupo_categoria` | Categoría y grupo, con valores de una lista cerrada |
| `comercio` | Nombre normalizado del comercio (solo empresas) |
| `contraparte` | Ordenante o beneficiario tal como aparece en el movimiento (incluye personas en Bizum y transferencias) |
| `concepto` | Concepto original (`description_raw`); texto **no confiable** |
| `medio_pago` | Tarjeta, recibo, transferencia, Bizum, etc. |
| `cuenta` | IBAN enmascarado de la cuenta, derivado del IBAN sintético completo de `accounts` |

Ninguna vista expone `user_id` (ADR-002).

### 5. Descripción del esquema para el LLM

- La documentación vive en la base de datos, con `COMMENT ON VIEW` y `COMMENT ON COLUMN` en castellano, versionada en las migraciones.
- El `SchemaProvider` la obtiene por introspección, de modo que la descripción y el esquema real no pueden divergir.
- El `SchemaProvider` incluye la **lista cerrada de valores** de `categoria` y `grupo_categoria`, para evitar filtros con nombres inventados que devuelven 0 filas sin dar error.
- Cada experimento de evaluación registra la **versión del esquema semántico** junto al commit, el modelo, el prompt y la versión del dataset.

## Opciones consideradas

### Opción A: El LLM consulta las tablas base

**Pros:** máxima flexibilidad; no hay capa adicional que mantener.

**Contras:** el LLM tiene que resolver signos, devoluciones, divisas y transferencias internas en cada consulta; más joins, más superficie de error y errores semánticos silenciosos.

### Opción B: Solo vistas semánticas (elegida)

**Pros:** las reglas de negocio se resuelven una vez y se prueban; esquema más pequeño y en el idioma de las preguntas; mejor schema linking.

**Contras:** hay que mantener las vistas; una pregunta que las vistas no cubran no se puede responder hasta ampliarlas.

### Opción C: Mixto (vistas y tablas)

**Descartada.** Da al modelo dos caminos para responder lo mismo, y tenderá a elegir el incorrecto precisamente en los casos difíciles.

### Alternativas descartadas dentro de la opción B

- **Una única vista `v_movimientos` con columna de tipo.** Esquema más simple, pero devuelve al LLM la responsabilidad de filtrar y aplicar los signos correctamente en cada consulta.
- **Vistas agregadas desde el inicio.** Limitan las preguntas respondibles (los filtros por día, importe o medio de pago no caben en un agregado mensual) y abren la puerta a dobles conteos al combinarse con vistas de detalle. Se aplazan hasta que el análisis de errores las justifique.
- **Vistas con permisos del propietario (sin `security_invoker`) para imponer "solo vistas" mediante `GRANT`.** Exigiría rediseñar las políticas de RLS del ADR-002 para aplicarlas al propietario de las vistas. No aporta aislamiento adicional, porque una consulta sobre tablas base también está protegida por RLS.

## Análisis de trade-offs

La capa semántica traslada complejidad del LLM a SQL escrito y probado por una persona. Ese intercambio es favorable porque el error que evita, una cifra plausible pero incorrecta, es difícil de detectar para el usuario y es exactamente lo que el proyecto quiere eliminar. El coste es la pérdida de flexibilidad ante preguntas no previstas, y se gestiona con el ciclo de análisis de errores: si una categoría de preguntas falla por falta de cobertura, se amplía la capa semántica y se mide el efecto.

## Consecuencias

**Más fácil**
- Las preguntas más frecuentes se reducen a agregaciones sencillas sobre una vista.
- Las reglas de negocio se prueban con tests de SQL independientes del LLM.
- Un lector en inglés entiende las tablas directamente y las vistas a través del diccionario.

**Más difícil**
- Hay que mantener las vistas, sus comentarios y el diccionario sincronizados (este último, verificado en CI).
- El generador de datos debe producir la información necesaria para clasificar cada movimiento: tipo de operación, devoluciones enlazadas con su compra y transferencias internas identificables.

**A revisar**
- **ADR-008:** qué fecha expone `fecha` y cómo se convierte a euros.
- **Semana 4:** la allowlist de sqlglot incluye exactamente las vistas semánticas.
- **Semana 6:** idioma del README y de los ADRs para lectores en inglés.

## Próximos pasos

1. [x] Renombrar a inglés las columnas de las tablas base en el modelo de datos (migración `0001`).
2. [x] Implementar `v_movimientos`, `v_gastos` y `v_ingresos` con `security_invoker = true` y sus `COMMENT ON` (migración `0002`, 2026-10-06).
3. [x] Tests de SQL de las reglas de negocio: devoluciones restan, traspasos internos excluidos, invariante de pertenencia a exactamente una vista y conversión a euros (`tests/db/test_semantic_views.py`).
4. [x] Crear `docs/data-dictionary.md` y el test de CI que verifica que todas las columnas están documentadas (en ambos sentidos: nada sin documentar y nada documentado que ya no exista).
5. [ ] Implementar el `SchemaProvider` por introspección, con las listas cerradas de categorías.
6. [ ] Añadir la versión del esquema semántico a los metadatos de experimentos y a las trazas.

## Enmiendas

### 2026-10-03: clasificación completa de los movimientos no internos

Al diseñar la taxonomía de categorías del generador se detectó una ambigüedad: si los Bizum recibidos contaban como ingreso pero los enviados no contaban como gasto, la pregunta "¿cuánto ahorré?" daba un resultado incorrecto. Se acuerda:

- `v_gastos` incluye todos los cargos no internos, también Bizum y transferencias a terceros y retiradas de efectivo, más las devoluciones con signo negativo.
- `v_ingresos` incluye todos los abonos no internos excepto las devoluciones.
- Los traspasos internos se identifican por `counterparty_account_id` y son los únicos movimientos fuera de ambas vistas.
- Se añade el invariante de pertenencia a exactamente una vista, verificado en CI.

### 2026-10-06: decisiones de implementación de la migración `0002`

- **El signo de `amount_eur` lo fija el tipo de operación**, con una restricción `CHECK` en `transactions` (`transactions_sign_matches_tx_code`): `CARD_PURCHASE`, `DIRECT_DEBIT`, `TRANSFER_OUT`, `BIZUM_OUT`, `FEE` y `ATM_WITHDRAWAL` son negativos; `CARD_REFUND`, `TRANSFER_IN`, `BIZUM_IN` y `SALARY` son positivos; el cero es imposible. Es lo que garantiza en la base de datos que todo movimiento no interno cae en exactamente una vista. El generador debe respetarla.
- **`v_gastos` y `v_ingresos` llevan `gasto_original` e `ingreso_original`** (con la misma convención de signo que su columna en euros) en lugar de `importe_original`, para que la convención de signo siga leyéndose en el nombre de cada columna de importe. `v_movimientos` mantiene `importe_original` con signo natural.
- **`medio_pago`** se calcula con la función `medio_pago_de(tx_code)`, fuente única para las tres vistas. `app_reader` solo tiene `EXECUTE` sobre ella.
- **`cuenta`** muestra el código de país, asteriscos y los 4 últimos dígitos del IBAN.
- **`fecha`** es `booking_date`, provisionalmente hasta ADR-008.
