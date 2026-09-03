import os
import subprocess
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from rich.align import Align

console = Console()

def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def obtener_logs_recientes():
    """Busca los archivos JSON más recientes en la carpeta reports/ para los logs del sistema."""
    logs = []
    ruta_reports = "reports"
    if os.path.exists(ruta_reports):
        for root, _, files in os.walk(ruta_reports):
            for file in files:
                if file.endswith(".json"):
                    ruta_completa = os.path.join(root, file)
                    tiempo_mod = os.path.getmtime(ruta_completa)
                    logs.append((tiempo_mod, file, root))
        
        logs.sort(key=lambda x: x[0], reverse=True)
        
    if not logs:
        return "[dim]No hay actividad o reportes registrados todavía en reports/.[/dim]"
    
    lineas_log = []
    # Toma hasta los últimos 8 registros para aprovechar la pantalla completa
    for _, archivo, carpeta in logs[:8]:
        lineas_log.append(f"[green]✔ [REGISTRO][/green] [cyan]{archivo}[/cyan] [dim]({carpeta})[/dim]")
    
    return "\n".join(lineas_log)

def construir_interfaz():
    """Construye un layout responsivo que abarca toda la pantalla de la terminal."""
    layout = Layout()

    # Dividir la pantalla principal en secciones verticales proporcionales
    layout.split(
        Layout(name="header", size=7),
        Layout(name="body", ratio=2),
        Layout(name="logs", ratio=3)
    )

    # 1. Sección Superior: Banner del Sistema
    banner_texto = "[bold green]AgroMich v2.0[/bold green] | [cyan]Inteligencia Territorial y Agronómica (Hermes & Eve)[/cyan]"
    layout["header"].update(Panel(Align.center(banner_texto, vertical="middle"), border_style="green", title="Estado del Sistema"))

    # 2. Sección Central: Tabla de Menú de Opciones
    table = Table(title="Menú de Control Principal - AgroMich", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Opción", style="cyan", justify="center", width=8)
    table.add_column("Módulo / Acción", style="green", width=30)
    table.add_column("Descripción", style="yellow")

    table.add_row("1", "Encender API Modular", "Inicia el servidor FastAPI (app.main) para los agentes")
    table.add_row("2", "Ejecutar Extractor Suelo (SIAP)", "Prueba el scraper de suelo directamente por CLI")
    table.add_row("3", "Verificar Estado de Entorno", "Comprueba librerías clave instaladas")
    table.add_row("4", "Verificar Estructura reports/", "Muestra los respaldos JSON almacenados")
    table.add_row("0", "Salir", "Cerrar la aplicación TUI")

    layout["body"].update(Panel(table, border_style="magenta", padding=(0, 1)))

    # 3. Sección Inferior: Logs dinámicos expandidos
    texto_logs = obtener_logs_recientes()
    layout["logs"].update(Panel(
        texto_logs,
        title="[bold yellow]📜 Logs del Sistema / Actividad Reciente en Reports[/bold yellow]",
        border_style="blue",
        padding=(1, 2)
    ))

    return layout

def menu_principal():
    while True:
        limpiar_pantalla()
        
        # Renderiza el layout responsivo adaptado al alto y ancho actual de la terminal
        console.print(construir_interfaz())
        
        opcion = Prompt.ask("\n[bold cyan]Selecciona una opción[/bold cyan]", choices=["0", "1", "2", "3", "4"], default="1")

        if opcion == "1":
            limpiar_pantalla()
            console.print("\n[bold yellow]--> Iniciando servidor FastAPI (Arquitectura Modular)...[/bold yellow]")
            console.print("[dim]Presiona CTRL+C en la terminal si deseas detener el servidor y regresar al menú.[/dim]\n")
            try:
                subprocess.run([sys.executable, "-m", "app.main"])
            except KeyboardInterrupt:
                console.print("\n[bold red]Servidor detenido por el usuario.[/bold red]")
            Prompt.ask("\nPresiona [bold cyan]Enter[/bold cyan] para volver al menú...")

        elif opcion == "2":
            limpiar_pantalla()
            console.print("\n[bold yellow]--> Ejecutando Extractor SIAP (Suelo y Socioeconómico)...[/bold yellow]")
            estado = Prompt.ask("Ingresa el estado a consultar", default="Michoacán")
            try:
                script_path = os.path.join("app", "services", "servicio_suelo.py")
                subprocess.run([sys.executable, script_path, "--estado", estado, "--tipo", "municipio"])
            except Exception as e:
                console.print(f"[bold red]Error al ejecutar el script: {e}[/bold red]")
            Prompt.ask("\nPresiona [bold cyan]Enter[/bold cyan] para volver al menú...")

        elif opcion == "3":
            limpiar_pantalla()
            console.print("\n[bold green]=== Verificación de Dependencias del Entorno ===[/bold green]")
            paquetes = ["fastapi", "uvicorn", "selenium", "bs4", "pandas", "rich"]
            for pkg in paquetes:
                try:
                    __import__(pkg)
                    console.print(f" [✓] {pkg}: [green]Instalado correctamente[/green]")
                except ImportError:
                    console.print(f" [!] {pkg}: [red]No encontrado (Falta instalar)[/red]")
            Prompt.ask("\nPresiona [bold cyan]Enter[/bold cyan] para volver al menú...")

        elif opcion == "4":
            limpiar_pantalla()
            console.print("\n[bold green]=== Estado detallado de la carpeta reports/ ===[/bold green]")
            ruta_reports = "reports"
            if os.path.exists(ruta_reports):
                for root, dirs, files in os.walk(ruta_reports):
                    indent = "  " * (root.count(os.sep) - 1)
                    console.print(f"{indent}[bold blue]📁 {os.path.basename(root)}/[/bold blue]")
                    for file in files:
                        if file.endswith(".json"):
                            console.print(f"{indent}    📄 {file}")
            else:
                console.print("[yellow]La carpeta 'reports' aún no ha generado archivos o no existe.[/yellow]")
            Prompt.ask("\nPresiona [bold cyan]Enter[/bold cyan] para volver al menú...")

        elif opcion == "0":
            if Confirm.ask("\n¿Estás seguro de que deseas salir?"):
                console.print("[bold green]¡Hasta luego, Hermes y Eve siguen operando en el sistema![/bold green]")
                break

if __name__ == "__main__":
    try:
        menu_principal()
    except KeyboardInterrupt:
        console.print("\n[bold red]Aplicación finalizada abruptamente.[/bold red]")