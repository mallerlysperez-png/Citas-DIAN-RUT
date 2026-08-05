from playwright.sync_api import sync_playwright
import os
 
# Carpeta donde vamos a guardar las capturas y el reporte de texto.
CARPETA_SALIDA = "reporte_exploracion"
os.makedirs(CARPETA_SALIDA, exist_ok=True)
 
# URL corregida: la que confirmamos navegando el sitio en vivo.
URL_PORTAL = "https://agendamiento.dian.gov.co/"
 
 
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
 
 
def listar_iframes(page):
    """
    Revisa si la pagina tiene 'iframes' (paginas incrustadas dentro de
    la pagina principal). Si el contenido real del agendamiento vive
    dentro de un iframe, necesitaremos ajustar el codigo final para
    buscar los botones ahi adentro, no en la pagina principal.
    """
    lineas = []
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        lineas.append(f"iframe encontrado -> url: {frame.url}")
    if not lineas:
        lineas.append("No se encontraron iframes. El contenido parece estar en la pagina principal.")
    return lineas
 
 
def main():
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=True)
        pagina = navegador.new_page()
 
        print(f"Abriendo el portal: {URL_PORTAL}")
        # Usamos "domcontentloaded" en lugar de "networkidle": este tipo de
        # sitios mantiene conexiones de red abiertas en segundo plano, y
        # "networkidle" podria quedarse esperando indefinidamente.
        pagina.goto(URL_PORTAL, wait_until="domcontentloaded", timeout=60000)
 
        # Primera captura: como se ve apenas carga el HTML inicial.
        ruta_captura_1 = os.path.join(CARPETA_SALIDA, "01_carga_inicial.png")
        pagina.screenshot(path=ruta_captura_1, full_page=True)
        print(f"Captura 1 guardada en: {ruta_captura_1}")
 
        # Le damos tiempo extra al JavaScript de la pagina para terminar
        # de dibujar el contenido (barras de carga, animaciones, etc).
        pagina.wait_for_timeout(8000)
 
        # Segunda captura: como se ve despues de esperar unos segundos.
        ruta_captura_2 = os.path.join(CARPETA_SALIDA, "02_despues_de_esperar.png")
        pagina.screenshot(path=ruta_captura_2, full_page=True)
        print(f"Captura 2 guardada en: {ruta_captura_2}")
 
        # Revisamos si el contenido esta dentro de un iframe.
        info_iframes = listar_iframes(pagina)
        ruta_iframes = os.path.join(CARPETA_SALIDA, "03_iframes_encontrados.txt")
        with open(ruta_iframes, "w", encoding="utf-8") as archivo:
            archivo.write("\n".join(info_iframes))
        print(f"Reporte de iframes guardado en: {ruta_iframes}")
 
        # Reporte de texto con todos los elementos interactivos de la
        # pagina principal (si el contenido esta en un iframe, esta
        # lista probablemente salga vacia o muy corta, y eso ya nos dice
        # algo importante).
        elementos = listar_elementos_interactivos(pagina)
        ruta_reporte = os.path.join(CARPETA_SALIDA, "04_elementos_encontrados.txt")
        with open(ruta_reporte, "w", encoding="utf-8") as archivo:
            archivo.write("\n".join(elementos))
        print(f"Reporte de elementos guardado en: {ruta_reporte}")
 
        navegador.close()
 
 
if __name__ == "__main__":
    main()
