# ADR-002: Aislamiento entre usuarios basado exclusivamente en Row-Level Security

**Estado:** Propuesto (pasa a Aceptado cuando el laboratorio de RLS valide los puntos de la sección "Criterios de aceptación")
**Fecha:** 2026-10-01
**Decide:** Erik Claveau
**Relacionados:** ADR-001 (PostgreSQL como único motor), ADR-005 (qué ve el LLM: tablas o vistas)

## Contexto

El asistente ejecuta SQL generado por un LLM sobre una base de datos con los movimientos de todos los usuarios. Ese SQL no es de confianza: el modelo puede equivocarse o ser manipulado por la pregunta del usuario o por texto inyectado en los conceptos de los movimientos. El requisito es **0 fugas entre usuarios** en el set adversarial, y el aislamiento debe mantenerse aunque fallen las demás capas (clasificación, prompt y validación estática).

Tras el ADR-001, PostgreSQL es el único motor y Row-Level Security (RLS) está disponible de forma nativa. Queda por decidir:

1. si RLS es el único mecanismo de aislamiento o se combina con reescritura del SQL generado;
2. cómo llega la identidad del usuario hasta las políticas;
3. qué cambios necesita el modelo de datos;
4. qué roles de base de datos existen y con qué permisos;
5. cómo se verifica que el aislamiento sigue configurado correctamente.

## Decisión

### Mecanismo

El aislamiento se basa **exclusivamente en RLS**. El SQL generado por el LLM **no se reescribe** para añadir filtros de usuario. La defensa en profundidad la aportan capas independientes: el LLM no conoce el `user_id`, el rol de la aplicación es de solo lectura y sqlglot aplica una allowlist de objetos. A esto se suma una verificación automática de la configuración de RLS en CI.

### Propagación de la identidad

1. La capa de autenticación de la API resuelve el `user_id`. Nunca se toma de la pregunta del usuario ni de la salida del LLM. En este proyecto la autenticación es simulada (fuera de alcance), pero el contrato es el mismo.
2. El LLM genera el SQL sin conocer al usuario. La columna `user_id` no aparece en el esquema que se le muestra.
3. El executor, por cada consulta:
   - abre una transacción explícita de solo lectura;
   - fija la identidad con `SELECT set_config('app.user_id', %s, true)`, con el id como parámetro y nunca interpolado (el `true` equivale a `SET LOCAL`, así que la variable muere con la transacción y no contamina la conexión al volver al pool);
   - comprueba que la variable ha quedado fijada antes de ejecutar;
   - ejecuta el SQL generado tal cual y cierra la transacción.

### Políticas

Todas las tablas con datos de usuario usan la misma forma de política:

```sql
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions FORCE ROW LEVEL SECURITY;

CREATE POLICY aislamiento_usuario ON transactions
  FOR SELECT TO app_reader
  USING (user_id = NULLIF(current_setting('app.user_id', true), '')::int);
```

- **Tablas con RLS:** `users`, `accounts`, `transactions`.
- **Tablas sin RLS:** `merchants` y `categories`, que son catálogos compartidos sin datos personales.
- **Fallo cerrado:** si la variable no está fijada, `NULLIF` la convierte en `NULL`, la comparación nunca es cierta y la consulta devuelve 0 filas. La comprobación previa del executor evita que un bug se manifieste como un falso "no tienes movimientos".
- **`FORCE ROW LEVEL SECURITY`** hace que ni siquiera el propietario de las tablas se salte las políticas.

### Modelo de datos

- `transactions` incorpora `user_id` desnormalizado, para que su política no dependa de un join con `accounts`.
- La coherencia se garantiza en la base de datos con una clave foránea compuesta:

```sql
ALTER TABLE accounts ADD UNIQUE (account_id, user_id);
ALTER TABLE transactions
  ADD FOREIGN KEY (account_id, user_id) REFERENCES accounts (account_id, user_id);
```

- `merchants` solo contiene empresas. Las contrapartes que son personas físicas (Bizum, transferencias entre particulares) se guardan únicamente en `transactions.counterparty`, que está protegida por RLS. Esta es una regla obligatoria para el generador de datos.

### Roles de base de datos

| Rol | Uso | Permisos |
|---|---|---|
| `app_owner` | Migraciones; propietario del esquema | DDL. No lo usa la API. |
| `app_loader` | Carga de datos sintéticos | `INSERT` y `BYPASSRLS`. Solo scripts de carga, nunca la API. |
| `app_reader` | Único rol de la API | Solo `SELECT`; sin `BYPASSRLS`; `default_transaction_read_only = on` y `statement_timeout` fijados en el propio rol. |

