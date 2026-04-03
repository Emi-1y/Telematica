#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <pthread.h>

/* --- Sockets Berkeley --- */
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>          /* getaddrinfo — resolución de nombres, no IPs hardcodeadas */

/* ============================================================
 *  CONSTANTES
 * ============================================================ */
#define MAX_CLIENTS     100
#define MAX_SENSORS     50
#define MAX_OPERATORS   20
#define BUFFER_SIZE     1024
#define MAX_HISTORY     20   /* últimas N mediciones por sensor */

/* Umbrales para detección de anomalías */
#define TEMP_MAX        40.0
#define TEMP_MIN       -10.0
#define VIBRATION_MAX   8.0
#define ENERGY_MAX    500.0

/* ============================================================
 *  ESTRUCTURAS DE DATOS
 * ============================================================ */

/* Una medición individual de un sensor */
typedef struct {
    char   sensor_id[64];
    char   tipo[32];       /* temperature, vibration, energy */
    double valor;
    time_t timestamp;
} Medicion;

/* Estado de un sensor conectado */
typedef struct {
    int    activo;
    char   id[64];
    char   tipo[32];
    char   ip[INET_ADDRSTRLEN];
    int    puerto;
    double ultimo_valor;
    time_t ultima_vez;
    Medicion historial[MAX_HISTORY];
    int    hist_count;
} Sensor;

/* Estado de un operador conectado */
typedef struct {
    int    activo;
    char   nombre[64];
    char   ip[INET_ADDRSTRLEN];
    int    socket_fd;      /* para enviarle alertas en tiempo real */
} Operador;

/* Datos que se le pasan a cada hilo de cliente */
typedef struct {
    int    socket_fd;
    char   ip[INET_ADDRSTRLEN];
    int    puerto;
} ClienteInfo;

/* ============================================================
 *  VARIABLES GLOBALES (protegidas por mutex)
 * ============================================================ */
Sensor    sensores[MAX_SENSORS];
Operador  operadores[MAX_OPERATORS];
int       num_sensores  = 0;
int       num_operadores = 0;

pthread_mutex_t mutex_sensores   = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t mutex_operadores = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t mutex_log        = PTHREAD_MUTEX_INITIALIZER;

FILE *archivo_log = NULL;

/* ============================================================
 *  LOGGING
 *  Escribe en consola Y en archivo con timestamp
 * ============================================================ */
void log_evento(const char *ip, int puerto, const char *recibido, const char *respuesta) {
    time_t ahora = time(NULL);
    struct tm *t = localtime(&ahora);
    char timestamp[32];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", t);

    pthread_mutex_lock(&mutex_log);

    /* Consola */
    printf("[%s] IP=%-16s PUERTO=%-6d | RX: %-40s | TX: %s\n",
           timestamp, ip, puerto, recibido, respuesta);

    /* Archivo */
    if (archivo_log) {
        fprintf(archivo_log, "[%s] IP=%s PUERTO=%d | RX=%s | TX=%s\n",
                timestamp, ip, puerto, recibido, respuesta);
        fflush(archivo_log);
    }

    pthread_mutex_unlock(&mutex_log);
}

/* ============================================================
 *  ENVIAR RESPUESTA
 *  Wrapper seguro para send()
 * ============================================================ */
int enviar(int fd, const char *msg) {
    return send(fd, msg, strlen(msg), 0);
}

/* ============================================================
 *  NOTIFICAR A TODOS LOS OPERADORES
 *  Se llama cuando se detecta una anomalía
 * ============================================================ */
void notificar_operadores(const char *alerta) {
    pthread_mutex_lock(&mutex_operadores);
    for (int i = 0; i < MAX_OPERATORS; i++) {
        if (operadores[i].activo) {
            send(operadores[i].socket_fd, alerta, strlen(alerta), MSG_NOSIGNAL);
        }
    }
    pthread_mutex_unlock(&mutex_operadores);
}

