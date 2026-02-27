from app import app
from waitress import serve
import webbrowser
import socket
import sys
from pathlib import Path

def base_dir():
    """Detecta se está rodando como .py ou como .exe via PyInstaller"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)  # pasta temporária usada pelo PyInstaller
    return Path(__file__).parent

if __name__ == "__main__":
    port = 5000

    # Descobre todos os IPs da máquina
    hostname = socket.gethostname()
    ips = socket.gethostbyname_ex(hostname)[2]

    print("🚀 Servidor rodando nos seguintes endereços:")
    for ip in ips:
        print(f"  -> http://{ip}:{port}")

    # Abre o navegador no primeiro IP encontrado
    if ips:
        url = f"http://{ips[0]}:{port}"
        print(f"🌐 Abrindo navegador em {url}")
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"⚠️ Não foi possível abrir o navegador: {e}")

    # Serve em todas as interfaces
    serve(app, host="0.0.0.0", port=port)
