# PRD: Asistente RAG de contratos marítimos

Cliente ficticio: Naviera Portecho. Versión MVP. Este documento recoge los requisitos funcionales y
marca cuáles no están implementados. Cómo está construido: [`ARCHITECTURE.md`](ARCHITECTURE.md).
Por qué se eligió cada cosa: [`../DECISIONS.md`](../DECISIONS.md).

## 1. Objetivo

El equipo legal y de operaciones de Naviera Portecho guarda cientos de contratos con proveedores en
PDF, con tablas de tarifas y cláusulas de penalización por demora, y pierde horas buscando
condiciones concretas. El asistente permite:

1. Subir contratos, uno o varios, y procesarlos en segundo plano.
2. Preguntar en lenguaje natural.
3. Recibir respuestas que citan documento, página y fragmento.
4. Recibir "No hay evidencia suficiente" cuando los contratos no respaldan la respuesta.

## 2. Actores

- **Analista legal u operativo:** sube contratos, consulta condiciones y verifica citas.
- **Worker:** procesa cada documento (parseo, segmentación, embeddings, persistencia).
- **Desarrollador:** prueba el sistema con el proveedor mock, sin claves, o con Gemini u OpenAI.

## Épica 1: Ingesta y gestión de contratos

### US-1.1 Subir contratos en PDF
Como analista quiero subir uno o varios PDFs a la vez para incorporarlos sin hacerlo de uno en uno.

- Solo se aceptan `.pdf` cuyo contenido empiece por `%PDF-`; el tamaño máximo es configurable
  (25 MB por defecto). Un archivo rechazado devuelve un error legible.
- `POST /api/v1/documents/upload` sube uno. `POST /api/v1/documents/upload-batch` sube varios y
  responde el resultado de cada archivo; un archivo inválido no bloquea al resto.
- La respuesta no espera al procesamiento: cada documento queda `pending`.

### US-1.2 Consultar el estado de un documento
Como usuario quiero saber cuándo un contrato está listo, o por qué falló.

- Estados: `pending`, `processing`, `ready` y `failed`. En `failed`, `error_detail` explica el motivo.
- `GET /api/v1/documents/{id}` devuelve estado, nombre, tamaño, número de fragmentos y fecha de
  creación.
- Ningún documento queda en un estado intermedio sin explicación: un reaper marca `failed` los que
  llevan demasiado tiempo en `processing`.

### US-1.3 Listar contratos
Como analista quiero ver qué contratos forman parte de la base de conocimiento.

- `GET /api/v1/documents` devuelve la lista, más recientes primero, con filtro opcional `?status=`.
- No implementado: paginación (`skip`, `limit`) y número de páginas por documento.

## Épica 2: Procesamiento asíncrono e idempotencia

### US-2.1 Pipeline en segundo plano
- Cada subida encola una tarea de Celery con Redis como broker, después de que la transacción hizo
  commit.
- Parseo con pdfplumber, que conserva las tablas como Markdown y el número de página (ver
  `DECISIONS.md` §1).
- Cada fragmento guarda `document_id`, `page_number`, `chunk_index` y posición de inicio y fin.
- Cada fragmento tiene un embedding en PostgreSQL con pgvector.

### US-2.2 Idempotencia y reintentos seguros
Como administrador quiero que subir el mismo PDF dos veces, o que un worker muera a mitad, no deje
duplicados ni datos a medias.

- El mismo contenido (SHA-256) devuelve el documento existente. Si estaba `failed`, se encola de nuevo.
- Redelivery de una tarea sobre un documento `ready`: no hace nada.
- Una tarea que falla borra los fragmentos del documento y lo deja `failed`; reintentarla no duplica.
- Un worker muerto sin manejar el error se recupera por reentrega de Redis (`acks_late`) o lo cierra
  el reaper.

### US-2.3 Documentos anómalos
- PDF con contraseña: `failed` con "El documento está protegido por contraseña".
- PDF corrupto o vacío: `failed` con "Archivo corrupto o sin páginas legibles".
- Un error en un documento no afecta a los demás de la cola.

