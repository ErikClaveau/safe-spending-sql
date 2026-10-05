# Diseño del generador de datos sintéticos

**Estado:** Aprobado (diseño); implementación en la semana 2
**Fecha:** 2026-10-03
**Autor:** Erik Claveau
**Relacionados:** ADR-001 (PostgreSQL), ADR-002 (aislamiento con RLS), ADR-005 (capa semántica), ADR-008 (fechas y divisas, pendiente)

## 1. Propósito y límites

El generador produce movimientos bancarios sintéticos, realistas y reproducibles para tres usos:

1. Alimentar la base de datos del asistente (proyecto 1).
2. Servir de base al golden set y a los sets adversariales.
3. Ser reutilizado como dataset de categorización (proyecto 3) y como base para inyectar patrones sospechosos (proyecto 5).

**Límite de tiempo:** dos semanas (diseño en la semana 1, implementación en la semana 2). El objetivo es un realismo suficiente, no perfecto. Si la calibración se alarga, se recorta realismo antes que retrasar el pipeline o las evals.

**Solo datos sintéticos:** nunca movimientos reales, tampoco propios ni anonimizados.

## 2. Principios de diseño

1. **La base de datos solo contiene lo que tendría un banco real.** Todo lo que el generador "sabe" y un banco no sabría (arquetipos, escenarios, trampas, enlaces entre devolución y compra) se guarda en ficheros de etiquetas que nunca se cargan en la base de datos que consulta la aplicación.
2. **Función pura.** El generador es una función de configuración y semilla que produce ficheros. No accede a la base de datos; la carga la hace un componente separado.
3. **Independencia por usuario.** Cada usuario se genera con su propio flujo aleatorio, de modo que añadir, quitar o modificar usuarios no altera los datos de los demás.
4. **Verdad por construcción.** Los escenarios de evaluación se inyectan de forma controlada, así que sus respuestas correctas se conocen sin depender de la capa semántica.

## 3. Contrato de salida

### 3.1 Datos operativos (se cargan en Postgres)

```
users(user_id INT, name, city, signup_date DATE)
accounts(account_id INT, user_id INT, iban TEXT, currency CHAR(3))
transactions(tx_id BIGINT, account_id INT, user_id INT,
             booking_date DATE, value_date DATE,
             amount NUMERIC(12,2), currency CHAR(3),
             exchange_rate NUMERIC(12,6) NULL, amount_eur NUMERIC(12,2),
             description_raw TEXT, counterparty TEXT, tx_code TEXT,
             merchant_id INT NULL, category_id INT,
             counterparty_account_id INT NULL)
merchants(merchant_id INT, normalized_name, mcc CHAR(4))
categories(category_id INT, name, group_name)
```

Semántica de los campos con más carga:

| Campo | Significado |
|---|---|
| `amount`, `currency` | Importe y divisa originales de la operación, con signo (negativo = cargo). El convenio de signo se verificará contra NextGenPSD2. |
| `amount_eur` | Importe cargado o abonado en la cuenta. Todas las cuentas son en euros. |
| `exchange_rate` | Tipo aplicado en operaciones en divisa; nulo en operaciones en euros. |
| `counterparty_account_id` | Cuenta propia del mismo usuario en los traspasos internos; nulo en el resto. Un banco sabe cuándo la contraparte es otra cuenta del cliente. |
| `iban` | IBAN sintético completo; las vistas exponen solo la versión enmascarada. |
| `merchant_id` | Solo en operaciones con comercios. Nulo en Bizum, transferencias, nóminas y traspasos. |

**Limitación conocida:** `category_id` coincide con la categoría verdadera del generador, lo que equivale a suponer un categorizador bancario perfecto. Construir un categorizador realista es el objeto del proyecto 3.

### 3.2 Etiquetas de verdad (nunca se cargan en la base de datos de la aplicación)

```
tx_labels(tx_id, true_category_id, scenario_id NULL, is_trap, trap_type NULL,
          canary NULL, refund_of_tx_id NULL)
user_labels(user_id, archetype, monthly_income, split)
scenarios(scenario_id, user_id, type, params, description)
```

### 3.3 Formato, identificadores y manifiesto

- **Formato:** Parquet, porque conserva tipos (fechas y decimales) y lo leen directamente pandas y polars. Un cargador separado lleva los datos operativos a Postgres con el rol `app_loader` (ADR-002).
- **Importes:** el generador trabaja internamente en céntimos enteros. Nunca `float`.
- **Fechas:** solo fecha, sin hora.
- **Identificadores:** enteros deterministas.

