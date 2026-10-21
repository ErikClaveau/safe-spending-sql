# ADR-001: PostgreSQL como único motor de base de datos

**Estado:** Aceptado
**Fecha:** 2026-10-01
**Decide:** Erik Claveau
**Relacionados:** ADR-002 (aislamiento entre usuarios), ADR-005 (qué ve el LLM: tablas o vistas)

## Contexto

El asistente responde preguntas sobre los gastos bancarios de un usuario ejecutando SQL generado por un LLM. Ese SQL no es de confianza: el modelo puede equivocarse o ser manipulado, tanto por la pregunta del usuario como por texto inyectado en los conceptos de los movimientos. El requisito más estricto del proyecto es que la tasa de fuga entre usuarios sea **0** en el set adversarial, y la primera capa de defensa debe aguantar "aunque falle todo lo demás".

Fuerzas en juego:

- **Volumen pequeño.** 50-200 usuarios sintéticos × 12-24 meses dan menos de ~500.000 movimientos. El rendimiento analítico no es un factor diferencial.
- **Aislamiento impuesto por el motor.** La garantía de aislamiento no puede depender de que el SQL generado contenga el filtro correcto.
- **Evals representativas.** La métrica principal (execution accuracy) solo es válida si se mide en el mismo motor y dialecto que se usaría en producción.
- **Restricciones del proyecto.** 6 semanas con 5-10 h/semana. Docker Compose y GitHub Actions ya están decididos.
- **Objetivo de portfolio.** Demostrar prácticas creíbles para entornos bancarios regulados.

## Decisión

Se usa **PostgreSQL** en todos los entornos (local, CI y evaluación), con Row-Level Security como mecanismo base de aislamiento. La versión mínima es la 15, necesaria para `security_invoker` en vistas. Se fija la versión exacta en la imagen de Docker Compose.

**DuckDB se descarta**, también como adaptador de tests. El puerto `QueryExecutor` tendrá un único adaptador real (Postgres). Los tests unitarios de los componentes que no dependen del motor usan dobles en memoria, no otra base de datos.

## Opciones consideradas

### Opción A: PostgreSQL

| Dimensión | Valoración |
|---|---|
| Aislamiento | RLS nativo: el motor aplica las políticas a cualquier consulta, independientemente de su texto |
| Control de acceso | Roles, `GRANT`/`REVOKE`, transacciones de solo lectura y `statement_timeout` por rol |
| Realismo | Alto; estándar habitual en backends de producción y en banca |
| Complejidad | Media: servicio adicional en Compose y CI, y trampas conocidas de RLS |
| Coste | Nulo (imagen oficial, self-hosted) |

**Pros**
- Cubre de forma nativa las capas 1, 2 y 4 de la defensa (RLS, rol de solo lectura, límites de ejecución).
- Las evals y los tests adversariales se ejecutan contra el mismo motor que impone el aislamiento.
- Es la tecnología que más valor aporta en entornos profesionales y amplía el conocimiento de Postgres que ya uso en el trabajo.

**Contras**
- Curva de aprendizaje en roles, políticas, variables de sesión y seguridad de vistas.
- Trampas que pueden anular RLS si se configuran mal: el propietario de la tabla se salta las políticas salvo con `FORCE ROW LEVEL SECURITY`, las vistas se ejecutan con permisos del propietario salvo con `security_invoker`, y `SET` sin `LOCAL` contamina conexiones del pool.
- Los tests de integración son más lentos que con un motor embebido.

### Opción B: DuckDB

| Dimensión | Valoración |
|---|---|
| Aislamiento | Sin RLS nativo ni modelo de roles; el aislamiento tendría que imponerse reescribiendo el SQL |
| Control de acceso | Limitado; motor embebido sin usuarios |
| Realismo | Bajo para un sistema transaccional multiusuario |
| Complejidad | Baja: embebido, sin servicio, fichero único reproducible |
| Coste | Nulo |

**Pros**
- Cero operación: ideal para prototipos y CI rápida.
- Muy rápido en consultas analíticas.

**Contras**
- El aislamiento dependería por completo de inyectar filtros con sqlglot sobre SQL generado por un modelo bajo ataque. Una CTE, subconsulta o `UNION` mal cubierta supone una fuga.
- Al ejecutarse dentro del proceso de la aplicación, el SQL generado tendría acceso a funciones de lectura de ficheros, `ATTACH` y extensiones con red, salvo que se desactiven explícitamente.
- No permite ejecutar el test obligatorio de RLS ni un set adversarial representativo.

### Opción C: PostgreSQL en producción + DuckDB para tests y evals

**Descartada.** Las diferencias de dialecto (fechas, intervalos, casts, redondeo) introducirían ruido en la execution accuracy, y las pruebas de aislamiento no se podrían ejecutar en DuckDB. Mantener dos adaptadores consumiría tiempo sin aportar señal fiable.

## Análisis de trade-offs

El factor decisivo es dónde reside la garantía de aislamiento. Con PostgreSQL reside en el motor, y el SQL del LLM se trata como no confiable sin que eso comprometa los datos de otros usuarios. Con DuckDB reside en la corrección de un reescritor de SQL, que es una buena segunda capa pero una mala capa única.

La simplicidad operativa de DuckDB es su ventaja real, pero aquí pesa poco: Docker Compose ya está decidido y un Postgres en GitHub Actions es un service container estándar. El coste efectivo de PostgreSQL es aprender a configurar RLS correctamente, y ese aprendizaje es uno de los objetivos del proyecto.

## Consecuencias

**Más fácil**
- Diseñar el aislamiento como propiedad del motor (ADR-002) en lugar de como transformación del SQL.
- Medir execution accuracy y tasa de fuga en condiciones equivalentes a producción.
- Defender el diseño en una entrevista para un entorno regulado.

**Más difícil**
- Configurar y probar correctamente roles, políticas, variables de sesión y vistas.
- Los tests de integración requieren levantar Postgres (Compose en local, service container en CI).

**A revisar**
- El ADR-002 queda condicionado: RLS es la garantía principal y la reescritura con sqlglot, si se añade, es defensa en profundidad.
- El ADR-005 debe asumir vistas con `security_invoker = true` para que la capa semántica respete RLS.
- El modelo de datos puede necesitar `user_id` desnormalizado en `transactions` para simplificar las políticas. Se decide en el ADR-002.
- Esta decisión solo se reabriría si el proyecto necesitara análisis sobre volúmenes que PostgreSQL no gestione con holgura, algo fuera del alcance previsto.

## Próximos pasos

1. [ ] Añadir PostgreSQL a `docker-compose.yml` con versión fijada (≥ 15).
2. [x] Laboratorio de RLS (hecho el 2026-10-05, ver ADR-002): dos usuarios, una política, e intentos deliberados de romperla (propietario, vista sin `security_invoker`, `SET` sin `LOCAL`, variable sin fijar).
3. [ ] Redactar el ADR-002 a partir de los resultados del laboratorio.
4. [ ] Configurar el service container de Postgres en GitHub Actions.
5. [ ] Eliminar DuckDB de la tabla de puertos y del stack en la documentación del proyecto.
