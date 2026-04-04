#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>

/* 
 * IOT C SENSOR CLIENT
 * -------------------
 * This client implements the IoT monitoring protocol in C.
 * It demonstrates multi-language compatibility for the system.
 */

#define BUFFER_SIZE 1024

void log_msg(const char *tag, const char *msg) {
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    printf("[%02d:%02d:%02d] [%s] %s\n", t->tm_hour, t->tm_min, t->tm_sec, tag, msg);
}

int main(int argc, char *argv[]) {
    if (argc != 5) {
        fprintf(stderr, "Uso: %s <host> <puerto> <sensor_id> <tipo>\n", argv[0]);
        return EXIT_FAILURE;
    }

    const char *host      = argv[1];
    const char *puerto_str = argv[2];
    const char *sensor_id = argv[3];
    const char *tipo      = argv[4];

    /* 1. Resolución DNS */
    struct addrinfo hints, *res;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family   = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    if (getaddrinfo(host, puerto_str, &hints, &res) != 0) {
        perror("getaddrinfo");
        return EXIT_FAILURE;
    }

    /* 2. Crear Socket */
    int sock = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (sock < 0) {
        perror("socket");
        freeaddrinfo(res);
        return EXIT_FAILURE;
    }

    /* 3. Conectar */
    if (connect(sock, res->ai_addr, res->ai_addrlen) < 0) {
        perror("connect");
        close(sock);
        freeaddrinfo(res);
        return EXIT_FAILURE;
    }
    freeaddrinfo(res);

    log_msg("CONN", "Conectado al servidor central IoT");

    char buffer[BUFFER_SIZE];
    char resp[BUFFER_SIZE];

    /* 4. Registro */
    snprintf(buffer, sizeof(buffer), "REGISTER SENSOR %s %s\n", sensor_id, tipo);
    send(sock, buffer, strlen(buffer), 0);
    
    int bytes = recv(sock, resp, sizeof(resp) - 1, 0);
    if (bytes > 0) {
        resp[bytes] = '\0';
        log_msg("REG", resp);
    }

    /* 5. Loop de Datos */
    srand(time(NULL));
    while (1) {
        double valor = 20.0 + (rand() % 150) / 10.0; /* 20.0 - 35.0 */
        
        /* Simular anomalía ocasional (5% probabilidad) */
        if ((rand() % 100) < 5) valor = 50.5;

        snprintf(buffer, sizeof(buffer), "DATA %s %s %.2f\n", sensor_id, tipo, valor);
        send(sock, buffer, strlen(buffer), 0);
        
        bytes = recv(sock, resp, sizeof(resp) - 1, 0);
        if (bytes > 0) {
            resp[bytes] = '\0';
            char log_txt[128];
            snprintf(log_txt, sizeof(log_txt), "Data: %.2f | Resp: %s", valor, resp);
            log_msg("DATA", log_txt);
        } else {
            log_msg("ERR", "Conexión perdida con el servidor");
            break;
        }
        
        sleep(5);
    }

    close(sock);
    return EXIT_SUCCESS;
}