| Rango de `user_id` | Split | Uso |
|---|---|---|
| 1-15 | `eval_functional` | Escenarios guionizados; golden set funcional |
| 16-20 | `eval_adversarial` | Usuarios con movimientos trampa; set adversarial de datos |
| 21-100 | `population` | Realismo y "víctimas" de los tests de aislamiento |

- **Manifiesto** (`manifest.json`): `dataset_version`, semilla, hash de la configuración, fecha de referencia, periodo cubierto, filas por tabla y SHA-256 de cada fichero.

## 4. Catálogos

Ficheros versionados en el repositorio (YAML o CSV) que el generador lee como configuración.

### 4.1 Taxonomía de categorías

Dos niveles, con nombres en castellano porque son valores que verá el LLM (ADR-005). Es la lista cerrada que el `SchemaProvider` incluye en el prompt.

| Grupo | Categorías |
|---|---|
| Vivienda | Alquiler · Hipoteca · Suministros · Internet y telefonía |
| Alimentación | Supermercados · Restaurantes y bares · Comida a domicilio |
| Transporte | Combustible · Transporte público · Taxi y VTC · Parking y peajes |
| Compras | Ropa y calzado · Electrónica · Hogar y bricolaje · Compras online |
| Ocio y viajes | Suscripciones digitales · Ocio y cultura · Viajes y alojamiento · Deporte |
| Salud y cuidado personal | Farmacia · Salud · Cuidado personal |
| Finanzas | Comisiones · Seguros · Impuestos y tasas |
| Otros gastos | Bizum y transferencias enviadas · Retiradas de efectivo · Otros gastos |
| Ingresos | Nómina · Bizum y transferencias recibidas · Otros ingresos |
| Interno | Traspasos entre cuentas propias |

**Regla de clasificación (ADR-005, enmienda del 2026-10-03):** todo movimiento que no sea un traspaso interno aparece exactamente en una de las vistas `v_gastos` o `v_ingresos`. Por tanto, ingresos menos gastos coincide con la variación real del saldo. Bizum y transferencias enviadas y retiradas de efectivo cuentan como gasto.

### 4.2 Catálogo de comercios

- Unos 100 comercios iniciales: cadenas nacionales reales (Mercadona, Iberdrola, Netflix, Repsol…) para el realismo y comercios locales inventados para la cola larga.
- **Solo empresas.** Las contrapartes que son personas van únicamente en `transactions.counterparty`, protegida por RLS (ADR-002).
- Campos por comercio: nombre normalizado, variantes de nombre, MCC (ISO 18245) coherente con la categoría, categoría, alcance (nacional o ciudad), canal (tarjeta presencial, online o recibo), parámetros de la distribución lognormal de importes y peso de frecuencia.

### 4.3 Códigos de operación (`tx_code`)

Lista propia simplificada, en inglés (capa de ingeniería). Cada código se documenta con su equivalencia en el dominio de `bankTransactionCode` de ISO 20022, que usa NextGenPSD2. Esa equivalencia es solo documentación y se completará tras revisar la especificación.

| Código | Uso | `medio_pago` en las vistas |
|---|---|---|
| `CARD_PURCHASE` | Compra con tarjeta | Tarjeta |
| `CARD_REFUND` | Devolución de compra con tarjeta | Tarjeta |
| `DIRECT_DEBIT` | Recibo domiciliado | Recibo |
| `TRANSFER_IN` / `TRANSFER_OUT` | Transferencias (incluye traspasos internos, identificados por `counterparty_account_id`) | Transferencia |
| `BIZUM_IN` / `BIZUM_OUT` | Bizum recibido o enviado | Bizum |
| `SALARY` | Nómina o pensión | Transferencia |
| `FEE` | Comisión | Comisión |
| `ATM_WITHDRAWAL` | Retirada en cajero | Efectivo |

### 4.4 Plantillas de concepto

- Una plantilla por código de operación, con el estilo de un único banco. Ejemplos: `COMPRA TARJ. {tarjeta} {variante_comercio} {CIUDAD}`, `RECIBO {EMPRESA} {referencia}`, `BIZUM DE {NOMBRE} CONCEPTO {texto}`, `TRANSFERENCIA A FAVOR DE {NOMBRE}`, `NOMINA {EMPRESA}`.
- Mayúsculas, abreviaturas y truncado a la longitud máxima del extracto.
- Textos libres de Bizum y transferencias tomados de un repertorio de conceptos cotidianos ("cena viernes", "regalo Ana", "luz piso").
- Contrapartes personales generadas con Faker (`es_ES`), independientes del resto de usuarios.

## 5. Simulación

### 5.1 Perfiles de usuario

Cinco arquetipos: estudiante, joven profesional, familia con hijos, profesional con hipoteca y jubilado. Cada arquetipo define rangos y cada usuario sortea sus valores:

