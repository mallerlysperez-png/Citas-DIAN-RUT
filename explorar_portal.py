"""
explorar_portal.py

IMPORTANTE: este script todavia NO verifica citas. Su unico trabajo es
"abrir los ojos" sobre el portal real de la DIAN, para que podamos verlo
juntos antes de programar la logica final de verificacion.

Que hace, paso a paso:
1. Abre un navegador invisible (headless) usando Playwright.
2. Entra a la pagina de agendamiento de citas de la DIAN.
3. Toma una captura de pantalla de como se ve la pagina al cargar.
4. Guarda en un archivo de texto todos los botones, enlaces y opciones
   visibles en la pagina, con su texto exacto.
5. Todo esto queda guardado como "artifacts" (archivos adjuntos) de esta
   ejecucion de GitHub Actions, para que los descarguemos y los revisemos.
"""

from playwright.sync_api import sync_playwright
import os

# Carpeta donde vamos a guardar las capturas y el reporte de texto.
CARPETA_SALIDA = "reporte_exploracion"
os.makedirs(CARPETA_SALIDA, exist_ok=True)

URL_PORTAL = "https://agendamientodigiturno.dian.gov.co/frmSolicitarNuevaCita.aspx"


def listar_elementos_interactivos(page):
    """
    Recorre la pagina y devuelve una lista de texto con todos los
    elementos con los que normalmente interactuaria una persona:
    botones, enlaces, casillas, radios y opciones de listas desplegables.
    """
    lineas = []

    selectores_a_revisar = {
        "Boton": "button",
        "Enlace": "a",
        "Opcion de radio o casilla": "input",
        "Elemento seleccionable (select)": "select",
        "Opcion dentro de un select": "option",
    }

    for etiqueta, selector_css in selectores_a_revisar.items():
        elementos = page.query_selector_all(selector_css)
        for elemento in elementos:
            try:
                texto = (elemento.inner_text() or "").strip()
            except Exception:
                texto = ""
            valor = elemento.get_attribute("value") or ""
            id_html = elemento.get_attribute("id") or ""
            if texto or valor:
                lineas.append(
                    f"[{etiqueta}] texto='{texto}' value='{valor}' id='{id_html}'"
                )

    return lineas


def main():
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=True)
        pagina = navegador.new_page()

        print(f"Abriendo el portal: {URL_PORTAL}")
        pagina.goto(URL_PORTAL, wait_until="networkidle", timeout=60000)

        # Captura de pantalla de la pagina tal como carga inicialmente.
        ruta_captura_inicial = os.path.join(CARPETA_SALIDA, "01_pagina_inicial.png")
        pagina.screenshot(path=ruta_captura_inicial, full_page=True)
        print(f"Captura guardada en: {ruta_captura_inicial}")

        # Reporte de texto con todos los elementos interactivos encontrados.
        elementos = listar_elementos_interactivos(pagina)
        ruta_reporte = os.path.join(CARPETA_SALIDA, "01_elementos_encontrados.txt")
        with open(ruta_reporte, "w", encoding="utf-8") as archivo:
            archivo.write("\n".join(elementos))
        print(f"Reporte de elementos guardado en: {ruta_reporte}")

        navegador.close()


if __name__ == "__main__":
    main()
