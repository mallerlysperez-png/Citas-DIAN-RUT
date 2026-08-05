"""
verificar_citas.py

Este es el programa principal de la automatizacion. Cada vez que se
ejecuta (GitHub Actions lo hara cada 10-15 minutos), hace lo siguiente:

1. Abre un navegador invisible con Playwright.
2. Entra al portal de agendamiento de citas de la DIAN.
3. Repite la misma secuencia de clics que haria una persona:
   Agendar cita -> Persona Natural -> Videoatencion -> RUT y orientacion TAC
4. Revisa el resultado:
   - Si aparece el mensaje de "no se encontraron especialidades", NO hay
     disponibilidad. No se envia ningun mensaje a Slack.
   - Si el sistema permite avanzar (no aparece ese mensaje), SI hay
     disponibilidad. Se envia un mensaje a Slack de inmediato.
   - Si algo sale mal tecnicamente (la pagina no carga, un boton no
     aparece, etc), se guarda una captura de pantalla como evidencia y
     se envia un mensaje de alerta distinto, avisando que la
     automatizacion necesita revision.

Nada de esto intenta resolver ni evadir controles de seguridad (como un
reCAPTCHA). Si alguno aparece, simplemente se trata como un error tecnico
mas, se registra, y el programa termina esa ejecucion sin insistir.
"""

from playwright.sync_api import sync_playwright
import os
import sys
import time
import random
import requests

# -----------------------------------------------------------------------
# Configuracion general
# -----------------------------------------------------------------------

URL_PORTAL = "https://agendamiento.dian.gov.co/"

# La direccion secreta de Slack se lee de una variable de entorno, nunca
# se escribe directamente en el codigo. GitHub Actions se encarga de
# poner este valor a partir de un "Secret" que configuraremos mas
# adelante.
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()

CARPETA_EVIDENCIA = "evidencia"
os.makedirs(CARPETA_EVIDENCIA, exist_ok=True)

# Este es el texto exacto que vimos aparecer cuando NO hay citas
# disponibles. Si el portal cambia este mensaje en el futuro, este es el
# lugar donde habria que actualizarlo.
TEXTO_SIN_DISPONIBILIDAD = "No se encontraron especialidades"


# -----------------------------------------------------------------------
# Funciones de apoyo
# -----------------------------------------------------------------------

def enviar_mensaje_slack(mensaje):
    """
    Envia un mensaje de texto simple al canal de Slack configurado,
    usando el Incoming Webhook. Si por alguna razon no hay una direccion
    configurada, solo lo avisa en los logs y sigue (no rompe el programa).
    """
    if not SLACK_WEBHOOK_URL:
        print("AVISO: no hay SLACK_WEBHOOK_URL configurado. No se envio nada a Slack.")
        print(f"(El mensaje que se hubiera enviado era: {mensaje})")
        return

    try:
        respuesta = requests.post(
            SLACK_WEBHOOK_URL,
            json={"text": mensaje},
            timeout=15,
        )
        if respuesta.status_code != 200:
            print(f"Slack respondio con un codigo inesperado: {respuesta.status_code} - {respuesta.text}")
    except Exception as error:
        print(f"No se pudo enviar el mensaje a Slack: {error}")


def guardar_captura(pagina, nombre_archivo):
    """Guarda una captura de pantalla de la pagina actual, sin interrumpir
    el programa si algo falla al guardarla."""
    try:
        ruta = os.path.join(CARPETA_EVIDENCIA, nombre_archivo)
        pagina.screenshot(path=ruta, full_page=True)
        print(f"Captura de evidencia guardada en: {ruta}")
    except Exception as error:
        print(f"No se pudo guardar la captura de pantalla: {error}")


TAMANO_MINIMO_PIXELES = 10  # ancho y alto minimos para considerar un elemento "real"


def _buscar_coincidencia_visible(pagina, texto, tiempo_espera_ms):
    """
    El portal de la DIAN dibuja varias copias del mismo texto en la
    pagina (por ejemplo, copias pensadas para lectores de pantalla, que
    tecnicamente son "visibles" pero miden 1 pixel o estan fuera de la
    pantalla). Esta funcion revisa TODAS las coincidencias de un texto,
    una y otra vez durante el tiempo de espera indicado, y descarta las
    que sean visibles pero demasiado pequenas para ser el boton real que
    una persona veria y presionaria. Devuelve la primera coincidencia que
    de verdad parezca un elemento usable, o None si se agoto el tiempo.
    """
    limite = time.time() + (tiempo_espera_ms / 1000)
    intento = 0
    while time.time() < limite:
        intento += 1
        candidatos = pagina.get_by_text(texto, exact=False).all()
        total = len(candidatos)
        visibles_pequenos = 0

        for candidato in candidatos:
            try:
                if not candidato.is_visible():
                    continue
                caja = candidato.bounding_box()
                if caja is None:
                    continue
                if caja["width"] < TAMANO_MINIMO_PIXELES or caja["height"] < TAMANO_MINIMO_PIXELES:
                    visibles_pequenos += 1
                    continue
                return candidato
            except Exception:
                continue

        if intento == 1:
            print(
                f"  (buscando '{texto}': {total} coincidencias totales en el DOM, "
                f"{visibles_pequenos} visibles pero demasiado pequenas para ser el boton real)"
            )
        pagina.wait_for_timeout(300)
    return None


