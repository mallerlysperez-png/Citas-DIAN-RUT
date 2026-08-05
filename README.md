# Automatización — Citas virtuales DIAN (RUT Persona Natural)

Este proyecto revisa automáticamente, cada 10 minutos, si hay citas virtuales
disponibles en el portal de la DIAN para el trámite de RUT y orientación TAC
(Persona Natural), y avisa a un canal de Slack apenas encuentra disponibilidad.

## Cómo funciona (resumen)

Cada 10 minutos, GitHub Actions ejecuta `verificar_citas.py`. Este programa:

1. Abre un navegador invisible (Playwright + Chromium) y entra a
   `https://agendamiento.dian.gov.co/`.
2. Repite la secuencia: Agendar cita → Persona Natural → Videoatención →
   RUT y orientación TAC.
3. Si aparece el mensaje "No se encontraron especialidades...", no hay
   disponibilidad y no se envía nada.
4. Si el sistema permite avanzar (no aparece ese mensaje), sí hay
   disponibilidad, y se envía un aviso al canal de Slack configurado.
5. Si algo falla técnicamente (la página no responde como se esperaba,
   aparece un control de seguridad, etc.), se guarda una captura de
   pantalla como evidencia y se envía un aviso de error distinto a Slack.

El programa nunca intenta resolver ni evadir ningún control de seguridad
(como un reCAPTCHA). Si aparece uno, simplemente se registra como un
error técnico normal.

## Archivos del proyecto

| Archivo | Para qué sirve |
|---|---|
| `verificar_citas.py` | El programa principal: revisa disponibilidad y avisa por Slack. |
| `requirements.txt` | Lista de librerías de Python que necesita el proyecto (Playwright, requests). |
| `explorar_portal.py` | Script de diagnóstico usado durante la construcción, para "ver" el portal antes de escribir la lógica final. No es parte de la operación diaria. |
| `.github/workflows/verificar.yml` | Le dice a GitHub que ejecute `verificar_citas.py` cada 10 minutos, automáticamente. |
| `.github/workflows/explorar.yml` | Workflow manual (no programado) para volver a correr `explorar_portal.py` si alguna vez necesitamos volver a "ver" el portal (por ejemplo, si la DIAN rediseña el sitio). |
| `.github/workflows/keepalive.yml` | Hace un pequeño cambio automático una vez al mes para que GitHub no desactive por inactividad la tarea programada. |

## Cómo revisar si está funcionando

Ve a la pestaña **Actions** del repositorio. Ahí verás el historial de
cada ejecución de "Verificar citas DIAN" (cada 10 minutos), con un ✅ si
todo salió bien o un ❌ si hubo un error técnico. Haciendo clic en
cualquier ejecución puedes ver el detalle paso a paso, y en la sección
"Artifacts" (al final de la página) puedes descargar una captura de
pantalla del resultado de esa revisión específica.

## Cómo pausar o reactivar la automatización

Para pausarla temporalmente: ve a **Actions** → "Verificar citas DIAN" →
menú de tres puntos (···) → "Disable workflow".

Para reactivarla: mismo lugar → "Enable workflow".

## Cómo actualizar el aviso de Slack

Si necesitas cambiar el canal o la dirección de Slack, genera una nueva
URL de Incoming Webhook desde https://api.slack.com/apps (app existente
→ "Incoming Webhooks"), y actualiza el secreto `SLACK_WEBHOOK_URL` en
**Settings → Secrets and variables → Actions** del repositorio.

## Si la DIAN cambia su portal

Si en algún momento la automatización empieza a fallar de forma
consistente (varias ejecuciones seguidas en rojo con el mismo error),
lo más probable es que la DIAN haya cambiado el diseño de su página. Para
diagnosticarlo:

1. Ejecuta manualmente el workflow "Explorar portal DIAN (solo
   diagnóstico)" desde la pestaña Actions.
2. Descarga las capturas de pantalla y el reporte de elementos.
3. Comparte esos archivos para actualizar los textos que busca
   `verificar_citas.py` (las líneas que dicen `hacer_clic_en_texto(...)`).

## Costos

Este proyecto no tiene ningún costo mensual: el repositorio es público
(lo que da minutos ilimitados y gratis de GitHub Actions), y el aviso de
Slack usa un Incoming Webhook gratuito.
