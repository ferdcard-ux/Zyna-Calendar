# Changelog

## 0.1.8

- Nuevo sistema de actualizaciones integrado: se consulta la release mas reciente en GitHub y se descarga el paquete `.deb` con barra de progreso.
- La descarga verifica el digest SHA-256 cuando la release publica el archivo `<paquete>.sha256`; si no existe, se muestran los datos reales calculados localmente.
- Nueva pestana "Actualizar" en configuracion: repositorio `owner/repo` (vacio = desactivado) y comprobacion automatica cada 12 horas y al iniciar.
- Nueva opcion de menu "Buscar actualizaciones" y notificacion de escritorio cuando hay una version mas reciente.
- Instalacion con `pkexec dpkg -i` desde el dialogo; la app avisa de reiniciar para aplicar el cambio.
- Corregido el limite de eventos: el widget vuelve a leer `max_events` en cada sincronizacion, por lo que los cambios se aplican sin reiniciar.

## 0.1.7

- "Salir" fuerza ahora un cierre total de la aplicacion (detiene timers e hilos) en vez de solo ocultar la ventana.
- Nueva opcion "Minimizar": oculta el widget y deja un icono compacto arrastrable por el escritorio; doble clic lo restaura.
- Nueva pestana "Apariencia" en configuracion: slider de transparencia con minimo seguro (30%), 7 temas preconfigurados mas tema personalizado con colores HEX y aviso de contraste Fondo/Tarjetas/Texto (WCAG).
- La opacidad configurada se aplica al fondo, las tarjetas y los menus; el texto conserva contraste legible automaticamente.
- Autoajuste dinamico del tamano: el widget crece y se encoge segun el numero de eventos visibles.
- Clic en cualquier punto de una tarjeta abre el evento en el navegador; se elimina el enlace textual "Abrir evento".
- Notificacion persistente (no expira) para los eventos de hoy.
- Resaltado por fecha: las tarjetas de eventos dentro de 2 dias usan 15% menos de opacidad y las de hoy 25% menos.

## 0.1.6

- Dependencias de Google API movidas a un entorno virtual interno (`--system-site-packages`) que hereda PyQt6 del sistema; se elimina el uso de `pip --user`, incompatible con entornos PEP 668.
- El lanzador resuelve el intérprete del venv y delega el estado del token a `core.auth` (códigos 10/11/20 requieren terminal; 30 = red/DNS permite arrancar en modo caché).
- Soporte multi-terminal en el lanzador (`xfce4-terminal`, `mate-terminal`, `gnome-terminal`, `tilix`, `x-terminal-emulator`).
- Integrado el `AuthDialog` nativo en la opcion "Refresh Token" del menu; se implementa `complete_manual_auth` y `init_manual_auth`, eliminando el import roto.
- Normalizada la configuracion: clave unica `refresh_interval`, migracion de `refresh_interval_minutes` y saneamiento de rangos (max_events 1-8).
- El limite de eventos de `CalendarClient` respeta ahora el maximo configurable de la UI (8) en vez de fijarse a 5.
- Instalador y paquete `.deb` construyen el venv en postinst; control actualizado a `python3-pyqt6`.
- Añadida infraestructura de desarrollo: `pyproject.toml`, `requirements-dev.txt`, Ruff, mypy y suite de pruebas.

## 0.1.5

- La terminal de autenticacion ya no mantiene viva la app como proceso hijo.
- Tras autenticar correctamente, Zyna Calendar se lanza desacoplado y la terminal muestra "Presione Enter para salir".
- Cerrar la terminal despues de autenticar ya no cierra el widget.

## 0.1.4

- El lanzador ahora detecta tokens revocados antes del arranque y abre la terminal de reautorizacion cuando hace falta.
- Se evita que la app quede silenciosa al iniciarse desde el menu con credenciales vencidas.

## 0.1.3

- La app ahora distingue de forma visible entre sincronizacion normal, uso de cache y autenticacion vencida.
- Se muestra la antiguedad de la ultima sincronizacion real con Google cuando los eventos provienen de cache.
- La UI eleva una advertencia persistente y una notificacion cuando la sincronizacion requiere atencion.
- El flujo de autenticacion fuerza reautorizacion limpia cuando Google revoca el refresh token.

## 0.1.2

- Instalador refuerza dependencias con pip --user y valida imports.
- Opcion "Refresh Token" para reautorizar y verificar conexion.
- Script de desinstalacion interactivo incluido.
- Documentacion actualizada con la nueva instalacion y desinstalacion.

## 0.1.1

- Correccion de autenticacion offline para evitar apertura de navegador sin conexion.
- Ajustes de dependencias del .deb para compatibilidad en Zorin Lite.
- Flujo de autenticacion manual unificado con guardado del refresh_token.
- Launcher detecta primera ejecucion y abre terminal solo si falta token.

## 0.1.0

- Base funcional del widget con OAuth2 y Google Calendar API.
- UI frameless, arrastrable y con estilo Zorin Dark Blue.
- Sincronizacion en segundo plano con cache local.
- Notificaciones nativas para eventos proximos.
- Dialogo de configuracion y menu de acciones.
- Script de instalacion y estructura de empaquetado .deb.
- Documentacion extendida con instalacion recomendada y resolucion de dependencias.
