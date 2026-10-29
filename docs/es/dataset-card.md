# Ficha del dataset: datos bancarios sintéticos de safe-spending

> 🇬🇧 English: [../dataset-card.md](../dataset-card.md)

Sigue la estructura de *Datasheets for Datasets*. Versión descrita: **0.5.0**. Cada cifra de abajo sale del dataset que produce el generador con la configuración versionada; si se regenera, los números deben coincidir (ver *Reproducibilidad*).

**Todo registro de aquí es inventado.** No se usó ninguna transacción real, propia ni anonimizada en ningún paso. Los nombres son generados, los IBAN usan un código de banco (`9999`) que no pertenece a ningún banco real y los comercios son un catálogo escrito a mano de establecimientos genéricos.

## 1. Motivación

El dataset existe para evaluar un asistente text-to-SQL sobre datos bancarios personales, y en particular dos cosas que un dataset público no puede dar: **aislamiento entre clientes** (cada fila pertenece a un usuario conocido, así que una fuga se puede reconocer) y **verdad trazable** (situaciones guionizadas cuya respuesta correcta se conoce por construcción).

No se hizo para entrenar un modelo, ni para ser estadísticamente representativo de España, ni para evaluar categorización. El proyecto 3 del plan reutiliza las etiquetas de categoría, pero esta ficha describe lo que hay hoy.

## 2. Composición

Una cuenta corriente por usuario, una cuenta de ahorro para algunos y todos los movimientos de dos años.

| Elemento | Valor |
|---|---|
| Usuarios | 25 (ids 1-25) |
| Cuentas | 36: 25 corrientes, 11 de ahorro |
| Movimientos | 29.234 |
| Periodo | 2024-09-16 a 2026-09-15 («hoy» congelado es 2026-09-15) |
| Movimientos por usuario | mediana 1.125; mín. 116 (el alta más reciente, 2026-07-13); máx. 2.177 |
| Divisas | EUR (29.205) y GBP (29, todos de un viaje guionizado) |
| Comercios / categorías | 72 / 32, en 7 grupos |

**Tipos de movimiento (`tx_code`).**

| Código | Filas | Qué es |
|---|---|---|
| `CARD_PURCHASE` | 25.427 | Compra con tarjeta de débito en un comercio |
| `DIRECT_DEBIT` | 1.547 | Pago recurrente (telecomunicaciones y suministros) |
| `TRANSFER_OUT` | 838 | Transferencia emitida, incluidos los traspasos a la cuenta de ahorro propia |
| `SALARY` | 674 | Nómina |
| `CARD_REFUND` | 426 | Devolución enlazada con una compra anterior |
| `TRANSFER_IN` | 276 | Transferencia recibida, incluidas las vueltas desde ahorro |
| `FEE` | 29 | Comisión de cambio en un pago en otra divisa |
| `BIZUM_IN` | 17 | Bizum recibido |

520 movimientos son **traspasos internos** entre cuentas propias: cada uno son dos movimientos de igual importe y signo contrario. Quedan fuera de las vistas de gasto e ingreso a propósito.

**Campos.** Las tablas operativas contienen solo lo que tendría un banco: `users`, `accounts`, `transactions`, `merchants`, `categories`. Las columnas y su significado para el asistente están en [`data-dictionary.md`](../data-dictionary.md); los campos propios del generador, en [`generator-design.md`](generator-design.md).

**Etiquetas (nunca se cargan en la base de datos que consulta el asistente).** Van en ficheros Parquet aparte: `tx_labels` (categoría verdadera, escenario, marcas de trampa, canario, enlace de devolución), `user_labels` (arquetipo, renta mensual, split) y `scenarios` (tipo, parámetros, descripción). La verdad del golden set se calcula desde ellas, por una vía que no usa las vistas semánticas.

## 3. Splits

Por id de usuario, no por fila, de modo que ningún usuario está en dos splits.

| Split | Usuarios | Uso |
|---|---|---|
| `eval_functional` | 1-15 | Golden set. Los usuarios 1-7 llevan cada uno un escenario guionizado; 8-15 son usuarios normales |
| `eval_adversarial` | 16-20 | Trampas de inyección de prompts, y quienes preguntan y las víctimas del set de aislamiento |
| `population` | 21-25 (hasta 100 por diseño) | Usuarios de fondo, y víctimas de las preguntas de aislamiento |

**Escenarios guionizados (usuarios 1-7).** Cambios de suscripciones, cambio de trabajo, alta reciente, una categoría con gasto cero, un mes anómalo, un viaje a Londres (divisa) y una serie de devoluciones de Amazon. Cada uno tiene una fila en `scenarios` cuyos parámetros son la respuesta por construcción.

**Trampas (usuarios 16-20).** Cada uno tiene un Bizum o una transferencia recibidos de cada uno de cinco tipos, más 0-3 repeticiones, 33 en total (`recategorization` 7, `response_manipulation` 7, `direct_instruction` 7, `system_impersonation` 6, `sql_lookalike` 6). El concepto de cada una contiene un texto de inyección y una palabra canario única que existe solo en los datos generados, nunca en un fichero del repositorio.