/* ============================================================
 *  DETECTAR ANOMALÍA
 *  Revisa si el valor supera umbrales y notifica
 * ============================================================ */
void verificar_anomalia(const char *sensor_id, const char *tipo, double valor,
                        const char *ip, int puerto) {
    char alerta[BUFFER_SIZE];
    int anomalia = 0;
    char razon[128] = "";

    if (strcmp(tipo, "temperature") == 0) {
        if (valor > TEMP_MAX) {
            snprintf(razon, sizeof(razon), "TEMPERATURA_ALTA (%.1f > %.1f)", valor, TEMP_MAX);
            anomalia = 1;
        } else if (valor < TEMP_MIN) {
            snprintf(razon, sizeof(razon), "TEMPERATURA_BAJA (%.1f < %.1f)", valor, TEMP_MIN);
            anomalia = 1;
        }
    } else if (strcmp(tipo, "vibration") == 0) {
        if (valor > VIBRATION_MAX) {
            snprintf(razon, sizeof(razon), "VIBRACION_ALTA (%.2f > %.1f)", valor, VIBRATION_MAX);
            anomalia = 1;
        }
    } else if (strcmp(tipo, "energy") == 0) {
        if (valor > ENERGY_MAX) {
            snprintf(razon, sizeof(razon), "CONSUMO_ALTO (%.1f > %.1f)", valor, ENERGY_MAX);
            anomalia = 1;
        }
    }

    if (anomalia) {
        snprintf(alerta, sizeof(alerta), "ALERT %s %s %.4f %s\n",
                 sensor_id, tipo, valor, razon);
        notificar_operadores(alerta);
        log_evento(ip, puerto, "anomalia detectada", alerta);
    }
}

/* ============================================================
 *  REGISTRAR SENSOR
 * ============================================================ */
int registrar_sensor(const char *id, const char *tipo, const char *ip, int puerto) {
    pthread_mutex_lock(&mutex_sensores);

    /* ¿Ya existe? */
    for (int i = 0; i < MAX_SENSORS; i++) {
        if (sensores[i].activo && strcmp(sensores[i].id, id) == 0) {
            pthread_mutex_unlock(&mutex_sensores);
            return -1; /* ya registrado */
        }
    }

    /* Buscar slot libre */
    for (int i = 0; i < MAX_SENSORS; i++) {
        if (!sensores[i].activo) {
            memset(&sensores[i], 0, sizeof(Sensor));
            sensores[i].activo = 1;
            strncpy(sensores[i].id,   id,   sizeof(sensores[i].id)   - 1);
            strncpy(sensores[i].tipo, tipo, sizeof(sensores[i].tipo) - 1);
            strncpy(sensores[i].ip,   ip,   sizeof(sensores[i].ip)   - 1);
            sensores[i].puerto = puerto;
            sensores[i].ultima_vez = time(NULL);
            num_sensores++;
            pthread_mutex_unlock(&mutex_sensores);
            return i;
        }
    }

    pthread_mutex_unlock(&mutex_sensores);
    return -2; /* servidor lleno */
}

/* ============================================================
 *  REGISTRAR OPERADOR
 * ============================================================ */
int registrar_operador(const char *nombre, const char *ip, int socket_fd) {
    pthread_mutex_lock(&mutex_operadores);
    for (int i = 0; i < MAX_OPERATORS; i++) {
        if (!operadores[i].activo) {
            operadores[i].activo    = 1;
            operadores[i].socket_fd = socket_fd;
            strncpy(operadores[i].nombre, nombre, sizeof(operadores[i].nombre) - 1);
            strncpy(operadores[i].ip,     ip,     sizeof(operadores[i].ip)     - 1);
            num_operadores++;
            pthread_mutex_unlock(&mutex_operadores);
            return i;
        }
    }
    pthread_mutex_unlock(&mutex_operadores);
    return -1;
}

/* ============================================================
 *  GUARDAR MEDICIÓN EN HISTORIAL
 * ============================================================ */
