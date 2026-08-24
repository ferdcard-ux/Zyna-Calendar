# Notas de Release

## v0.2.0

- Nueva autenticacion por navegador (loopback IP): la app abre el navegador, captura la autorizacion automaticamente y ya no depende del flujo OOB retirado por Google (que provocaba "Error 400: invalid_request").
- Fallback manual copy/paste con redirect `http://localhost:1` para equipos sin entorno grafico.
- Tras renovar el token desde "Refresh Token", la sincronizacion se recupera sin reiniciar la app (invalidacion de credenciales cacheadas).
- Los fallos transitorios de red durante el refresco ya no fuerzan re-autorizacion: la app arranca en modo cache.
- Escritura atomica de settings, cache y token; recuperacion automatica ante JSON corrupto (respaldo `.corrupt` + valores por defecto).
- `token.json` con permisos 0600 (owner-only).
- Log rotativo (512 KB x 2 copias) en lugar de crecimiento ilimitado.
- El estado de notificaciones del dia se persiste: reiniciar no re-emite notificaciones ya mostradas.
- Zona horaria detectada del sistema con America/Bogota como respaldo.
- Corregido el resaltado por fecha: hoy suma +25% de visibilidad y los proximos 2 dias +15% (tope 100%); antes quedaban mas transparentes que el resto.
- Boton hamburguesa pintado con el color de texto del tema activo; textos unificados con tildes.
- Publica tokens permanentes cuando el Consent Screen de Google esta en modo Production.

## v0.1.8

- Sistema de actualizaciones en la app: consulta la release mas reciente en GitHub (repositorio configurable `owner/repo`).
- Descarga del paquete `.deb` con barra de progreso y verificacion del digest SHA-256 publicado (o calculo local si no hay digest publicado).
- Pestana "Actualizar" en configuracion: repositorio (vacio desactiva las actualizaciones) y comprobacion automatica cada 12 horas y al arrancar.
- Accion de menu "Buscar actualizaciones" y notificacion de escritorio cuando hay una version mas reciente.
- Instalacion desde el dialogo con `pkexec dpkg -i` y aviso de reinicio tras aplicar el cambio.
- Corregido el limite de eventos: el widget lee `max_events` en cada sincronizacion, aplicando el cambio sin reiniciar la app.

## v0.1.7

- "Salir" fuerza un cierre total: detiene timers, hilos y cierra la ventana de icono antes de terminar el proceso.
- Nueva accion "Minimizar": el widget se oculta y deja un icono compacto arrastrable; doble clic restaura la ventana en su posicion.
- Pestana "Apariencia" en configuracion con slider de transparencia (minimo seguro 30%), 7 temas preconfigurados y tema personalizado con colores HEX para Fondo, Tarjetas, Texto y Acento.
- Contraste WCAG automatico: si el texto elegido no destaca sobre el fondo, la app lo reemplaza por blanco o negro legible.
- Autoajuste dinamico de tamano: el widget crece y se reduce segun la cantidad de eventos visibles.
- Clic en toda la tarjeta abre el evento; se elimina el enlace textual "Abrir evento".
- Notificacion persistente (--expire-time=0) para los eventos de hoy.
- Resaltado por fecha con opacidad relativa: hoy -25%, proximos 2 dias -15%.

## v0.1.6

- Dependencias de Google API movidas a un entorno virtual interno (`--system-site-packages`) que hereda PyQt6 del sistema; se elimina el uso de `pip --user`, incompatible con entornos PEP 668.
- El lanzador resuelve el intérprete del venv y delega el estado del token a `core.auth` (códigos 10/11/20 requieren terminal; 30 = red/DNS permite arrancar en modo caché).
- Soporte multi-terminal en el lanzador (`xfce4-terminal`, `mate-terminal`, `gnome-terminal`, `tilix`, `x-terminal-emulator`).
- Integrado el `AuthDialog` nativo en la opcion "Refresh Token" del menu; se implementa `complete_manual_auth` y `init_manual_auth`, eliminando el import roto.
- Normalizada la configuracion: clave unica `refresh_interval`, migracion de `refresh_interval_minutes` y saneamiento de rangos (max_events 1-8).
- El limite de eventos de `CalendarClient` respeta ahora el maximo configurable de la UI (8) en vez de fijarse a 5.
- Instalador y paquete `.deb` construyen el venv en postinst; control actualizado a `python3-pyqt6`.
- Añadida infraestructura de desarrollo: `pyproject.toml`, `requirements-dev.txt`, Ruff, mypy y suite de pruebas.

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
