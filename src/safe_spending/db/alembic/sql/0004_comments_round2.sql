-- Round 2 of the golden-set improvement (ADR-003, ADR-010): a trip abroad has no dates in the data, but its
-- payments are the ones in another currency, so the assistant should assume that instead of asking for dates.
-- Comments only; no object changes. Runs as app_owner.

COMMENT ON COLUMN v_gastos.divisa_original IS
    'Código ISO de la divisa original de la operación (EUR, GBP, USD...). Todas las cuentas son en euros. Un viaje al extranjero se reconoce por los pagos con divisa_original distinta de EUR (Londres = GBP): no hace falta preguntar las fechas, filtra por la divisa y di en el mensaje que has interpretado así el viaje. La comisión de cambio de cada pago está en euros, aparte (ver concepto).';

COMMENT ON COLUMN v_movimientos.divisa_original IS
    'Código ISO de la divisa original de la operación (EUR, GBP, USD...). Todas las cuentas son en euros. Un viaje al extranjero se reconoce por los pagos con divisa_original distinta de EUR (Londres = GBP): no hace falta preguntar las fechas, filtra por la divisa y di en el mensaje que has interpretado así el viaje.';