Todos los usuarios finales comparten `app_reader` y se distinguen por la variable de sesión, no por roles de Postgres.

### Verificación continua

Un **test de configuración** en CI consulta el catálogo de Postgres y falla si:

- alguna tabla con datos de usuario no tiene RLS activada y forzada (`pg_class.relrowsecurity`, `relforcerowsecurity`);
- alguna de esas tablas no tiene política para `app_reader` (`pg_policies`);
- alguna vista de la capa semántica no tiene `security_invoker` (`pg_class.reloptions`);
- `app_reader` tiene `BYPASSRLS` o es superusuario (`pg_roles`).

## Opciones consideradas

### Opción A: RLS como único mecanismo + verificación de configuración (elegida)

**Pros**
- La garantía reside en el motor y no depende del texto del SQL generado.
- Una sola implementación del filtro: no hay lógica duplicada que pueda divergir.
- El LLM nunca necesita conocer ni manejar el `user_id`.
- El riesgo principal (una configuración incorrecta de RLS) se detecta automáticamente en CI.

**Contras**
- Si RLS se configura mal y el test de configuración no cubre el caso, no hay una segunda barrera específica de aislamiento.
- Requiere dominar las trampas de RLS: propietario, vistas, variables de sesión con pool de conexiones.

### Opción B: RLS + reescritura del SQL con sqlglot como segunda capa

**Pros**
- Segunda barrera independiente ante una configuración incorrecta de RLS.

**Contras**
- Reescribir correctamente CTEs, subconsultas, joins, `UNION` y alias es complejo, y un caso no cubierto deja la capa sin efecto.
- Duplica la lógica de aislamiento en dos sitios que pueden divergir.
- Obliga a reintroducir el `user_id` en el camino del SQL generado.
- Introduce fallos de ejecución que contaminan la execution accuracy.

### Opción C: Solo reescritura del SQL

**Descartada.** Tras el ADR-001 no tiene sentido renunciar a una garantía que impone el motor para depender de un parser que procesa SQL generado bajo ataque.

## Análisis de trade-offs

La opción B protege contra un error concreto: RLS mal configurada. Pero lo hace con un mecanismo frágil y costoso, y desplaza el riesgo en lugar de eliminarlo. La opción A ataca ese mismo error en su origen: comprueba de forma determinista, en cada build, que la configuración que impone el aislamiento sigue en su sitio. El resto de capas (LLM sin identidad, rol de solo lectura, allowlist de sqlglot, timeouts) aportan defensa en profundidad sin repetir el filtro.

## Consecuencias

**Más fácil**
- Escribir y razonar sobre el pipeline de generación: el SQL nunca contiene lógica de aislamiento.
- Auditar el aislamiento: todas las políticas tienen la misma forma y su presencia se verifica en CI.

**Más difícil**
- El executor debe gestionar con rigor transacciones y variables de sesión.
- Cada tabla nueva con datos de usuario necesita `user_id`, RLS forzada y política. El test de configuración debe incluirla.

**A revisar**
- **ADR-005:** con `security_invoker`, Postgres comprueba los permisos de las tablas base contra `app_reader`, que por tanto necesita `SELECT` sobre ellas. Que el LLM solo use vistas no lo pueden garantizar los `GRANT`; debe hacerlo la allowlist de sqlglot.
- **Generador de datos:** respetar la regla de contrapartes personales fuera de `merchants`.

## Tests asociados

1. **RLS directo, sin LLM:** consultas escritas a mano con la variable fijada a otro usuario devuelven 0 filas de los demás.
2. **Fallo cerrado:** una consulta sin fijar `app.user_id` devuelve 0 filas.
3. **Contaminación del pool:** tras una consulta del usuario A, una consulta en la misma conexión sin fijar la variable devuelve 0 filas.
4. **Configuración:** las comprobaciones de catálogo descritas en "Verificación continua".
5. **Set adversarial:** cualquier fila de otro usuario rompe el build.

## Criterios de aceptación (laboratorio de RLS)

- [ ] Una política con `FORCE` impide al propietario ver filas sin la variable fijada.
- [ ] Una vista sin `security_invoker` se comporta como se espera y una con `security_invoker` respeta RLS.
- [ ] `set_config(..., true)` no persiste tras el fin de la transacción en una conexión reutilizada del pool.
- [ ] Una variable vacía o ausente produce 0 filas.
- [ ] `app_reader` no puede escribir aunque intente desactivar el modo de solo lectura dentro de la transacción. Si puede hacerlo, el bloqueo depende de los `GRANT`; documentarlo.
