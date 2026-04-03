"""
analisis.py — Datos de mercado, indicadores y señales de trading
"""

from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

SIMBOLO_PREFERIDO = "EURUSD"
TIMEFRAME         = mt5.TIMEFRAME_M15   # velas de 15 minutos
VELAS_HISTORICO   = 200                 # cantidad de velas a traer


def obtener_simbolo() -> Optional[str]:
    """Devuelve el símbolo disponible (EURUSD o el primer Forex encontrado)."""
    if mt5.symbol_info(SIMBOLO_PREFERIDO) is not None:
        mt5.symbol_select(SIMBOLO_PREFERIDO, True)
        return SIMBOLO_PREFERIDO

    # Busca cualquier par Forex disponible
    simbolos = mt5.symbols_get()
    if simbolos:
        for s in simbolos:
            if "USD" in s.name or "EUR" in s.name:
                mt5.symbol_select(s.name, True)
                print(f"[INFO] Usando símbolo alternativo: {s.name}")
                return s.name

    print("[ERROR] No se encontró ningún símbolo Forex disponible")
    return None


def obtener_velas(simbolo: str, timeframe: int, n: int) -> Optional[pd.DataFrame]:
    """Trae n velas históricas y las devuelve como DataFrame."""
    rates = mt5.copy_rates_from_pos(simbolo, timeframe, 0, n)
    if rates is None or len(rates) == 0:
        print(f"[ERROR] No se pudieron obtener velas de {simbolo}: {mt5.last_error()}")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df


def calcular_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega SMA20, SMA50 y RSI14 al DataFrame."""
    close = df["close"]

    # Medias móviles simples
    df["sma20"] = close.rolling(20).mean()
    df["sma50"] = close.rolling(50).mean()

    # RSI 14
    delta  = close.diff()
    ganancia = delta.clip(lower=0)
    perdida  = (-delta).clip(lower=0)
    avg_g = ganancia.rolling(14).mean()
    avg_p = perdida.rolling(14).mean()
    rs    = avg_g / avg_p.replace(0, np.nan)
    df["rsi14"] = 100 - (100 / (1 + rs))

    return df


def detectar_senal(df: pd.DataFrame) -> str:
    """
    Retorna 'COMPRA', 'VENTA' o 'NEUTRAL' basado en cruce de medias y RSI.

    Compra : SMA20 cruza por encima de SMA50 Y RSI < 70
    Venta  : SMA20 cruza por debajo de SMA50 Y RSI > 30
    """
    if len(df) < 51:
        return "DATOS_INSUFICIENTES"

    ultima  = df.iloc[-1]
    anterior = df.iloc[-2]

    cruce_alcista = (anterior["sma20"] <= anterior["sma50"]) and (ultima["sma20"] > ultima["sma50"])
    cruce_bajista = (anterior["sma20"] >= anterior["sma50"]) and (ultima["sma20"] < ultima["sma50"])
    rsi = ultima["rsi14"]

    if cruce_alcista and rsi < 70:
        return "COMPRA"
    if cruce_bajista and rsi > 30:
        return "VENTA"
    return "NEUTRAL"


def mostrar_analisis(simbolo: str) -> dict:
    """
    Ejecuta el análisis completo e imprime resultados.
    Devuelve un dict con los valores para uso externo.
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Analizando {simbolo}...")

    df = obtener_velas(simbolo, TIMEFRAME, VELAS_HISTORICO)
    if df is None:
        return {}

    df = calcular_indicadores(df)
    senal = detectar_senal(df)

    ultima = df.iloc[-1]
    tick   = mt5.symbol_info_tick(simbolo)
    bid    = tick.bid if tick else ultima["close"]
    ask    = tick.ask if tick else ultima["close"]

    print(f"  Precio  — Bid: {bid:.5f}  Ask: {ask:.5f}")
    print(f"  SMA 20  : {ultima['sma20']:.5f}")
    print(f"  SMA 50  : {ultima['sma50']:.5f}")
    print(f"  RSI 14  : {ultima['rsi14']:.2f}")
    print(f"  Señal   : >>> {senal} <<<")

    return {
        "simbolo": simbolo,
        "bid": bid,
        "ask": ask,
        "sma20": ultima["sma20"],
        "sma50": ultima["sma50"],
        "rsi14": ultima["rsi14"],
        "senal": senal,
    }


if __name__ == "__main__":
    from conexion import conectar, desconectar
    import sys

    if not conectar():
        sys.exit(1)

    simbolo = obtener_simbolo()
    if simbolo:
        mostrar_analisis(simbolo)

    desconectar()
