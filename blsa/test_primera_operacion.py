"""
test_primera_operacion.py
Abre UNA operación de prueba en cuenta DEMO y muestra el resultado.
Corré este script en tu PC con Windows y MT5 instalado.
"""

import sys
from conexion import conectar, mostrar_cuenta, desconectar
from analisis import obtener_simbolo, mostrar_analisis
from operaciones import abrir_orden, mostrar_posiciones
import MetaTrader5 as mt5

def main():
    print("=" * 50)
    print("  TEST — Primera Operación DEMO")
    print("=" * 50)

    # 1. Conectar
    if not conectar():
        sys.exit(1)

    mostrar_cuenta()

    # 2. Obtener símbolo y analizar
    simbolo = obtener_simbolo()
    if not simbolo:
        desconectar()
        sys.exit(1)

    print(f"\n[SÍMBOLO] {simbolo}")
    resultado = mostrar_analisis(simbolo)

    if not resultado:
        print("[ERROR] No se pudo analizar el mercado")
        desconectar()
        sys.exit(1)

    # 3. Abrir operación de COMPRA (BUY) de prueba
    #    Independientemente de la señal — es solo un test
    print("\n[TEST] Abriendo orden de COMPRA de prueba...")
    ticket = abrir_orden(simbolo, "COMPRA", sl_pips=30, tp_pips=60)

    if ticket:
        print(f"\n[ÉXITO] Orden #{ticket} abierta correctamente")
        print("\n--- Posiciones abiertas ahora ---")
        mostrar_posiciones(simbolo)

        # Mostrar detalles de la orden
        pos = mt5.positions_get(ticket=ticket)
        if pos:
            p = pos[0]
            print(f"\n  Resumen de la operación:")
            print(f"  Ticket   : #{p.ticket}")
            print(f"  Símbolo  : {p.symbol}")
            print(f"  Tipo     : {'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL'}")
            print(f"  Volumen  : {p.volume} lotes")
            print(f"  Apertura : {p.price_open:.5f}")
            print(f"  SL       : {p.sl:.5f}")
            print(f"  TP       : {p.tp:.5f}")
            print(f"  P&L act. : {p.profit:.2f}")
    else:
        print("\n[FALLO] No se pudo abrir la orden — revisá los logs de arriba")

    desconectar()


if __name__ == "__main__":
    main()
