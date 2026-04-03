"""
operaciones.py — Apertura de órdenes con gestión de riesgo
"""

from typing import Optional
import MetaTrader5 as mt5


RIESGO_PORCENTAJE = 1.0     # % del balance por operación
SL_PIPS           = 30      # Stop Loss en pips
TP_PIPS           = 60      # Take Profit en pips (ratio 1:2)
MAGIC_NUMBER      = 20240001


def calcular_lot_size(simbolo: str, sl_pips: float, riesgo_pct: float) -> float:
    """
    Calcula el lot size para que la pérdida máxima no supere riesgo_pct del balance.

    lot = (balance * riesgo%) / (sl_pips * pip_value_por_lot)
    """
    cuenta   = mt5.account_info()
    simbolo_info = mt5.symbol_info(simbolo)

    if cuenta is None or simbolo_info is None:
        print("[ERROR] No se pudo obtener info de cuenta o símbolo")
        return simbolo_info.volume_min if simbolo_info else 0.01

    balance  = cuenta.balance
    riesgo   = balance * (riesgo_pct / 100)

    # Valor de un pip en la moneda de la cuenta
    pip_size       = simbolo_info.point * 10          # 1 pip = 10 points para la mayoría
    pip_value_lot  = pip_size * simbolo_info.trade_contract_size  # en moneda del activo

    # Convertir a moneda de la cuenta si es necesario (simplificado para pares USD)
    tick   = mt5.symbol_info_tick(simbolo)
    precio = tick.ask if tick else 1.0
    if simbolo_info.currency_profit != cuenta.currency:
        pip_value_lot = pip_value_lot / precio

    lots = riesgo / (sl_pips * pip_value_lot)

    # Redondear al step permitido
    step  = simbolo_info.volume_step
    lots  = round(round(lots / step) * step, 2)
    lots  = max(simbolo_info.volume_min, min(lots, simbolo_info.volume_max))

    print(f"  Balance  : {balance:,.2f} {cuenta.currency}")
    print(f"  Riesgo   : {riesgo:,.2f} ({riesgo_pct}%)")
    print(f"  Lot size : {lots}")

    return lots


def abrir_orden(simbolo: str, tipo: str, sl_pips: int = SL_PIPS, tp_pips: int = TP_PIPS) -> Optional[int]:
    """
    Abre una orden de mercado.

    tipo : 'COMPRA' | 'VENTA'
    Retorna el ticket de la orden o None si falla.
    """
    tipo = tipo.upper()
    if tipo not in ("COMPRA", "VENTA"):
        print(f"[ERROR] Tipo inválido: {tipo}. Usar 'COMPRA' o 'VENTA'")
        return None

    simbolo_info = mt5.symbol_info(simbolo)
    if simbolo_info is None:
        print(f"[ERROR] Símbolo no encontrado: {simbolo}")
        return None

    tick = mt5.symbol_info_tick(simbolo)
    if tick is None:
        print(f"[ERROR] No se pudo obtener precio de {simbolo}")
        return None

    point = simbolo_info.point
    pip   = point * 10  # 1 pip para la mayoría de pares a 5 decimales

    if tipo == "COMPRA":
        precio    = tick.ask
        order_type = mt5.ORDER_TYPE_BUY
        sl        = precio - sl_pips * pip
        tp        = precio + tp_pips * pip
    else:
        precio    = tick.bid
        order_type = mt5.ORDER_TYPE_SELL
        sl        = precio + sl_pips * pip
        tp        = precio - tp_pips * pip

    lots = calcular_lot_size(simbolo, sl_pips, RIESGO_PORCENTAJE)
    if lots <= 0:
        print("[ERROR] Lot size inválido, operación cancelada")
        return None

    request = {
        "action":     mt5.TRADE_ACTION_DEAL,
        "symbol":     simbolo,
        "volume":     lots,
        "type":       order_type,
        "price":      precio,
        "sl":         round(sl, simbolo_info.digits),
        "tp":         round(tp, simbolo_info.digits),
        "deviation":  20,
        "magic":      MAGIC_NUMBER,
        "comment":    "blsa_bot",
        "type_time":  mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    print(f"\n[ORDEN] {tipo} {simbolo}")
    print(f"  Precio : {precio:.5f}")
    print(f"  SL     : {round(sl, simbolo_info.digits):.5f}  ({sl_pips} pips)")
    print(f"  TP     : {round(tp, simbolo_info.digits):.5f}  ({tp_pips} pips)")

    resultado = mt5.order_send(request)

    if resultado is None or resultado.retcode != mt5.TRADE_RETCODE_DONE:
        codigo = resultado.retcode if resultado else "N/A"
        desc   = resultado.comment if resultado else str(mt5.last_error())
        print(f"[ERROR] Orden rechazada — código {codigo}: {desc}")
        return None

    print(f"[OK] Orden abierta — Ticket #{resultado.order}  Deal #{resultado.deal}")
    return resultado.order


def cerrar_todas(simbolo: str) -> None:
    """Cierra todas las posiciones abiertas del símbolo."""
    posiciones = mt5.positions_get(symbol=simbolo)
    if not posiciones:
        print(f"[INFO] Sin posiciones abiertas en {simbolo}")
        return

    for pos in posiciones:
        tick  = mt5.symbol_info_tick(simbolo)
        tipo  = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        precio = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        req = {
            "action":    mt5.TRADE_ACTION_DEAL,
            "symbol":    simbolo,
            "volume":    pos.volume,
            "type":      tipo,
            "position":  pos.ticket,
            "price":     precio,
            "deviation": 20,
            "magic":     MAGIC_NUMBER,
            "comment":   "blsa_bot_close",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"[OK] Cerrada posición #{pos.ticket}")
        else:
            print(f"[ERROR] No se pudo cerrar #{pos.ticket}: {res.comment if res else mt5.last_error()}")


def mostrar_posiciones(simbolo: str) -> None:
    """Lista las posiciones abiertas del símbolo."""
    posiciones = mt5.positions_get(symbol=simbolo)
    if not posiciones:
        print(f"  Sin posiciones en {simbolo}")
        return

    print(f"  {'Ticket':<10} {'Tipo':<6} {'Lots':<6} {'Apertura':<10} {'SL':<10} {'TP':<10} {'P&L':<10}")
    print("  " + "-" * 65)
    for p in posiciones:
        tipo = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
        print(f"  {p.ticket:<10} {tipo:<6} {p.volume:<6} {p.price_open:<10.5f} {p.sl:<10.5f} {p.tp:<10.5f} {p.profit:<10.2f}")


if __name__ == "__main__":
    from conexion import conectar, desconectar
    from analisis import obtener_simbolo
    import sys

    if not conectar():
        sys.exit(1)

    simbolo = obtener_simbolo()
    if simbolo:
        print("\n--- Posiciones actuales ---")
        mostrar_posiciones(simbolo)

        # Test: abrir una compra de prueba
        # abrir_orden(simbolo, "COMPRA")

    desconectar()
