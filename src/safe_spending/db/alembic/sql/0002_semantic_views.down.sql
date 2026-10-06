DROP VIEW IF EXISTS v_ingresos, v_gastos, v_movimientos;
DROP FUNCTION IF EXISTS medio_pago_de(text);
ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_sign_matches_tx_code;
