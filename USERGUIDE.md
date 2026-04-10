# Guia de Usuario

## Primer inicio

1. Crea un proyecto en Google Cloud Console y habilita Google Calendar API.
2. Genera un cliente OAuth de tipo Desktop app.
3. Descarga `credentials.json` y configura su ruta desde el menu (Configuracion).
4. En el primer inicio se abrira un enlace en la terminal para autorizar. Al finalizar veras el mensaje `Autenticacion completada`.

## Menu principal

- Sync Manual: actualiza los eventos inmediatamente.
- Refresh Token: reautoriza el acceso y valida la conexion con Google.
- Configuracion: ajusta numero de eventos, autostart y ruta de credenciales.
- Info: informacion basica del widget.
- Reiniciar Applet: reinicia la aplicacion.
- Salir: cierra el widget.

## Intervalo de sincronizacion

Desde Configuracion puedes definir el intervalo en minutos.

- 0 desactiva la sincronizacion automatica.
- Un valor mayor que 0 actualiza automaticamente el calendario.

## Modo sin conexion

Si no hay red disponible, Zyna-Calendar mostrara los ultimos eventos guardados en cache y un mensaje sutil de estado.

## Autenticacion persistente

El archivo `~/.config/zyna-calendar/token.json` guarda el `refresh_token`. Mientras no se elimine ni sea revocado por Google, la app no solicitara el codigo otra vez despues de reiniciar el sistema.

## Notificaciones

Se envia una notificacion cuando falta menos de 10 minutos para el proximo evento. Requiere `notify-send` (paquete `libnotify-bin`).

## Instalacion con .deb

Opcion recomendada (resuelve dependencias automaticamente):

```bash
sudo apt install ./build_deb/zyna-calendar_0.1.2_all.deb
```

Instalacion automatizada:

```bash
./build_deb/install.sh
```

## Desinstalacion

Puedes ejecutar el script interactivo:

```bash
./uninstall.sh
```

Pregunta si deseas eliminar los datos locales y las dependencias instaladas con `pip --user`.
