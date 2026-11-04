FROM oven/bun:1-alpine

WORKDIR /app

# Copiar archivos de dependencias
COPY package.json bun.lock ./

# Instalar dependencias con Bun
RUN bun install --frozen-lockfile

# Copiar código fuente y configuración
COPY . .

# Exponer el puerto de la aplicación
EXPOSE 3000

# Ejecutar el servidor de desarrollo/preview con host accesible
CMD ["bun", "run", "dev", "--host", "0.0.0.0", "--port", "3000"]