void guardar_medicion(const char *sensor_id, const char *tipo, double valor) {
    pthread_mutex_lock(&mutex_sensores);
    for (int i = 0; i < MAX_SENSORS; i++) {
        if (sensores[i].activo && strcmp(sensores[i].id, sensor_id) == 0) {
            int idx = sensores[i].hist_count % MAX_HISTORY; /* buffer circular */
            strncpy(sensores[i].historial[idx].sensor_id, sensor_id,
                    sizeof(sensores[i].historial[idx].sensor_id) - 1);
            strncpy(sensores[i].historial[idx].tipo, tipo,
                    sizeof(sensores[i].historial[idx].tipo) - 1);
            sensores[i].historial[idx].valor     = valor;
            sensores[i].historial[idx].timestamp = time(NULL);
            sensores[i].ultimo_valor = valor;
            sensores[i].ultima_vez   = time(NULL);
            sensores[i].hist_count++;
            break;
        }
    }
    pthread_mutex_unlock(&mutex_sensores);
}

/* ============================================================
 *  CONSTRUIR LISTA DE SENSORES (formato texto)
 * ============================================================ */
void construir_lista_sensores(char *buf, int buf_size) {
    pthread_mutex_lock(&mutex_sensores);
    int pos = snprintf(buf, buf_size, "SENSOR_LIST [");
    for (int i = 0; i < MAX_SENSORS; i++) {
        if (sensores[i].activo) {
            pos += snprintf(buf + pos, buf_size - pos,
                            "{id:%s,tipo:%s,valor:%.2f,ip:%s}",
                            sensores[i].id, sensores[i].tipo,
                            sensores[i].ultimo_valor, sensores[i].ip);
        }
    }
    snprintf(buf + pos, buf_size - pos, "]\n");
    pthread_mutex_unlock(&mutex_sensores);
}

/* ============================================================
 *  PROCESAR MENSAJE
 *  Parsea un mensaje recibido y devuelve la respuesta
 * ============================================================ */