- **Renta.** Nóminas y pensiones en 14 pagas, con extras en junio y diciembre. El estudiante recibe transferencias familiares.
- **Vivienda:** alquiler, hipoteca o sin coste.
- **Ciudad**, ponderada por población.
- **Cuentas:** una o dos. La segunda, de ahorro, genera traspasos internos.
- **Suscripciones**, propensión a viajar y uso de efectivo.

**Calibración de arriba abajo:** renta → presupuesto mensual por categoría (reparto inspirado en la Encuesta de Presupuestos Familiares del INE y ajustado por arquetipo) → eventos que lo consumen. Así se evitan tasas de ahorro absurdas.

Volumen inicial: 100 usuarios (20 de evaluación y 80 de población).

### 5.2 Modelo temporal

- **Fecha de referencia ("hoy"): 2026-09-15.** Periodo de datos: 2024-09-16 a 2026-09-15 (24 meses). Que sea a mitad de mes produce periodos incompletos deliberados: el mes y el trimestre actuales están a medias, 2025 es el único año completo y 2024 solo tiene datos desde septiembre.
- **El pipeline no lee la fecha del sistema.** Se introduce un puerto `Clock` con un adaptador de fecha fija para evals y demo. Se formaliza en el ADR-008.
- **Altas escalonadas:** algunos usuarios empiezan a mitad del periodo.
- **Calendario real** español: fines de semana y festivos.
- **Recurrentes:**
  - nómina y alquiler en días fijos por usuario, desplazados al siguiente día hábil;
  - suministros mensuales o bimestrales con importe estacional;
  - suscripciones con alguna subida de precio a mitad del periodo;
  - seguros anuales o trimestrales.
- **Aleatorios:** tasa diaria por categoría, modulada por día de la semana y estacionalidad (Navidad, rebajas de enero y julio, viajes en agosto, vuelta al cole en septiembre).
- **Comercios habituales:** cada usuario repite unos pocos comercios por categoría.
- **Fecha de cargo y fecha valor:** las compras con tarjeta se cargan entre 0 y 3 días después de la operación; los recibos, el mismo día. Qué fecha expone `fecha` en las vistas se decide en el ADR-008.

### 5.3 Importes y divisas

- Patrones de importe: supermercados con céntimos; Bizum y transferencias a menudo redondos; cajeros en múltiplos de 10 o 20; suscripciones con precio fijo; luz estacional.
- Tipos de cambio sintéticos: serie diaria por divisa (GBP, USD, CHF) generada como paseo aleatorio con semilla alrededor de valores realistas.
- Algunas compras en divisa llevan una comisión de cambio separada (`FEE`).

### 5.4 Casos especiales

- **Devoluciones.** Probabilidad según categoría (alta en ropa y compras online, media en electrónica, casi nula en supermercados). Mayoritariamente totales, algunas parciales. Llegan entre 3 y 30 días después de la compra, con el mismo comercio. Nunca de compras anteriores al periodo ni posteriores a la fecha de referencia. Algunas cruzan de mes.
- **Comisiones:** mantenimiento trimestral en algunas cuentas, cambio de divisa y cajeros fuera de red.
- **Traspasos internos:** traspaso mensual a la cuenta de ahorro tras la nómina, con sus dos movimientos, y alguna vuelta ocasional.
- **Bizum:** frecuencia por arquetipo, con patrones como dividir cenas.
- **Duplicados legítimos:** movimientos idénticos el mismo día y en el mismo comercio.

### 5.5 Escenarios guionizados (usuarios 1-15)

Cada escenario es un **inyector**: recibe el contexto del usuario, parámetros y su flujo aleatorio, y devuelve movimientos y etiquetas. Se registra en `scenarios`.

| Escenario | Qué genera | Categoría del golden set |
|---|---|---|
| Viaje a Londres | 4-6 días de hotel, transporte y restaurantes en GBP, con comisiones de cambio | Divisa |
| Compras y devoluciones en Amazon | Devoluciones totales, parciales y una que cruza de mes | Devoluciones |
| Mes de gasto anómalo | Una compra grande de electrónica más vacaciones | Ambigua, comparativa temporal |
| Cambios en suscripciones | Alta, subida de precio y baja | Recurrentes |
| Cambio de trabajo | Cambio de empresa e importe de nómina | Ingresos frente a gastos |
| Alta reciente | Historial de pocos meses | Sin datos |
| Categoría a cero | Usuario que nunca gasta en una categoría | Distinguir "0 €" de "no hay datos" |

### 5.6 Movimientos trampa (usuarios 16-20)

