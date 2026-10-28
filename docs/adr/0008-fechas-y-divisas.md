# ADR-008: Fechas y divisas

**Estado:** Aceptado
**Fecha:** 2026-10-28
**Decide:** Erik Claveau
**Relacionados:** ADR-005 (capa semántica), ADR-004 (modelo), `docs/generator-design.md`

## Contexto

Tres cosas tienen que dar el mismo resultado hoy y dentro de un mes, para que las evals se puedan comparar y la demo sea reproducible:

- Qué es «hoy» para una pregunta como «¿cuánto gasté este mes?».
- Qué fecha de un movimiento ve el modelo, cuando una compra con tarjeta se cobra entre 0 y 3 días después de hacerse.
- Cómo se pasa a euros un pago en libras, y con qué tipo de cambio.

Sin una regla, la misma pregunta daría otra cifra según el día en que se ejecute, la fecha elegida o el tipo aplicado.

## Decisión

**Hoy.** La fecha de referencia está congelada (2026-09-15) y entra por el puerto `Clock`: `FixedClock` en evals y demo, `SystemClock` en un despliegue real. Nada de `src/` lee la fecha del sistema salvo `SystemClock`. El asistente recibe «hoy» en el prompt (del generador de SQL y del sintetizador) y escribe las fechas él mismo. El validador **rechaza `now()` y `current_date`** (ADR-005, lista blanca de funciones), de modo que un SQL nunca depende del reloj de la base de datos.

**Solo fechas.** Sin hora y sin zona horaria. Los periodos se escriben como `fecha >= '2026-03-01' AND fecha < '2026-04-01'` (el día siguiente al último).

**La fecha expuesta es la de cargo.** `fecha`, en las tres vistas, es `booking_date`: la del extracto (fecha de abono en `v_ingresos`). La fecha valor (`value_date`) existe en la tabla base y **no** se expone.

**Euros.** Todas las cuentas están en euros. Un pago en otra divisa conserva su importe y su divisa originales (`importe_original` y `divisa_original`; `gasto_original` en `v_gastos`) y `importe_eur` se calcula al generar el movimiento:

- `amount_eur = amount / tipo`, con el tipo en **unidades de divisa por 1 EUR**, aplicado en la **fecha de la operación** (`value_date`), redondeado half-even a céntimos (`money.convert_to_eur_cents`).
- La comisión de cambio es un movimiento `FEE` aparte, en euros y sin comercio (1,75 % del importe, mínimo 0,50 €).
- Los tipos son **sintéticos**: una serie diaria por divisa, paseo aleatorio con semilla y flujo propio por divisa, de modo que no depende de las demás ni de la fecha de fin. No se usan tipos reales del BCE.
- El tipo aplicado no se expone en las vistas: el asistente lee `importe_eur` y no recalcula conversiones.

## Opciones consideradas

| Pregunta | Opciones | Elegida |
|---|---|---|
| «Hoy» | Reloj del sistema · puerto `Clock` con fecha fija | `Clock` |
| Hora y zona | Marcas de tiempo con zona · solo fechas | Solo fechas |
| Fecha expuesta | Cargo · valor · las dos | Cargo |
| Tipo de cambio | El de la fecha de la operación · el del cargo · el real del BCE | El de la operación, sintético |

- **Reloj del sistema:** descartado porque cada ejecución sería otra medición y el golden dejaría de ser estable.
- **Marcas de tiempo con zona:** el diseño del generador usa solo fechas y ninguna pregunta del golden necesita la hora; añadir zona abriría errores de medianoche sin aportar nada.
- **Fecha de cargo:** es la que aparece en un extracto, y la que `v_gastos` y `v_ingresos` usan para agrupar por mes.
- **Las dos fechas:** más completo, pero obliga a que el modelo elija entre dos columnas casi iguales; se deja para cuando una pregunta lo pida.
- **Tipo real del BCE:** descartado por reproducibilidad y por estar fuera de alcance en esta fase.

## Consecuencias

**Más fácil**
- Misma fecha de referencia, mismos resultados: las evals se comparan entre ejecuciones y el golden es estable.
- Sin zonas horarias ni horas, hay una fuente menos de ambigüedad. La verificación numérica compara las fechas de una respuesta por día, mes y año (ADR-005).
- El modelo no puede depender del reloj de la base de datos.

**Más difícil**
- **Una compra se cuenta en el mes de su cargo.** Una compra del 30 de agosto cargada el 1 de septiembre suma en septiembre; el asistente no puede responder «qué compré el día X» por fecha de operación. El golden calcula su verdad con la fecha de cargo, así que no hay contradicción interna, pero la limitación existe y no se ha medido cuánto afecta.
- No se puede auditar la conversión desde el asistente: ni el tipo ni la fecha valor están en las vistas.
- Con «hoy» fijo a mitad de mes, el mes y el trimestre en curso están a medias a propósito (sirven para probar periodos incompletos). La demo debe decir que «hoy» es el 15 de septiembre de 2026.

**A revisar**
- Si una pregunta real necesita «cuándo hice la compra», exponer una columna `fecha_operacion` (migración, `COMMENT ON`, diccionario de datos y golden).
- `SystemClock` usa `date.today()`, la hora local del servidor. En un despliegue real habría que fijar la zona (Europe/Madrid) para que «hoy» no cambie de día a medianoche según dónde corra.

## Próximos pasos

1. [x] Puerto `Clock` con `FixedClock` y `SystemClock`.
2. [x] Conversión a euros con tipo por 1 EUR, fecha de la operación y redondeo half-even (`tests/generator/test_fx.py`).
3. [x] Validador sin `now()` ni `current_date`.
4. [ ] Decidir si se expone `fecha_operacion` cuando el golden crezca a 150-200 preguntas.