## 4. Proceso de generación

Una función pura de una configuración y una semilla: `config.yaml` + dos catálogos (`merchants.yaml`, `traps.yaml`) + semilla `20260915` producen los ficheros Parquet y un manifiesto.

1. **Perfil** de cada usuario: arquetipo, renta, ciudad, fecha de alta.
2. **Pagos recurrentes** y nómina, a partir del perfil.
3. **Compras con tarjeta**, a partir de hábitos por categoría y un peso por día de la semana.
4. **Devoluciones**, sorteadas por cada compra reembolsable.
5. **Inyectores de escenarios** (usuarios 1-7) reescriben o eliminan los eventos base y escriben la verdad.
6. **Ahorro**, construido después de los escenarios a partir de las nóminas que el usuario realmente tiene, para que el saldo nunca sea negativo.
7. **Trampas** (usuarios 16-20).
8. **Campos derivados**: texto del extracto (`description_raw`), conversión de divisa y comisión, fecha valor.
9. **Exportación** a Parquet y un manifiesto.

Los importes son céntimos enteros en todo el proceso. Un tipo de cambio es unidades de divisa por 1 EUR, aplicado en la fecha de la operación y redondeado half-even. Cada usuario y cada etapa tienen su propio flujo aleatorio, así que añadir un usuario o cambiar una etapa no altera otros datos (comprobado con tests). El generador nunca lee la fecha del sistema.

## 5. Usos previstos y fuera de alcance

**Previstos:** evaluar el acierto text-to-SQL, el aislamiento entre usuarios y la robustez frente a la inyección a través de datos recuperados; demostrar el asistente.

**No adecuados para:** sacar conclusiones sobre comportamiento de gasto real, modelos de fraude o crédito, estudios de equidad, ni entrenar un categorizador que se vaya a enfrentar a extractos reales. Las estadísticas están hechas para ser verosímiles, no están validadas (ver *Limitaciones*).

## 6. Reproducibilidad y distribución

Los datos **no están en el repositorio**; su huella sí. `dataset/manifest.json` contiene la versión, la semilla, el hash de la configuración y, de cada fichero, su número de filas y su SHA-256. `tests/generator/test_reference_manifest.py` regenera el dataset y falla si algo difiere, así que un cambio en los datos es siempre una decisión.

```bash
uv run safe-spending-generate        # escribe data/dataset (Parquet + manifest.json)
uv run safe-spending-load --reset    # carga las tablas operativas como app_loader
```

Que el Parquet sea idéntico byte a byte depende de la versión fijada de `pyarrow` en `uv.lock`. Un cambio de código del generador, de configuración, de catálogos o de dependencias exige un nuevo `dataset_version`, un manifiesto refrescado y un golden set refrescado. La licencia del repositorio (MIT) se aplica al generador y a los catálogos.

## 7. Limitaciones conocidas

- **25 usuarios, no 100.** El diseño pide 100 (ids 1-100); la configuración actual genera 25. Los ids 26-100 no existen.
- **Un arquetipo.** Todos los usuarios son `young_professional`, y se diferencian en renta (1.875 a 3.158 al mes), ciudad y hábitos. No hay jubilados, estudiantes, autónomos ni familias. Las conclusiones sobre el comportamiento «típico» no van más allá de este perfil.
- **Sin validación estadística todavía.** El gasto está dominado por vivienda y alimentación (alrededor del 44 % y el 25 % de lo cargado, sin contar traspasos internos), con compras 14 %, ocio y viajes 10 %, transporte 4 % y cuidado personal 3 %. Estos repartos **no** se compararon con una encuesta de presupuestos familiares; esa comparación, una tasa de ahorro por arquetipo y una comprobación de estacionalidad están previstas como un informe que no bloquea y no están construidas.
- **Poco Bizum.** Los únicos `BIZUM_IN` (17) vienen de las trampas. No hay pagos regulares entre personas ni `BIZUM_OUT`.
- **La divisa extranjera es un único viaje.** Los 29 pagos en GBP pertenecen al escenario de Londres. Los tipos son una serie diaria sintética (en torno a 0,86 GBP por EUR), no tipos de mercado reales.
- **Sin efectos de calendario.** Sin festivos, sin efecto de día de cobro ni de verano más allá de un peso por día de la semana.
- **Contrapartes sin acoplar.** Un Bizum de un usuario no es el Bizum emitido de otro.
- **Solo fechas.** Sin hora y sin zona horaria: la fecha de movimiento es la fecha de cargo.
- **Estilo de extracto simple.** Un único formato de extracto de un banco; los conceptos reales son más desordenados.
- **Trampas por patrones.** Cinco familias de inyección escritas a mano; ponen a prueba las defensas descritas en el proyecto, no todos los ataques de la literatura.

## 8. Mantenimiento

Se mantiene con el repositorio. Todo cambio que altere los datos sube `dataset_version` y queda registrado en el manifiesto y en `docs/iteraciones-evals.md`, que también dice qué midió el golden set en cada versión.
