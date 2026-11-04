# Decisiones técnicas

Proyecto: asistente RAG de contratos.
Aquí están las respuestas a las preguntas de diseño, los trade-offs y el uso de IA.
Lo que no está implementado se dice explícitamente.

---

## 1. Parser de PDFs con tablas

Hace falta un parser de PDFs que entienda tablas: Docling, o una alternativa justificada. Elegí
`pdfplumber`.

- **Docling:** reconoce el layout con modelos de visión, pero arrastra PyTorch y modelos locales de
  varios GB. Eso encarece el build de Docker y la memoria necesaria, y arriesga la máquina
  de quien lo ejecute. No lo medí en este repo: es una estimación basada en sus dependencias.
- **MarkItDown:** devuelve el documento como un único bloque de Markdown, sin saber en qué página
  está cada cláusula. Las citas exigen la página exacta, así que lo descarté.
- **`pdfplumber` + serializador a Markdown:** se procesa página por página, de modo que cada
  fragmento conserva su página. Las tablas (`extract_tables()`) se convierten a tablas Markdown, un
  formato que el modelo lee bien, y no hay modelos de visión que descargar.

Costo asumido: `pdfplumber` no hace OCR ni reconoce layouts complejos (tablas sin bordes, varias
columnas). Para PDFs escaneados el documento termina `failed` con un motivo legible.

---

## 2. Estrategia de Segmentación (Chunking) y Recuperación

### Segmentación

- `MarkdownTableChunker`: nunca mezcla páginas (el número de página se conserva siempre), separa
  párrafos por línea en blanco y serializa las tablas a Markdown.
- Tamaño: 500 caracteres con 80 de solapamiento (`CHUNK_MAX_CHARS`, `CHUNK_OVERLAP_CHARS`). Se mide
  en caracteres y no en tokens porque es determinista y no exige un tokenizador por proveedor.
- Una tabla de tarifas nunca se parte a mitad de fila.
- Cada fragmento guarda `document_id`, `page_number`, `chunk_index` y las posiciones de inicio y
  fin; el nombre del documento se obtiene por JOIN.

### Evidencia (`backend/eval/run_eval.py`, 12 preguntas respondibles, embedding mock)

| Chunk / solape | Chunks | hit@1 | hit@3 | hit@5 |
| -------------- | ------ | ----- | ----- | ----- |
| 300 / 30       | 17     | 0,75  | 0,83  | 0,92  |
| 400 / 50       | 12     | 0,75  | 0,92  | 0,92  |
| **500 / 80**   | 11     | 0,75  | 0,92  | 0,92  |
| 600 / 100      | 9      | 0,67  | 0,83  | 0,92  |
| 800 / 30       | 9      | 0,67  | 0,83  | 0,92  |

Los fragmentos pequeños (300 o menos) tienden a separar una cláusula de su tabla; los grandes (600 o más) mezclan temas distintos y empeoran el ranking en este conjunto. 400 y 500 empatan y elegí 500 porque produce menos fragmentos. Antes de esta evaluación el valor por defecto era 800/100.

El único fallo persistente a k=5 (`q10`, "fuerza mayor" frente a "huelgas portuarias") es de vocabulario: el embedding mock es léxico y no conecta sinónimos. Esta tabla mide el pipeline con un embedding mock, no la calidad de Gemini. Con solo 12 preguntas, diferencias de una pregunta (0,08) no son concluyentes.

### Recuperación: solo vectorial

- Distancia coseno en pgvector (`vector_cosine_ops`, índice HNSW), solo sobre documentos `ready`.
  Sin reranking.
- Motivo: el vocabulario del dominio tiene sinónimos (*días libres*, *free time*, *demurrage*,
  *sobreestadía*) que una búsqueda léxica no conecta, y con 4 contratos de ejemplo no hay evidencia
  para justificar una segunda etapa.
- Costo: los identificadores exactos (número de cláusula, código de contenedor, importes) se
  recuperan peor. La búsqueda híbrida con RRF es la primera mejora prevista (§9).

---

## 3. Idempotencia y Ciclo de Vida ante Reprocesamiento

### Definición