## Épica 3: Consulta con validación de citas

### US-3.1 Recuperación
- La pregunta se vectoriza con el mismo modelo que los fragmentos.
- Búsqueda por distancia coseno en pgvector, solo en documentos `ready`, con `top_k` configurable.
- Cada fragmento recuperado incluye `chunk_id`, `document_id`, nombre del documento, página y texto.

### US-3.2 Respuesta estructurada y citas verificadas
- La salida del LLM se valida contra un esquema Pydantic: `answer`, `citations` y
  `has_sufficient_evidence`.
- Cada cita debe pertenecer a un fragmento recuperado y su texto debe aparecer en él; las demás se
  descartan. Si todas se descartan, la respuesta se marca sin evidencia suficiente.

### US-3.3 Abstención
- Los fragmentos bajo el umbral de similitud (`RAG_SIMILARITY_THRESHOLD`) no llegan al LLM.
- Sin evidencia: `has_sufficient_evidence` es `false`, `citations` va vacío y la respuesta indica
  "No hay evidencia suficiente en los contratos disponibles para responder a esta pregunta."
- Contratos contradictorios: el prompt pide exponer ambas posturas citando cada documento. No hay
  una validación automática de esto.

## Épica 4: Frontend (React + TypeScript)

### US-4.1 Subida y estado
- Zona de arrastre para uno o varios PDFs, con validación de tipo y tamaño.
- El estado se actualiza en vivo con eventos del servidor (SSE, `GET /api/v1/documents/events`). Si la
  conexión cae, la interfaz vuelve al polling cada 2 s hasta que todos los documentos tienen un estado
  final; con la conexión abierta mantiene además un sondeo lento de 30 s como respaldo.

### US-4.2 Catálogo
- Tabla con nombre, tamaño, fragmentos, fecha y estado, con filtro por estado en la URL.
- Los documentos `failed` muestran el motivo.

### US-4.3 Chat con citas
- La respuesta llega en streaming (SSE) y va seguida de las citas verificadas.
- Al abrir una cita, un panel lateral muestra el fragmento original completo con el texto citado
  resaltado y un enlace al PDF en la página citada.
- Si no hay evidencia suficiente, la interfaz lo señala.

## Épica 5: Proveedores y resiliencia

### US-5.1 Gemini real y mock determinista
- `LLM_PROVIDER` y `EMBEDDING_PROVIDER` eligen `mock`, `gemini` u `openai` sin cambiar código.
- El mock genera embeddings deterministas a partir de las palabras del texto y responde de forma
  extractiva con citas reales o abstención, de modo que todo funciona sin claves.

### US-5.2 Fallos del proveedor
- Timeout configurable en cada llamada al LLM y a embeddings.
- Hasta 3 intentos con backoff exponencial ante timeouts, errores 5xx, límites de cuota y respuestas
  malformadas.
- Si se agotan, la API responde 503 (no disponible), 429 (cuota) o 502 (respuesta inválida) con un
  mensaje legible y sin datos del proveedor.

## 3. Requisitos no funcionales

- **Entrada:** el texto de los PDFs se entrega al modelo como datos delimitados y el prompt ordena
  ignorar instrucciones del documento. Es una mitigación, no una garantía.
- **Privacidad:** los logs no incluyen el texto de las preguntas ni el contenido de los contratos.
- **Trazabilidad:** una traza de OpenTelemetry une la petición HTTP, el encolado, la tarea del
  worker y las consultas a la base de datos; las llamadas al LLM llevan tokens.
- **Aislamiento por área:** no implementado (ver `DECISIONS.md` §5).

## 4. Criterios de salida

- [x] Todo se levanta con `docker compose up --build`, sin claves.
- [x] La interfaz permite subir PDFs, ver su estado y consultar con citas navegables.
- [x] El modo mock funciona sin dependencias externas.
- [x] Las pruebas unitarias y de integración pasan.
- [ ] Paginación del listado, validación automática de contratos contradictorios, versionado de
  parser y modelo de embeddings, permisos por área.