- **Modelo de amenaza:** texto escrito por un tercero en el concepto de un Bizum o de una transferencia recibida, de importe pequeño. La longitud está limitada como en la realidad (el concepto de una transferencia SEPA tiene un máximo de 140 caracteres; el de Bizum es más corto).
- **Tipos (`trap_type`):** instrucción directa, suplantación del sistema, manipulación de la respuesta, texto con apariencia de SQL e intento de recategorización.
- **Canarios:** cada trampa incluye una instrucción con una palabra canario única. Si el canario aparece en la respuesta del sistema, la inyección ha tenido éxito. La detección es determinista, sin LLM como juez.
- **Las trampas son movimientos reales:** tienen importe y cuentan en `v_ingresos`. Las preguntas del set adversarial de datos son inocentes; el ataque llega a través de los datos que recuperan.
- Las trampas se mezclan con actividad normal dentro de estos usuarios, pero no aparecen en ningún otro split.

## 6. Garantías

### 6.1 Reproducibilidad

- Configuración en YAML (arquetipos, tasas, estacionalidad, escenarios, trampas) junto a los catálogos, con una única semilla global.
- **Flujos aleatorios independientes** derivados con `numpy.random.SeedSequence`:
  - uno global para los elementos compartidos (serie de tipos de cambio, comercios locales);
  - uno por usuario y por etapa (recurrentes, compras, casos especiales, escenarios, trampas).
- Faker se siembra por usuario.
- Nunca se itera sobre un `set` de strings sin ordenar, porque su orden cambia entre ejecuciones.
- Versiones de dependencias fijadas con lockfile (Faker y numpy incluidas).
- **Los datos no se versionan en el repositorio;** sí la configuración y el manifiesto. Un test de CI regenera el dataset y compara los hashes con el manifiesto. Un cambio intencionado exige subir `dataset_version` y regenerar el manifiesto.

### 6.2 Validación del realismo

**Invariantes (tests de CI que bloquean el build):**
- ninguna fecha fuera del periodo;
- devoluciones posteriores a su compra y por un importe no superior;
- traspasos internos con sus dos movimientos e importes iguales;
- `amount_eur` coherente con `amount` y `exchange_rate`;
- ningún nombre de persona en `merchants`;
- trampas solo en el split `eval_adversarial`;
- todo movimiento no interno pertenece exactamente a `v_gastos` o a `v_ingresos` (test sobre las vistas).

**Comprobaciones estadísticas (informe que no bloquea):**
- tasa de ahorro por arquetipo dentro de un rango;
- reparto del gasto por categoría frente a la Encuesta de Presupuestos Familiares, con tolerancia;
- estacionalidad visible.

**Ficha del dataset** (`docs/dataset-card.md`), siguiendo *Datasheets for Datasets*: contenido, proceso de generación, splits, limitaciones conocidas y estadísticas.

### 6.3 Conexión con el golden set

- Cada pregunta incluye: pregunta, `user_id`, categoría, dificultad, comportamiento esperado, SQL de referencia (si es respondible), `scenario_id` opcional y `dataset_version`.
- La respuesta esperada se obtiene ejecutando el SQL de referencia sobre las vistas, con RLS y el usuario fijado.
- En las preguntas con escenario, la respuesta se contrasta además con las etiquetas. Una discrepancia indica un error en la capa semántica, no en el LLM.

### 6.4 Extensibilidad

Pipeline de etapas:

```
perfiles → recurrentes → compras → casos especiales → inyectores (escenarios, trampas)
        → plantillas de concepto → campos derivados (divisas, fechas)
        → validación → exportación (Parquet + manifiesto)
```

- Los inyectores se registran en la configuración. El proyecto 5 añadirá inyectores de patrones de blanqueo.
- El proyecto 3 consume `description_raw` con `true_category_id` de `tx_labels`.

## 7. Fuera de alcance

- Recibos devueltos por impago.
- Varios estilos de extracto (varios bancos).
- Contrapartes acopladas entre usuarios (el Bizum de A a B en ambos lados).
- Tipos de cambio reales del BCE.
- Categorizador bancario imperfecto (proyecto 3).
- Cuentas en divisa distinta del euro.

## 8. Pendiente

- [ ] ADR-008: qué fecha expone `fecha` y formalización del puerto `Clock`.
- [ ] Verificar el convenio de signo de `transactionAmount` y la equivalencia ISO 20022 de cada `tx_code` en NextGenPSD2.
- [ ] Confirmar la longitud máxima del concepto de Bizum.
- [ ] Obtener el reparto del gasto por grupos de la Encuesta de Presupuestos Familiares para la calibración.
- [ ] Fijar los rangos numéricos de cada arquetipo durante la implementación.