Una operación es idempotente si repetirla (re-subida, redelivery de Celery o reintento tras un
fallo) deja la base de datos igual que ejecutarla una vez: un documento por contenido y un único
conjunto completo de fragmentos. Las pruebas están en
`backend/tests/integration/test_idempotency_integration.py`, con PostgreSQL y Redis reales.

### Cómo se implementa

- **Subida duplicada:** SHA-256 de los bytes con índice único en `content_hash`. El mismo PDF
  devuelve el documento existente, sin archivo, fila ni tarea nuevos.
- **Subidas simultáneas:** la inserción corre en un SAVEPOINT; quien pierde la carrera recibe el
  documento ganador en vez de un error 500.
- **Redelivery tras éxito:** Celery entrega al menos una vez. Si el documento ya está `ready`, la
  tarea no hace nada.
- **Fallo a mitad:** se borran los fragmentos del documento y queda `failed` con un motivo legible.
  Los fragmentos se escriben juntos tras generar todos los embeddings, así que nunca quedan a medias.
- **Re-subida de un `failed`:** vuelve a `pending` y se encola de nuevo. Es la forma de reintentar
  desde la interfaz.
- **Encolado tras el commit:** antes la tarea se encolaba dentro de la petición y un worker rápido
  podía no encontrar aún el documento. Ahora se encola cuando la transacción ya hizo commit.
- **Worker muerto (SIGKILL u OOM):** `acks_late` y `reject_on_worker_lost` hacen que Redis
  reentregue el mensaje tras 600 s (`TASK_VISIBILITY_TIMEOUT_SECONDS`) y el reproceso termina sin
  duplicar. Como respaldo, un reaper de Celery Beat marca `failed`, con motivo legible, los
  documentos en `processing` desde hace más de 900 s (`PROCESSING_TIMEOUT_SECONDS`). Está probado
  simulando el worker muerto, no matando un contenedor real.

Limitaciones: si una tarea lenta supera el timeout, el documento pasa a `failed` y luego a `ready`
cuando esa tarea termina; el estado final es correcto pero el intermedio se ve en la interfaz. Y el
archivo de una subida que pierde la carrera queda huérfano en el almacenamiento (el puerto no tiene
`delete`).

### Parser o modelo de embeddings con otra versión

Decisión: reemplazar (borrar y reinsertar los fragmentos del documento), no versionar ni rechazar.
Mantiene una sola versión del índice y evita mezclar en una consulta vectores de modelos distintos,
que no son comparables. El costo es no poder comparar versiones ni volver atrás.

Esto todavía no está automatizado: el esquema no guarda la versión del parser ni del modelo, y el
reemplazo solo ocurre si se reprocesa un documento que no está `ready`. Con más tiempo añadiría las
columnas `parser_version` y `embedding_model` y un comando de reindexado.

---

## 4. Criterio de Suficiencia de Evidencia y Política Anti-Alucinación

### Criterio de suficiencia

1. **Umbral de similitud:** se descartan los fragmentos con similitud coseno menor que
   `RAG_SIMILARITY_THRESHOLD` (0,25 por defecto). Si ninguno lo supera, el contexto llega vacío al
   LLM. Con el mock, las 2 preguntas sin evidencia del conjunto de evaluación quedan bajo el umbral.
   Con Gemini hay que recalibrarlo, porque cada modelo tiene su propia escala de similitud.
2. **Juicio del modelo:** el prompt obliga a devolver `has_sufficient_evidence=false` y a no inventar
   cifras cuando el contexto no responde. No se evita la llamada al LLM cuando no hay fragmentos,
   porque el asistente también responde saludos y preguntas sobre sus capacidades.
3. **Validación de citas (`StrictCitationValidator`):** cada cita debe pertenecer a un documento
   recuperado y su `snippet_text` debe aparecer literalmente (normalizando espacios y mayúsculas)
   en un fragmento recuperado de ese documento. Los metadatos de la cita devuelta (`chunk_id`,
   página, nombre) se reescriben desde el fragmento real, así que el modelo no puede falsear la
   página. Si todas las citas fallan, la respuesta se marca sin evidencia suficiente y sin citas.

### Contratos que se contradicen

