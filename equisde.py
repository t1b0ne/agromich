import random
import time
from playwright.sync_api import sync_playwright

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfkyIgC1Stqr6RsnE9I_x8b0Tlkz8sarw8NJZ08i0-OstvIuQ/viewform?usp=publish-editor"

def responder_aleatorio(page):
    # 1. Inputs de texto corto o largo
    text_inputs = page.locator('input[type="text"]:not([aria-hidden="true"]), textarea')
    count_text = text_inputs.count()
    
    respuestas_ejemplo = ["Opción A", "Texto aleatorio", "Ejemplo", "Prueba"]
    for i in range(count_text):
        input_elem = text_inputs.nth(i)
        if input_elem.is_visible():
            input_elem.fill(random.choice(respuestas_ejemplo))

    # 2. Preguntas de Selección Única (Radio Buttons)
    # Agrupamos por cada contenedor de pregunta
    radio_groups = page.locator('div[role="radiogroup"]')
    count_radios = radio_groups.count()
    
    for i in range(count_radios):
        group = radio_groups.nth(i)
        # Obtenemos todas las opciones disponibles en esta pregunta
        opciones = group.locator('div[role="radio"]')
        num_opciones = opciones.count()
        if num_opciones > 0:
            # Elegimos un índice al azar
            eleccion = random.randint(0, num_opciones - 1)
            opciones.nth(eleccion).click()

    # 3. Preguntas de Casillas de Verificación (Checkboxes)
    # En las casillas se puede elegir una o varias opciones al azar
    checkbox_groups = page.locator('div[role="list"]')
    count_checkboxes = checkbox_groups.count()
    
    for i in range(count_checkboxes):
        group = checkbox_groups.nth(i)
        opciones = group.locator('div[role="checkbox"]')
        num_opciones = opciones.count()
        if num_opciones > 0:
            # Seleccionar entre 1 y N opciones al azar
            k = random.randint(1, num_opciones)
            indices_elegidos = random.sample(range(num_opciones), k)
            for idx in indices_elegidos:
                opciones.nth(idx).click()

    # 4. Hacer clic en el botón Enviar
    boton_enviar = page.locator('div[role="button"]:has-text("Enviar"), div[role="button"]:has-text("Submit")')
    if boton_enviar.count() > 0:
        boton_enviar.first.click()
        print("Formulario enviado con opciones aleatorias.")


def ejecutar_bucle(envios=5):
    with sync_playwright() as p:
        # Poner headless=True si no quieres que se abra la ventana del navegador
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        for i in range(envios):
            print(f"--- Procesando envío {i + 1}/{envios} ---")
            page = context.new_page()
            page.goto(FORM_URL)
            
            # Esperar a que cargue la estructura del formulario
            page.wait_for_selector('form')
            
            # Detectar y responder
            responder_aleatorio(page)
            
            time.sleep(2)  # Pausa breve entre envíos
            page.close()
            
        browser.close()

if __name__ == "__main__":
    ejecutar_bucle(envios=3)