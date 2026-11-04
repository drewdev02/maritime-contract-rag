# Frontend

React + TypeScript + Vite, con Bun como gestor de paquetes. Tres vistas: subida de PDFs
(`/upload`), lista de documentos (`/documents`) y chat con citas (`/chat`).

## Comandos

```bash
bun install
bun run dev        # servidor de desarrollo con proxy a la API (BACKEND_PROXY_TARGET)
bun run typecheck  # tsc -b
bun run lint       # oxlint
bun run test       # vitest (happy-dom)
bun run build
```

## Variables de entorno

| Variable | Para qué | Por defecto |
|---|---|---|
| `VITE_API_URL` | Prefijo de la API | `/api/v1` |
| `VITE_POLL_INTERVAL_MS` | Intervalo de polling de documentos | `2000` |
| `VITE_API_TIMEOUT_MS` | Timeout de las peticiones | `30000` |
| `VITE_MAX_FILE_SIZE_MB` | Tamaño máximo en la validación del cliente | `25` |
| `BACKEND_PROXY_TARGET` | Destino del proxy de Vite | `http://api:8000` |

Los valores de ejemplo están en `../.env.example`.

## Estructura

```
src/
  routes/            rutas de TanStack Router
  features/
    upload/          zona de arrastre y subida por lote
    documents/       tabla, filtro por estado y polling
    chat/            conversación, streaming SSE, citas y panel del fragmento
  shared/            cliente HTTP, componentes de shadcn/ui, utilidades
```

## Notas sobre las pruebas

Las pruebas usan happy-dom registrado globalmente. Con ese entorno `screen` de Testing Library queda
atado al documento anterior y `waitFor` falla, así que los tests consultan `document.body` con
`within` y vacían las promesas pendientes con `act`.