El sistema no promedia ni elige: el prompt pide exponer ambas posturas citando documento y página
(por ejemplo 7 días libres en Maersk y 10 en CMA CGM, ambos en los contratos de ejemplo). Depende del
modelo y no está validado automáticamente; falta una pregunta de evaluación para esto.

### Límites

La cita se valida por coincidencia literal del texto, no por el `chunk_id` que declara el modelo. Que
el fragmento realmente respalde la afirmación lo decide el modelo; el sistema no lo comprueba.

---

## 5. Aislamiento de Datos entre Áreas

Decisión para el MVP: dejarlo como trabajo futuro. El esquema no tiene `tenant_id` ni
`department_id`, y cualquier usuario con acceso a la API ve todos los contratos.

- **Costo de modelarlo ahora:** autenticación, tabla de equipos, un filtro obligatorio en cada
  consulta (incluida la recuperación vectorial), idealmente Row-Level Security en PostgreSQL y
  pruebas de aislamiento. Desviaría el tiempo de los requisitos centrales.
- **Riesgo de no modelarlo:** un usuario puede obtener por el chat texto de contratos de otra área.
  Es aceptable solo en una demo con datos sintéticos y red interna, no en producción.
- **Costo de añadirlo después:** moderado. Hace falta una columna en `contracts_documents` (y en
  `document_chunks` para filtrar antes de la búsqueda aproximada), migrar los datos existentes y un
  `WHERE` en `PgVectorQueryEngine`. Con HNSW, un filtro muy selectivo puede devolver menos de `k`
  resultados; habría que ajustar `hnsw.ef_search` o particionar.

---

## 6. Observabilidad, seguridad y fallos

- **Trazas:** `FastAPIInstrumentor` y `CeleryInstrumentor` propagan el contexto W3C en las cabeceras
  de la tarea, así que HTTP, encolado, tarea, etapas (`index.parse`, `index.chunk`, `index.embed`,
  `index.persist`), `rag.*` y `llm.generate` (o `llm.generate_stream`, con tiempo hasta el primer token
y las llamadas HTTP al proveedor) forman una sola traza. El instrumentador oficial de SQLAlchemy
  no soporta la versión 2.1, por eso `core/telemetry/tracer.py` emite los spans `db.query` con los
  eventos del núcleo, guardando el texto de la sentencia sin parámetros.
- **Exportación:** `OTEL_TRACES_EXPORTER=otlp|console|none`. Por defecto es `none`; compose usa
  `otlp` hacia Jaeger. Los logs JSON incluyen `trace_id`, `span_id` y los campos `extra`.
- **Privacidad:** los logs no incluyen el texto de las preguntas (solo su longitud) ni contenido de
  contratos, y los errores de la API no exponen detalles del proveedor.
- **Subida:** extensión `.pdf`, firma `%PDF-`, tamaño máximo (25 MB) y archivo no vacío. En lote, un
  archivo rechazado no bloquea al resto.
- **PDFs problemáticos:** corruptos, con contraseña o sin texto terminan en `failed` con un motivo
  legible.
- **Caída del proveedor:** los errores del LLM y de embeddings se clasifican (no disponible, cuota,
  respuesta inválida), se reintentan con backoff y, si persisten, la API responde 503, 429 o 502 con
  un mensaje legible. Durante la indexación, el documento queda `failed` con ese motivo.
- **Inyección de instrucciones en PDFs:** el prompt ordena ignorar instrucciones del documento, el
  contexto se entrega delimitado como datos y la validación de citas impide inventar fuentes. Es
  una mitigación, no una garantía: un contrato malicioso aún podría sesgar la redacción.

---

## 7. Eventos entre procesos

El sistema tiene eventos de dominio (`document.uploaded`, `document.processing_started`,
`document.ready`, `document.failed`) y los usa para algo concreto: que el navegador se entere de los
cambios de estado del worker sin sondear. La arquitectura completa está en
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); aquí van las decisiones.

- **Comandos y eventos van por canales distintos.** Encolar el procesamiento es un comando (Celery);
  que un documento esté `ready` es un hecho (stream). Mezclarlos habría hecho que un evento
  duplicado pudiera procesar dos veces el mismo documento. Por eso `document.uploaded` dispara la
  tarea con un suscriptor local y no se lee del stream.
