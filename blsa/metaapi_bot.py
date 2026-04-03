"""
metaapi_bot.py — Sistema BLSA usando MetaApi Cloud
Funciona desde cualquier dispositivo (celular, tablet, PC).

SETUP (una sola vez):
1. Registrate gratis en https://app.metaapi.cloud
2. Agregá tu cuenta MT5:
   - Login   : 10010390946
   - Password : K!Ks1pHn
   - Server  : MetaQuotes-Demo
3. Copiá tu API_TOKEN desde el dashboard de MetaApi
4. Pegalo en API_TOKEN abajo
5. Copiá el ACCOUNT_ID que te asigna MetaApi para tu cuenta
6. Corré: pip install metaapi-cloud-sdk pandas numpy
"""

import asyncio
from datetime import datetime
import numpy as np
import pandas as pd
from metaapi_cloud_sdk import MetaApi

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
API_TOKEN  = "TU_API_TOKEN_AQUI"       # desde app.metaapi.cloud → API tokens
ACCOUNT_ID = "TU_ACCOUNT_ID_AQUI"     # desde app.metaapi.cloud → tu cuenta MT5
SIMBOLO    = "EURUSD"
RIESGO_PCT = 1.0     # % del balance por operación
SL_PIPS    = 30
TP_PIPS    = 60


# ── INDICADORES ───────────────────────────────────────────────────────────────
def calcular_indicadores(velas: list) -> dict:
    """Calcula SMA20, SMA50 y RSI14 a partir de las velas."""
    cierres = [v["close"] for v in velas]
    s = pd.Series(cierres)

    sma20 = s.rolling(20).mean().iloc[-1]
    sma50 = s.rolling(50).mean().iloc[-1]

    delta    = s.diff()
    ganancia = delta.clip(lower=0).rolling(14).mean()
    perdida  = (-delta).clip(lower=0).rolling(14).mean()
    rs       = ganancia / perdida.replace(0, np.nan)
    rsi14    = (100 - 100 / (1 + rs)).iloc[-1]

    prev_sma20 = s.rolling(20).mean().iloc[-2]
    prev_sma50 = s.rolling(50).mean().iloc[-2]

    if prev_sma20 <= prev_sma50 and sma20 > sma50 and rsi14 < 70:
        senal = "COMPRA"
    elif prev_sma20 >= prev_sma50 and sma20 < sma50 and rsi14 > 30:
        senal = "VENTA"
    else:
        senal = "NEUTRAL"

    return {
        "sma20": round(sma20, 5),
        "sma50": round(sma50, 5),
        "rsi14": round(rsi14, 2),
        "senal": senal,
    }


def calcular_lotes(balance: float, precio: float) -> float:
    """1% del balance, SL de 30 pips."""
    riesgo      = balance * (RIESGO_PCT / 100)
    pip_usd_lot = 10.0            # ~$10 por pip por lote estándar en EURUSD
    lotes       = riesgo / (SL_PIPS * pip_usd_lot)
    lotes       = round(max(0.01, min(round(lotes, 2), 10.0)), 2)
    return lotes


# ── CORE ──────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 50)
    print("  BLSA Trading Bot — MetaApi Cloud")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    api     = MetaApi(API_TOKEN)
    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)

    # Conectar
    print("\n[...] Conectando a MT5 via MetaApi...")
    await account.deploy()
    await account.wait_connected()

    conn = account.get_rpc_connection()
    await conn.connect()
    await conn.wait_synchronized()
    print("[OK] Conectado\n")

    # Info de cuenta
    info = await conn.get_account_information()
    print(f"  Balance  : {info['balance']:,.2f} {info['currency']}")
    print(f"  Equity   : {info['equity']:,.2f}")
    print(f"  Margen L.: {info['freeMargin']:,.2f}")

    # Velas + indicadores
    print(f"\n[ANÁLISIS] {SIMBOLO} — últimas 200 velas M15...")
    velas_raw = await conn.get_historical_candles(SIMBOLO, "15m", datetime.utcnow(), 200)
    ind = calcular_indicadores(velas_raw)

    precio = await conn.get_symbol_price(SIMBOLO)
    bid    = precio["bid"]
    ask    = precio["ask"]

    print(f"  Precio   : Bid {bid:.5f}  Ask {ask:.5f}")
    print(f"  SMA 20   : {ind['sma20']}")
    print(f"  SMA 50   : {ind['sma50']}")
    print(f"  RSI 14   : {ind['rsi14']}")
    print(f"  Señal    : >>> {ind['senal']} <<<")

    # Abrir operación de prueba (COMPRA)
    lotes = calcular_lotes(info["balance"], ask)
    pip   = 0.0001   # 1 pip EURUSD

    sl = round(ask - SL_PIPS * pip, 5)
    tp = round(ask + TP_PIPS * pip, 5)

    print(f"\n[ORDEN] Abriendo COMPRA de prueba...")
    print(f"  Ask    : {ask:.5f}")
    print(f"  Lotes  : {lotes}")
    print(f"  SL     : {sl:.5f}  ({SL_PIPS} pips)")
    print(f"  TP     : {tp:.5f}  ({TP_PIPS} pips)")

    resultado = await conn.create_market_buy_order(
        SIMBOLO,
        lotes,
        sl,
        tp,
        {"comment": "blsa_bot_test"},
    )

    print(f"\n[ÉXITO] Orden abierta!")
    print(f"  Order ID : {resultado.get('orderId', 'N/A')}")

    # Posiciones abiertas
    posiciones = await conn.get_positions()
    print(f"\n[POSICIONES] {len(posiciones)} abierta(s):")
    for p in posiciones:
        tipo = "BUY" if p["type"] == "POSITION_TYPE_BUY" else "SELL"
        print(f"  {tipo} {p['symbol']}  {p['volume']} lotes  entrada {p['openPrice']:.5f}  P&L {p['profit']:.2f}")

    await conn.close()
    print("\n[OK] Listo.")


if __name__ == "__main__":
    asyncio.run(main())