void procesar_mensaje(const char *msg, char *respuesta, int resp_size,
                      ClienteInfo *cli, int *es_operador, char *nombre_cliente) {
    char cmd[32] = {0};
    char arg1[64] = {0};
    char arg2[64] = {0};
    char arg3[64] = {0};

    /* Parsear el mensaje (formato: CMD arg1 arg2 arg3) */
    sscanf(msg, "%31s %63s %63s %63s", cmd, arg1, arg2, arg3);

    /* ---- REGISTER SENSOR <id> <tipo> ---- */
    if (strcmp(cmd, "REGISTER") == 0 && strcmp(arg1, "SENSOR") == 0) {
        int r = registrar_sensor(arg2, arg3, cli->ip, cli->puerto);
        if (r >= 0) {
            snprintf(respuesta, resp_size, "OK SENSOR_REGISTERED %s\n", arg2);
            strncpy(nombre_cliente, arg2, 63);
        } else if (r == -1) {
            snprintf(respuesta, resp_size, "ERROR SENSOR_ALREADY_EXISTS %s\n", arg2);
        } else {
            snprintf(respuesta, resp_size, "ERROR SERVER_FULL\n");
        }
    }

    /* ---- REGISTER OPERATOR <nombre> ---- */
    else if (strcmp(cmd, "REGISTER") == 0 && strcmp(arg1, "OPERATOR") == 0) {
        int r = registrar_operador(arg2, cli->ip, cli->socket_fd);
        if (r >= 0) {
            snprintf(respuesta, resp_size, "OK OPERATOR_REGISTERED %s\n", arg2);
            *es_operador = 1;
            strncpy(nombre_cliente, arg2, 63);
        } else {
            snprintf(respuesta, resp_size, "ERROR SERVER_FULL\n");
        }
    }

    /* ---- DATA <sensor_id> <tipo> <valor> ---- */
    else if (strcmp(cmd, "DATA") == 0) {
        double valor = atof(arg3);
        guardar_medicion(arg1, arg2, valor);
        verificar_anomalia(arg1, arg2, valor, cli->ip, cli->puerto);
        snprintf(respuesta, resp_size, "OK DATA_RECEIVED\n");
    }

    /* ---- LIST SENSORS ---- */
    else if (strcmp(cmd, "LIST") == 0 && strcmp(arg1, "SENSORS") == 0) {
        construir_lista_sensores(respuesta, resp_size);
    }

    /* ---- GET HISTORY <sensor_id> ---- */
    else if (strcmp(cmd, "GET") == 0 && strcmp(arg1, "HISTORY") == 0) {
        pthread_mutex_lock(&mutex_sensores);
        int encontrado = 0;
        for (int i = 0; i < MAX_SENSORS; i++) {
            if (sensores[i].activo && strcmp(sensores[i].id, arg2) == 0) {
                int pos = snprintf(respuesta, resp_size, "HISTORY %s [", arg2);
                int total = sensores[i].hist_count < MAX_HISTORY
                            ? sensores[i].hist_count : MAX_HISTORY;
                for (int j = 0; j < total; j++) {
                    int idx = j % MAX_HISTORY;
                    pos += snprintf(respuesta + pos, resp_size - pos,
                                    "{t:%ld,v:%.2f}",
                                    sensores[i].historial[idx].timestamp,
                                    sensores[i].historial[idx].valor);
                }
                snprintf(respuesta + pos, resp_size - pos, "]\n");
                encontrado = 1;
                break;
            }
        }
        pthread_mutex_unlock(&mutex_sensores);
        if (!encontrado)
            snprintf(respuesta, resp_size, "ERROR SENSOR_NOT_FOUND %s\n", arg2);
    }

    /* ---- DISCONNECT ---- */
    else if (strcmp(cmd, "DISCONNECT") == 0) {
        snprintf(respuesta, resp_size, "OK GOODBYE\n");
    }

    /* ---- Comando desconocido ---- */
    else {
        snprintf(respuesta, resp_size, "ERROR UNKNOWN_COMMAND %s\n", cmd);
    }
}

/* ============================================================
 *  HILO POR CLIENTE
 *  Cada conexión aceptada corre en su propio hilo
 * ============================================================ */
void *manejar_cliente(void *arg) {
    ClienteInfo *cli = (ClienteInfo *)arg;
    char buffer[BUFFER_SIZE];
    char respuesta[BUFFER_SIZE];
    int  es_operador = 0;
    char nombre_cliente[64] = "desconocido";

    log_evento(cli->ip, cli->puerto, "CONEXION_ESTABLECIDA", "-");

    while (1) {
        memset(buffer, 0, sizeof(buffer));

        int bytes = recv(cli->socket_fd, buffer, sizeof(buffer) - 1, 0);

        if (bytes <= 0) {
            /* Cliente desconectado o error de red */
            if (bytes == 0) {
                log_evento(cli->ip, cli->puerto, "DESCONEXION", nombre_cliente);
            } else {
                log_evento(cli->ip, cli->puerto, "ERROR_RED", strerror(errno));
            }

            /* Marcar sensor/operador como inactivo */
            if (es_operador) {
                pthread_mutex_lock(&mutex_operadores);
                for (int i = 0; i < MAX_OPERATORS; i++) {
                    if (operadores[i].activo &&
                        strcmp(operadores[i].nombre, nombre_cliente) == 0) {
                        operadores[i].activo = 0;
                        num_operadores--;
                        break;
                    }
                }
                pthread_mutex_unlock(&mutex_operadores);
            } else {
                pthread_mutex_lock(&mutex_sensores);
                for (int i = 0; i < MAX_SENSORS; i++) {
                    if (sensores[i].activo &&
                        strcmp(sensores[i].id, nombre_cliente) == 0) {
                        sensores[i].activo = 0;
                        num_sensores--;
                        break;
                    }
                }
                pthread_mutex_unlock(&mutex_sensores);
            }
            break;
        }

        /* Eliminar el \n final para el log */
        buffer[strcspn(buffer, "\n")] = '\0';

        memset(respuesta, 0, sizeof(respuesta));
        procesar_mensaje(buffer, respuesta, sizeof(respuesta),
                         cli, &es_operador, nombre_cliente);

        enviar(cli->socket_fd, respuesta);
        log_evento(cli->ip, cli->puerto, buffer, respuesta);
    }

    close(cli->socket_fd);
    free(cli);
    return NULL;
}