- **Redis Streams, no Pub/Sub.** Pub/Sub pierde todo lo que ocurre mientras un lector está
  desconectado. Con un stream, cada instancia de la API lee el log completo por su cuenta
  (difusión, sin grupos de consumidores), recorta con `MAXLEN` (10.000 eventos) y un cliente que se
  reconecta recupera lo perdido con `Last-Event-ID`. El id del SSE es el id del stream.
- **Publicar solo tras el commit** (`DeferredEventBus`). Antes se encolaba dentro de la petición, y un
  worker rápido podía no encontrar aún el documento. Con rollback, los eventos pendientes se
  descartan.
- **`processing` se confirma antes del trabajo lento.** Toda la tarea corría en una sola
  transacción, así que `processing` no era visible hasta el final: ni la interfaz, ni el evento, ni
  el reaper de documentos atascados lo veían de verdad. Ahora la tarea confirma `processing`,
  publica `document.processing_started`, hace el trabajo y confirma `ready` o `failed`.
- **Un fallo de Redis no rompe nada.** Si no se puede publicar, se registra y se sigue: el estado ya
  está en PostgreSQL. A cambio, el evento se pierde (como máximo una vez desde el publicador).
- **Un cliente lento se corta.** Cada cliente SSE tiene una cola acotada; si se llena, se cierra su
  flujo y el navegador reconecta con `Last-Event-ID`, en lugar de acumular memoria o frenar a los
  demás.

### Garantías y qué cubre cada defensa

| Canal               | Garantía                      | Si falla                                                  |
| ------------------- | ----------------------------- | --------------------------------------------------------- |
| Tarea de Celery     | Al menos una vez, idempotente | Reentrega por `acks_late`; el reaper cierra los atascados |
| Evento al stream    | Como máximo una vez           | La interfaz sondea cada 30 s y refresca al reconectar     |
| Stream al navegador | Al menos una vez              | `Last-Event-ID` reenvía lo perdido                        |

Límites conocidos:

- Si el worker muere entre el commit y la publicación, ese evento no llega nunca al stream. La
  solución completa es un *outbox* transaccional; no la hice por el tiempo disponible.
- El stream no tiene control de acceso por área: igual que el resto de la API (ver §5), cualquier
  cliente conectado ve los eventos de todos los documentos. Los eventos solo llevan identificadores,
  recuento de fragmentos y el motivo del fallo; nunca texto de contratos.
- Cada conexión SSE retrasa el cierre ordenado de uvicorn hasta el `--timeout-graceful-shutdown`
  (5 s en compose).

## 8. Uso de IA

Usé Claude code y Antigravity.

- **Qué generó la IA:** el esqueleto del backend y del frontend, los adaptadores de proveedores, la
  mayoría de las pruebas y, en la fase final, el script y el dataset de evaluación, el cableado de
  OpenTelemetry, la subida por lote, el manejo de errores del proveedor, la navegación de citas, la
  robustez del worker, el bus de eventos sobre Redis Streams con su SSE, las pruebas de integración
  y esta documentación.
- **Cómo se verificó:** ejecutando `ruff`, `mypy` estricto, `pytest` (unitarias e integración con
  PostgreSQL y Redis reales), `vitest` y la evaluación de recuperación; y levantando
  `docker compose up --build` para comprobar una subida, una consulta y una traza completa en Jaeger.
- **Qué no se verificó:** el camino con Gemini real (no hay claves en el repo) y la
  recuperación de un worker matado de verdad (solo se simula en las pruebas).

## 9. Con más tiempo

1. Búsqueda híbrida (texto completo de PostgreSQL más vectores, fusionados con RRF) y reranking,
   si la evaluación con embeddings reales lo justifica.
2. *Outbox* transaccional para que los eventos nunca se pierdan entre el commit y su publicación.
3. Versionado de parser y modelo de embeddings, con comando de reindexado.
4. Permisos por equipo con autenticación, y filtrado en la recuperación (también en el SSE).
5. OCR para contratos escaneados.
6. Evaluación con embeddings reales y contratos reales; medir el p95 de extremo a extremo.
