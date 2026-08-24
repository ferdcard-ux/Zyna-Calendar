# Plan Técnico de Mejoras V2 — Zyna Calendar

**Fecha:** 2026-08-23
**Versión objetivo:** 0.2.0
**Alcance:** Diagnóstico completo del fallo de ejecución y plan de mejoras por fases.

---

## 1. Contexto

La aplicación instalada (`/opt/zyna-calendar`) no arranca. El launcher
(`/usr/bin/zyna-calendar`) ejecuta una sonda de autenticación que devuelve el
estado `revoked` (código de salida 20) porque el refresh token de Google fue
revocado:

```
google.auth.exceptions.RefreshError:
('invalid_grant: Token has been expired or revoked.', ...)
```

## 2. Causas raíz identificadas

| ID  | Problema | Ubicación | Severidad |
|-----|----------|-----------|-----------|
| A   | **Flujo OAuth OOB deprecado.** Google retiró el flujo `urn:ietf:wg:oauth:2.0:oob` en 2023. Toda re-autorización manual (terminal y diálogo gráfico) depende de este flujo roto. | `core/auth.py` (`init_manual_auth`) | Crítica |
| B   | **Refresh tokens efímeros.** Con el Consent Screen en modo *Testing*, Google expira los refresh tokens cada 7 días, provocando revocaciones periódicas. | Config GCP (no código) | Crítica |
| C   | **Credenciales obsoletas tras re-auth.** `CalendarClient` construye el servicio una sola vez con las credenciales del arranque. Al renovar el token con el diálogo gráfico, el nuevo token se persiste pero el cliente sigue usando las credenciales viejas hasta reiniciar. | `core/calendar_service.py` (`_get_service`), `main.py` | Alta |
| D   | **Errores de red tratados como revocación.** Un fallo transitorio de red durante el refresh fuerza una re-autorización completa innecesaria. | `core/auth.py` (`load_google_credentials`) | Media |

## 3. Plan de mejoras por fases

### Fase 0 — Hotfix (resuelve el fallo de ejecución)

1. **Migrar OAuth OOB → Loopback IP.**
   - Nueva función `run_loopback_auth()` basada en `InstalledAppFlow.run_local_server(port=0)`
     para entornos gráficos (abre navegador y captura el código automáticamente).
   - El flujo manual copy/paste pasa a usar `http://localhost:1` como redirect URI
     (Google lo admite si existe al menos una URI localhost registrada en GCP).
   - Requisito administrativo: registrar `http://localhost` como URI autorizada en
     Google Cloud Console → Credentials → Authorized redirect URIs.
2. **Publicar el Consent Screen en modo Production** (o Internal) en GCP para
   eliminar la caducidad de 7 días de los refresh tokens.
3. **Invalidación de credenciales tras re-auth.**
   - `CalendarClient.invalidate()` limpia servicio y credenciales cacheadas;
     la siguiente sincronización recarga el token desde disco.
   - El widget llama `invalidate()` cuando el diálogo de autorización termina con éxito.
4. **Distinguir red vs revocación en `load_google_credentials`.**
   - Ante error no-`RefreshError` (red/DNS/timeout) durante el refresh se devuelven
     las credenciales cacheadas (la sync caerá a modo caché) en lugar de forzar re-auth.

### Fase 1 — Robustez

5. **Escritura atómica de archivos de configuración** (`settings.json`,
   `events_cache.json`): escritura a archivo temporal + `os.replace()` para evitar
   corrupción ante cortes de energía.
6. **Tolerancia a JSON corrupto:** `load_settings()` respalda el archivo dañado y
   retorna los valores por defecto en lugar de lanzar excepción.
7. **Permisos `0600` en `token.json`** (contiene client_secret y refresh_token).
8. **Log rotativo:** `RotatingFileHandler` (512 KB × 2 copias) en `configure_logging()`.
9. **Fallback a caché en la ruta de error del widget:** `EventSyncThread` emite la
   excepción y `CalendarClient.fallback_result(error)` permite renderizar eventos
   cacheados también cuando la señal `sync_failed` se dispara.

### Fase 2 — Calidad y mantenimiento

10. **Timezone del sistema:** resolver la zona desde `/etc/localtime` con
    `America/Bogota` como fallback (elimina el hardcodeo).
11. **Persistir IDs de eventos notificados hoy** (`notified_state.json`) para no
    re-emitir notificaciones persistentes tras reiniciar la app.
12. **UI consistente:** color del botón hamburguesa tomado del tema activo;
    unificación de tildes y textos.
13. **Empaquetado de fuente única:** `build_deb/build.sh` ya genera `pkgroot` desde
    la raíz; se excluyen del repositorio los binarios `.deb` y `pkgroot/`
    (`.gitignore`) y se sincroniza `VERSION` con `APP_VERSION`.

## 4. Verificación de calidad (QA gate)

Todo cambio debe pasar el siguiente gate antes de considerarse completo:

```bash
# Desde la raíz del proyecto (usa el venv interno o el del sistema):
./venv/bin/python3 -m pytest tests/          # Suite de pruebas (66 tests)
./venv/bin/python3 -m ruff check .           # Linting (E,F,W,I,UP,B,SIM)
./venv/bin/python3 -m mypy                   # Tipado estricto (disallow_untyped_defs)
```

Herramientas declaradas en `requirements-dev.txt`:

| Herramienta | Versión mínima | Configuración |
|-------------|----------------|---------------|
| pytest      | ≥ 8.0 (+ pytest-mock) | `[tool.pytest.ini_options]` en `pyproject.toml` |
| ruff        | ≥ 0.9          | `[tool.ruff]` en `pyproject.toml` |
| mypy        | ≥ 1.13         | `[tool.mypy]` en `pyproject.toml` |

Reglas del gate:
- `ruff check` sin errores (código de salida 0).
- `mypy` sin errores sobre `main.py`, `core/`, `ui/`, `utils/`.
- `pytest` 100 % verde. Toda corrección de bug debe incluir un test de regresión.

## 5. Matriz de riesgos

| Riesgo | Mitigación |
|--------|------------|
| Usuario sin navegador en el host (SSH/headless) | Fallback automático al flujo copy/paste con `http://localhost:1` |
| Puerto de loopback ocupado | `run_local_server(port=0)` elige un puerto efímero libre |
| Corrupción de settings/token | Escritura atómica + respaldo del archivo corrupto |
| Regresión en tests existentes | QA gate obligatorio (sección 4) |

## 6. Criterios de aceptación

- [ ] `zyna-calendar` arranca con token válido sin abrir terminal.
- [ ] Ante token revocado, la re-autorización funciona desde la GUI (loopback)
      y desde terminal (copy/paste) sin depender del flujo OOB.
- [ ] Tras renovar el token desde el menú, la app sincroniza **sin reiniciar**.
- [ ] Corte de red durante el arranque inicia la app en modo caché, sin terminal de auth.
- [ ] QA gate verde: pytest + ruff + mypy.