/* ============================================================
 *  MAIN
 * ============================================================ */
int main(int argc, char *argv[]) {

    if (argc != 3) {
        fprintf(stderr, "Uso: %s <puerto> <archivo_logs>\n", argv[0]);
        fprintf(stderr, "Ej:  %s 8080 server.log\n", argv[0]);
        return EXIT_FAILURE;
    }

    const char *puerto_str   = argv[1];
    const char *archivo_str  = argv[2];

    /* Abrir archivo de logs */
    archivo_log = fopen(archivo_str, "a");
    if (!archivo_log) {
        perror("No se pudo abrir el archivo de logs");
        return EXIT_FAILURE;
    }

    /* --------------------------------------------------------
     * Crear socket del servidor (SOCK_STREAM = TCP)
     * SOCK_STREAM: confiable, orientado a conexión → ideal para
     * mensajes de control donde no podemos perder datos.
     * -------------------------------------------------------- */
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("socket()");
        return EXIT_FAILURE;
    }

    /* Reutilizar puerto inmediatamente (evita "Address already in use") */
    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    /* --------------------------------------------------------
     * Configurar dirección del servidor
     * -------------------------------------------------------- */
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;      /* acepta conexiones en cualquier interfaz */
    addr.sin_port        = htons(atoi(puerto_str));  /* htons: host→network byte order */

    /* --------------------------------------------------------
     * Bind: asociar el socket al puerto
     * -------------------------------------------------------- */
    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind()");
        close(server_fd);
        return EXIT_FAILURE;
    }

    /* --------------------------------------------------------
     * Listen: empezar a escuchar (cola de hasta 10 conexiones pendientes)
     * -------------------------------------------------------- */
    if (listen(server_fd, 10) < 0) {
        perror("listen()");
        close(server_fd);
        return EXIT_FAILURE;
    }

    printf("=== Servidor IoT iniciado en puerto %s ===\n", puerto_str);
    printf("=== Logs en: %s ===\n\n", archivo_str);

    /* --------------------------------------------------------
     * Loop principal: aceptar conexiones y crear un hilo por cliente
     * -------------------------------------------------------- */
    while (1) {
        struct sockaddr_in cliente_addr;
        socklen_t addr_len = sizeof(cliente_addr);

        int cliente_fd = accept(server_fd,
                                (struct sockaddr *)&cliente_addr,
                                &addr_len);
        if (cliente_fd < 0) {
            /* Error de red: no terminar el servidor, seguir aceptando */
            perror("accept() — continuando...");
            continue;
        }

        /* Crear struct con info del cliente para pasarle al hilo */
        ClienteInfo *cli = malloc(sizeof(ClienteInfo));
        if (!cli) {
            perror("malloc");
            close(cliente_fd);
            continue;
        }
        cli->socket_fd = cliente_fd;
        cli->puerto    = ntohs(cliente_addr.sin_port);
        inet_ntop(AF_INET, &cliente_addr.sin_addr,
                  cli->ip, sizeof(cli->ip));

        /* Crear hilo — cada cliente es independiente */
        pthread_t hilo;
        if (pthread_create(&hilo, NULL, manejar_cliente, cli) != 0) {
            perror("pthread_create");
            close(cliente_fd);
            free(cli);
            continue;
        }
        pthread_detach(hilo); /* el hilo se limpia solo al terminar */
    }

    fclose(archivo_log);
    close(server_fd);
    return EXIT_SUCCESS;
}