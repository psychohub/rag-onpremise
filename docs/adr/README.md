# Architecture Decision Records

Este directorio guarda las decisiones de diseño del repositorio que
cuestan más de explicar una vez.

## Qué es un ADR en este repo

Un ADR registra **una decisión y por qué se tomó**, incluyendo las
alternativas que se descartaron y lo que se pierde con la opción elegida.
No es documentación de uso ni especificación de implementación.

Consecuencia importante para este repositorio: **un ADR describe una
decisión, no necesariamente código que ya exista.** El repo es material
de referencia, y parte de lo que se decide está por delante de lo que
está implementado. Cada ADR debe decir explícitamente qué parte de la
decisión ya está en el código y qué parte es diseño pendiente.

## Convención: los ADR no se editan

Un ADR aceptado no se reescribe. Si la decisión cambia, se escribe uno
nuevo que **supersede** al anterior:

- El ADR nuevo indica en su encabezado a cuál supersede.
- El ADR viejo cambia su `Status` a `Superseded by ADR-NNN` y no se
  toca en nada más.

El motivo es el mismo que llevó a resolver la errata de
`threshold-safety.md` por adición y no por reescritura: el registro de
lo que se decidió en su momento tiene valor incluso cuando la decisión
ya no vale.

Excepción única: correcciones de un ADR que todavía no se ha commiteado,
o erratas factuales dentro del mismo ADR marcadas como tales.

Valores de `Status`: `Proposed`, `Accepted`, `Superseded by ADR-NNN`,
`Rejected`.

## Índice

| ADR | Título | Estado | Origen |
|---|---|---|---|
| [001](001-cache-partitioning-by-authorization-scope.md) | Cache partitioning by authorization scope | Accepted | Hilo de dev.to (Ivan Rossouw) |

## Documentos relacionados

- [`docs/experiments/threshold-safety.md`](../experiments/threshold-safety.md)
  — reporte del experimento que llevó a deshabilitar el caché semántico
  por defecto. Es un reporte experimental, no un ADR: registra una
  medición, no una decisión de diseño.

---

*Este es un proyecto personal de código abierto. No describe ningún
deployment institucional ni utiliza datos de sistemas en producción.*
