# Zyna-Calendar

Widget de escritorio ligero para Zorin OS Lite (XFCE) que muestra los eventos de Google Calendar mediante la API oficial.

## Caracteristicas

- Ventana frameless y arrastrable, integrada como elemento de fondo.
- Autoajuste de tamano: crece y se encoge segun el numero de eventos.
- Minimizar a un icono compacto arrastrable; doble clic restaura el widget.
- Sincronizacion no bloqueante con hilo dedicado.
- Cache local para modo sin conexion.
- Autenticacion OAuth por navegador (loopback IP) con persistencia del refresh_token; modo manual copy/paste como respaldo.
- Opcion "Refresh Token" para reautorizar y validar conexion.
- Notificaciones nativas de eventos proximos y notificacion persistente para los eventos de hoy.
- Tarjetas resaltadas por cercania: hoy suma 25% de visibilidad y los proximos 2 dias 15% (tope 100%).
- Clic en cualquier punto de una tarjeta abre el evento en el navegador.
- Pestana "Apariencia": transparencia ajustable (minimo seguro 30%), 7 temas y colores HEX personalizados con contraste Fondo/Tarjetas/Texto (WCAG).
- Sistema de actualizaciones integrado: comprueba las releases de GitHub (repositorio `owner/repo` configurable), descarga el `.deb` con barra de progreso y verifica su SHA-256 antes de instalar.
- Pestana "Actualizar": repositorio, comprobacion automatica cada 12 horas y al iniciar, y boton "Buscar actualizaciones ahora".
- Configuracion editable desde la interfaz (eventos, autostart, credenciales, intervalo, actualizaciones).
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

Si es el primer inicio y no existe `token.json`, la app abrira tu navegador para autorizar el acceso (flujo loopback); al aceptar, veras `AUTENTICACION OK - token guardado`. En equipos sin entorno grafico se usa el modo manual copy/paste con `http://localhost:1`.

## Instalador para autostart

```bash
./install.sh
```

El instalador tambien instala dependencias adicionales en el entorno de usuario y verifica las importaciones principales.

## Empaquetado .deb

### Instalacion recomendada del .deb (resuelve dependencias)

```bash
sudo apt install ./build_deb/zyna-calendar_0.2.0_all.deb
```

### Instalacion automatizada con dependencias

```bash
./build_deb/install.sh
```

### Construccion del paquete

```bash
./build_deb/build.sh
```

El paquete generado quedara en `build_deb/zyna-calendar_0.2.0_all.deb`.

## Desinstalacion interactiva

```bash
./uninstall.sh
```

Permite eliminar el applet, el autostart, el entorno virtual y los datos locales. La opcion de dependencias `pip --user` ya no se usa: todas las dependencias de Google API viven en el entorno virtual interno.
