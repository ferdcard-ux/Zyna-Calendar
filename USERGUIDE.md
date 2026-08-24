# Guia de Usuario

## Primer inicio

1. Crea un proyecto en Google Cloud Console y habilita Google Calendar API.
2. Genera un cliente OAuth de tipo Desktop app.
3. Descarga `credentials.json` y configura su ruta desde el menu (Configuracion).
4. En el primer inicio la app abrira tu navegador para autorizar el acceso (loopback). Si Google muestra el aviso "app no verificada", usa Continuar > Avanzado > Ir a Zyna Calendar.
5. Al aceptar, la app guarda el token y arranca sola. En equipos sin navegador se muestra una URL y un campo para pegar el codigo manualmente.

## Menu principal

- Sync Manual: actualiza los eventos inmediatamente.
- Refresh Token: reautoriza el acceso abriendo tu navegador (sin reiniciar la app) y valida la conexion con Google.
- Configuracion: ajusta eventos, intervalos, credenciales, apariencia y actualizaciones.
- Buscar actualizaciones: consulta la release mas reciente en GitHub y permite descargar e instalar el nuevo `.deb`.
- Info: informacion basica del widget.
- Reiniciar Applet: reinicia la aplicacion.
- Minimizar: oculta el widget y deja un icono compacto en el escritorio. Arrastra el icono para moverlo; doble clic restaura la ventana.
- Salir: cierra la aplicacion por completo.

## Actualizaciones

Desde la pestana "Actualizar" (Configuracion):

- **Repositorio**: indica el slug `owner/repo` de GitHub donde se publican las releases (vacio desactiva las actualizaciones).
- **Comprobacion automatica**: al activarla, la app revisa cada 12 horas y al iniciar; si hay una version mas reciente se muestra una notificacion.
- **Buscar actualizaciones ahora**: abre el dialogo que muestra las notas de la release, descarga el paquete `.deb` con barra de progreso y verifica su SHA-256 cuando la release publica el digest.
- La instalacion pide permisos de administrador (`pkexec`) y avisa de reiniciar la aplicacion para aplicar el cambio.

## Apariencia

Desde la pestana "Apariencia" (Configuracion) puedes personalizar el widget:

- **Transparencia**: un slider con minimo seguro de 30% para mantener el texto legible.
- **Tema**: 7 temas preconfigurados (Clasico Azul, Medianoche Violeta, Bosque Verde, Oceano Azul, Llamarada Naranja, Rosa Suave y Grafito Neutro).
- **Personalizado**: define colores HEX para Fondo, Tarjetas, Texto y Acento.
- El cuadro de contraste avisa si el texto no destacara sobre el fondo; si el contraste es insuficiente, la app usa texto blanco o negro legible automaticamente.

## Intervalo de sincronizacion

Desde Configuracion puedes definir el intervalo en minutos.

- 0 desactiva la sincronizacion automatica.
- Un valor mayor que 0 actualiza automaticamente el calendario.

## Modo sin conexion

Si no hay red disponible, Zyna-Calendar mostrara los ultimos eventos guardados en cache y un mensaje sutil de estado.

## Autenticacion persistente

El archivo `~/.config/zyna-calendar/token.json` guarda el `refresh_token`. Mientras no se elimine ni sea revocado por Google, la app no solicitara el codigo otra vez despues de reiniciar el sistema.

## Notificaciones

- Se envia una notificacion cuando falta menos de 10 minutos para el proximo evento.
- Los eventos de hoy reciben una notificacion persistente (no expira) que queda en pantalla hasta que la cierres.
- Requiere `notify-send` (paquete `libnotify-bin`).

## Tarjetas de eventos

- Clic en cualquier punto de una tarjeta abre el evento en el navegador.
- La cercania se refleja en la visibilidad: las tarjetas de eventos de hoy suman 25% de opacidad sobre la base y las de los proximos 2 dias suman 15% (tope 100%), destacandose sobre el resto.

## Instalacion con .deb

Opcion recomendada (resuelve dependencias automaticamente):

```bash
sudo apt install ./build_deb/zyna-calendar_0.2.0_all.deb
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

Pregunta si deseas desinstalar el applet (removiendo el paquete `.deb` si esta instalado, el autostart y el entorno virtual) y eliminar los datos locales (cache, token y settings).
