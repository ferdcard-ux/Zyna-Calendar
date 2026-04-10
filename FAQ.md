# FAQ

## No aparecen eventos

- Verifica tu conexion a internet.
- Asegura que `credentials.json` sea valido y tenga permisos correctos.
- Confirma que el calendario seleccionado tenga eventos futuros.

## No se abre la ventana de autenticacion

- Revisa la ruta de credenciales en Configuracion.
- Asegura que la API de Google Calendar este habilitada.
- En el primer inicio la autorizacion se realiza por consola; asegurate de aceptar el enlace y pegar el codigo.

## Quiero refrescar el token manualmente

- Usa el menu "Refresh Token" para reautorizar y validar la conexion.

## Me vuelve a pedir el codigo de autenticacion

- Verifica que exista `~/.config/zyna-calendar/token.json`.
- Asegura que el archivo contenga `refresh_token`.
- Revisa si revocaste el acceso en tu cuenta de Google.

## No recibo notificaciones

- Instala `notify-send` con `sudo apt install libnotify-bin`.
- Asegura que el proximo evento sea dentro de los siguientes 10 minutos.

## El .deb no instala dependencias automaticamente

- Usa `sudo apt install ./build_deb/zyna-calendar_0.1.2_all.deb` para resolver dependencias.
- Alternativamente ejecuta `./build_deb/install.sh`.

## Como desinstalo el widget

- Si lo instalaste con .deb, ejecuta `sudo apt remove zyna-calendar`.
- Si lo ejecutas localmente, borra el directorio y elimina el autostart desde la configuracion.
- También puedes usar `./uninstall.sh` para una desinstalacion guiada.
