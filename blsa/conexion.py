"""
conexion.py — Conexión y verificación de cuenta MT5
"""

import MetaTrader5 as mt5
import sys

MT5_LOGIN    = 10010390946
MT5_PASSWORD = "K!Ks1pHn"
MT5_SERVER   = "MetaQuotes-Demo"


def conectar() -> bool:
    """Inicia y verifica la conexión con MetaTrader 5."""
    if not mt5.initialize():
        print(f"[ERROR] No se pudo inicializar MT5: {mt5.last_error()}")
        return False

    ok = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not ok:
        print(f"[ERROR] Login fallido: {mt5.last_error()}")
        mt5.shutdown()
        return False

    print("[OK] Conectado a MetaTrader 5")
    return True


def mostrar_cuenta() -> None:
    """Imprime balance, equity y margen de la cuenta."""
    info = mt5.account_info()
    if info is None:
        print(f"[ERROR] No se pudo obtener info de cuenta: {mt5.last_error()}")
        return

    print("=" * 40)
    print(f"  Cuenta   : {info.login}")
    print(f"  Servidor : {info.server}")
    print(f"  Moneda   : {info.currency}")
    print(f"  Balance  : {info.balance:,.2f}")
    print(f"  Equity   : {info.equity:,.2f}")
    print(f"  Margen   : {info.margin:,.2f}")
    print(f"  Libre    : {info.margin_free:,.2f}")
    print(f"  Nivel M. : {info.margin_level:.2f}%" if info.margin_level else "  Nivel M. : N/A")
    print(f"  Apalanca.: 1:{info.leverage}")
    print("=" * 40)


def desconectar() -> None:
    mt5.shutdown()
    print("[OK] Desconectado de MT5")


if __name__ == "__main__":
    if not conectar():
        sys.exit(1)
    mostrar_cuenta()
    desconectar()
