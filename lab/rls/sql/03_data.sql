-- Toy data (run as `app_loader`, which has BYPASSRLS).
-- Three users with distinct, easy-to-recognise rows: user 3 has a single account and
-- two movements, so any leak of another user's rows changes a count visibly.

INSERT INTO users (user_id, name) VALUES
    (1, 'Ana'),
    (2, 'Beto'),
    (3, 'Carla');

INSERT INTO accounts (account_id, user_id, iban) VALUES
    (10, 1, 'ES0000000000000000000010'),
    (11, 1, 'ES0000000000000000000011'),
    (20, 2, 'ES0000000000000000000020'),
    (30, 3, 'ES0000000000000000000030');

INSERT INTO transactions (tx_id, account_id, user_id, booking_date, amount, description) VALUES
    (1,  10, 1, '2026-09-01',  -42.50, 'Supermercado A'),
    (2,  10, 1, '2026-09-02', 1500.00, 'Nomina A'),
    (3,  11, 1, '2026-09-03',  -10.00, 'Cafeteria A'),
    (4,  20, 2, '2026-09-01',  -99.99, 'Gimnasio B'),
    (5,  20, 2, '2026-09-05', 2000.00, 'Nomina B'),
    (6,  30, 3, '2026-09-04',  -15.00, 'Cine C'),
    (7,  30, 3, '2026-09-06', 1200.00, 'Nomina C');
