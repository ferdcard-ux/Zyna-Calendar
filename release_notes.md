# Notas de Release

## v0.1.5

- La terminal de autenticacion ya no mantiene viva la app como proceso hijo.
- Tras autenticar correctamente, Zyna Calendar se lanza desacoplado y la terminal muestra "Presione Enter para salir".
- Cerrar la terminal despues de autenticar ya no cierra el widget.

## v0.1.4

- El lanzador ahora detecta tokens revocados antes del arranque y abre la terminal de reautorizacion cuando hace falta.
- Se evita que la app quede silenciosa al iniciarse desde el menu con credenciales vencidas.

## v0.1.3

- La app ahora distingue de forma visible entre sincronizacion normal, uso de cache y autenticacion vencida.
- Se muestra la antiguedad de la ultima sincronizacion real con Google cuando los eventos provienen de cache.
- La UI eleva una advertencia persistente y una notificacion cuando la sincronizacion requiere atencion.
- El flujo de autenticacion fuerza reautorizacion limpia cuando Google revoca el refresh token.

## v0.1.2

- Instalador refuerza dependencias con pip --user y valida imports.
- Opcion "Refresh Token" para reautorizar y verificar conexion.
- Script de desinstalacion interactivo incluido.
- Documentacion actualizada con la nueva instalacion y desinstalacion.

## v0.1.1

- Correccion de autenticacion offline para evitar apertura de navegador sin conexion.
- Ajustes de dependencias del .deb para compatibilidad en Zorin Lite.
- Flujo de autenticacion manual unificado con guardado del refresh_token.
- Launcher detecta primera ejecucion y abre terminal solo si falta token.

## v0.1.0

- Base funcional del widget con OAuth2 y Google Calendar API.
- UI frameless, arrastrable y con estilo Zorin Dark Blue.
- Sincronizacion en segundo plano con cache local.
- Notificaciones nativas para eventos proximos.
- Dialogo de configuracion y menu de acciones.
- Script de instalacion y estructura de empaquetado .deb.
- Documentacion extendida con instalacion recomendada y resolucion de dependencias.
