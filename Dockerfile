# ─────────────────────────────────────────────────────────────
#  ETAPA 1: compilación
#  Usamos una imagen con gcc para compilar el servidor en C.
#  Esta etapa no va al resultado final — solo sirve para compilar.
# ─────────────────────────────────────────────────────────────
FROM ubuntu:22.04 AS compilador

# Instalar gcc y las herramientas de compilación
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar el código fuente al contenedor
COPY server/server.c .

# Compilar el servidor
# -o server      → nombre del ejecutable
# -lpthread      → linkear la librería de hilos (pthread)
# -Wall          → mostrar todos los warnings
RUN gcc -o server server.c -lpthread -Wall

# ─────────────────────────────────────────────────────────────
#  ETAPA 2: imagen final
#  Solo copiamos el binario compilado, sin gcc ni código fuente.
#  Resultado: imagen mucho más pequeña y segura.
# ─────────────────────────────────────────────────────────────
FROM ubuntu:22.04

WORKDIR /app

# Copiar solo el binario compilado desde la etapa anterior
COPY --from=compilador /app/server .

# Crear directorio para los logs
RUN mkdir -p /app/logs

# Documentar qué puerto usa el contenedor
# (esto no abre el puerto — eso se hace con -p al correr)
EXPOSE 8080

# Comando por defecto al iniciar el contenedor
# Puerto 8080, logs en /app/logs/server.log
CMD ["./server", "8080", "/app/logs/server.log"]