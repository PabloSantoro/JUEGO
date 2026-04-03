"""
main.py — Sistema de trading BLSA
Corre el análisis cada 60 segundos y opera automáticamente según señales.
"""

import time
import sys
from datetime import datetime

from conexion import conectar, mostrar_cuenta, desconectar
from analisis import obtener_simbolo, mostrar_analisis
from operaciones import abrir_orden, mostrar_posiciones

INTERVALO_SEGUNDOS = 60
OPERAR_AUTO        = False   # Cambiar a True para operar automáticamente


def ciclo(simbolo: str) -> None:
    """Un ciclo de análisis (y operación opcional)."""
    resultado = mostrar_analisis(simbolo)
    if not resultado:
        return

    print("\n--- Posiciones abiertas ---")
    mostrar_posiciones(simbolo)

    senal = resultado.get("senal", "NEUTRAL")

    if OPERAR_AUTO and senal in ("COMPRA", "VENTA"):
        print(f"\n[BOT] Señal detectada: {senal} — abriendo orden...")
        abrir_orden(simbolo, senal)
    elif senal != "NEUTRAL":
        print(f"\n[BOT] Señal: {senal} (modo manual — OPERAR_AUTO=False)")


def main() -> None:
    print("=" * 50)
    print("  BLSA Trading Bot")
    print(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Intervalo: {INTERVALO_SEGUNDOS}s  |  Auto-operar: {OPERAR_AUTO}")
    print("=" * 50)

    if not conectar():
        sys.exit(1)

    mostrar_cuenta()

    simbolo = obtener_simbolo()
    if not simbolo:
        desconectar()
        sys.exit(1)

    print(f"\n[OK] Símbolo activo: {simbolo}")
    print("[INFO] Presioná Ctrl+C para detener\n")

    try:
        while True:
            ciclo(simbolo)
            print(f"\n[ESPERA] Próximo ciclo en {INTERVALO_SEGUNDOS}s...\n")
            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        print("\n[INFO] Bot detenido por el usuario")

    finally:
        desconectar()


if __name__ == "__main__":
    main()