def hacer_clic_en_texto(pagina, texto_visible, tiempo_espera_ms=15000):
    """
    Busca, entre todas las copias de un texto en la pagina, la primera
    que sea realmente visible, y hace clic en ella. Usamos texto en
    lugar de codigos tecnicos internos porque es mucho mas resistente a
    cambios pequenos de diseno en el portal.
    """
    elemento = _buscar_coincidencia_visible(pagina, texto_visible, tiempo_espera_ms)
    if elemento is None:
        raise TimeoutError(
            f"No se encontro ninguna copia VISIBLE del texto '{texto_visible}' "
            f"despues de esperar {tiempo_espera_ms / 1000:.0f} segundos."
        )
    elemento.click()


def aparece_texto(pagina, texto_a_buscar, tiempo_espera_ms=10000):
    """
    Revisa si un texto especifico aparece visible en la pagina, esperando
    hasta 'tiempo_espera_ms' milisegundos. Devuelve True/False en lugar de
    lanzar un error si no aparece (a diferencia de hacer_clic_en_texto).
    """
    return _buscar_coincidencia_visible(pagina, texto_a_buscar, tiempo_espera_ms) is not None


# -----------------------------------------------------------------------
# Logica principal: revisar el portal una vez
# -----------------------------------------------------------------------

def revisar_portal():
    """
    Ejecuta una revision completa del portal y devuelve un texto con el
    resultado: "sin_disponibilidad", "hay_disponibilidad" o "error".
    """
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=True)
        pagina = navegador.new_page()

        try:
            print(f"Abriendo el portal: {URL_PORTAL}")
            pagina.goto(URL_PORTAL, wait_until="domcontentloaded", timeout=60000)
            pagina.wait_for_timeout(3000)

            print("Paso 1: clic en 'Agendar cita'")
            hacer_clic_en_texto(pagina, "Agendar cita")
            pagina.wait_for_timeout(2000)

            # Usamos fragmentos cortos y unicos en lugar de la frase
            # completa: el portal dibuja "Persona" y "Natural" (o "RUT" y
            # "orientacion TAC") en lineas separadas dentro de la misma
            # tarjeta, asi que buscar la frase completa con espacio nunca
            # encuentra nada. Elegimos una palabra que no se repita en
            # ninguna otra parte de la pagina (por ejemplo, el pie de
            # pagina) para no hacer clic en el lugar equivocado.
            print("Paso 2: clic en 'Natural' (tarjeta Persona Natural)")
            hacer_clic_en_texto(pagina, "Natural")
            pagina.wait_for_timeout(1500)

            print("Paso 3: clic en 'Videoatención'")
            hacer_clic_en_texto(pagina, "Videoatención")
            pagina.wait_for_timeout(1500)

            print("Paso 4: clic en 'RUT' (tarjeta RUT y orientación TAC)")
            hacer_clic_en_texto(pagina, "RUT")
            pagina.wait_for_timeout(3000)

            # Guardamos siempre una captura del resultado final, sin
            # importar cual haya sido, para poder revisarla despues si
            # algo se ve raro.
            guardar_captura(pagina, "resultado_ultima_revision.png")

            if aparece_texto(pagina, TEXTO_SIN_DISPONIBILIDAD, tiempo_espera_ms=8000):
                print("Resultado: SIN disponibilidad (mensaje de 'no encontrado' presente).")
                return "sin_disponibilidad"

            print("Resultado: el mensaje de 'sin disponibilidad' NO aparecio -> posible disponibilidad.")
            return "hay_disponibilidad"

        except Exception as error:
            print(f"ERROR TECNICO durante la revision: {error}")
            guardar_captura(pagina, "error_ultima_revision.png")
            return "error"

        finally:
            navegador.close()


# -----------------------------------------------------------------------
# Punto de entrada del programa
# -----------------------------------------------------------------------

def main():
    # Pequena espera aleatoria (entre 0 y 45 segundos) para que la
    # ejecucion no ocurra siempre en el segundo exacto programado, y el
    # patron de trafico se parezca un poco mas al de una persona.
    espera_inicial = random.randint(0, 45)
    print(f"Esperando {espera_inicial} segundos antes de empezar (variacion normal)...")
    time.sleep(espera_inicial)

    resultado = revisar_portal()

    if resultado == "hay_disponibilidad":
        enviar_mensaje_slack(
            "🚨 Hay citas virtuales disponibles en la DIAN para RUT de Persona Natural.\n"
            "Se recomienda ingresar inmediatamente al portal para agendar la cita:\n"
            "https://agendamiento.dian.gov.co/"
        )
        print("Aviso de disponibilidad enviado a Slack.")

    elif resultado == "sin_disponibilidad":
        print("Sin disponibilidad. No se envia ningun mensaje. Ejecucion normal.")

    elif resultado == "error":
        enviar_mensaje_slack(
            "⚠️ La automatización de citas DIAN tuvo un error técnico en esta "
            "revisión (por ejemplo, el portal no respondió como se esperaba, o "
            "apareció un control de seguridad). Revisa los registros y la "
            "captura de pantalla en la pestaña Actions de GitHub."
        )
        # Terminamos con un codigo de salida distinto de cero para que
        # GitHub marque esta ejecucion como "fallida" en su historial,
        # ademas del aviso que ya enviamos a Slack.
        sys.exit(1)


if __name__ == "__main__":
    main()
