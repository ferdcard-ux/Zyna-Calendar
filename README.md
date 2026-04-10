# Zyna-Calendar

Widget de escritorio ligero para Zorin OS Lite (XFCE) que muestra los eventos de Google Calendar mediante la API oficial.

## Caracteristicas

- Ventana frameless y arrastrable, integrada como elemento de fondo.
- Sincronizacion no bloqueante con hilo dedicado.
- Cache local para modo sin conexion.
- Autenticacion manual por consola con persistencia de refresh_token.
- Opcion "Refresh Token" para reautorizar y validar conexion.
- Notificaciones nativas de eventos proximos.
- Configuracion editable desde la interfaz (eventos, autostart, credenciales, intervalo).
- Menu hamburguesa con acciones rapidas.

## Requisitos

- Python 3.10+
- PyQt6
- google-api-python-client y dependencias de autenticacion

## Ejecucion rapida

1. Instala dependencias del sistema o usa `requirements.txt`.
2. Coloca `credentials.json` donde prefieras y configura su ruta desde el menu (o dejalo en el directorio del proyecto).
3. Ejecuta:

```bash
python3 main.py
```

Si es el primer inicio y no existe `token.json`, se mostrara un enlace en la terminal para autorizar el acceso. Al finalizar veras el mensaje `Autenticacion completada`.

## Instalador para autostart

```bash
./install.sh
```

El instalador tambien instala dependencias adicionales en el entorno de usuario y verifica las importaciones principales.

## Empaquetado .deb

### Instalacion recomendada del .deb (resuelve dependencias)

```bash
sudo apt install ./build_deb/zyna-calendar_0.1.2_all.deb
```

### Instalacion automatizada con dependencias

```bash
./build_deb/install.sh
```

### Construccion del paquete

```bash
./build_deb/build.sh
```

El paquete generado quedara en `build_deb/zyna-calendar_0.1.2_all.deb`.

## Desinstalacion interactiva

```bash
./uninstall.sh
```

Permite eliminar el applet, los datos locales y las dependencias instaladas con `pip --user`.
