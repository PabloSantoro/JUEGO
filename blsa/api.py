"""
api.py — REST API local para el sistema BLSA Trading
Expone MT5 vía HTTP para ser consultado desde celular u otras apps.

Uso:
    python api.py

Endpoints disponibles:
    GET  /cuenta          — balance, equity, margen
    GET  /analisis        — indicadores y señal actual
    GET  /posiciones      — posiciones abiertas
    POST /orden           — abrir orden de compra/venta
    POST /cerrar          — cerrar todas las posiciones del símbolo
    GET  /health          — estado del servidor y conexión MT5
"""

import sys
import threading
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from conexion import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
from analisis import obtener_simbolo, mostrar_analisis
from operaciones import abrir_orden, cerrar_todas, mostrar_posiciones

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="BLSA Trading API",
    description="API local para MetaTrader 5 — solo accesible desde tu red",
    version="1.0.0",
)

# Permite solicitudes desde la app móvil en la misma red local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # restringir a tu IP de celular si querés más seguridad
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Estado global de conexión
_conectado = False
_lock = threading.Lock()


# ── Modelos ───────────────────────────────────────────────────────────────────
class OrdenRequest(BaseModel):
    simbolo: Optional[str] = None   # si es None, usa el símbolo por defecto
    tipo: str                        # "COMPRA" | "VENTA"
    sl_pips: int = 30
    tp_pips: int = 60


class CerrarRequest(BaseModel):
    simbolo: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────
def _asegurar_conexion() -> None:
    global _conectado
    with _lock:
        if not _conectado:
            if not mt5.initialize():
                raise HTTPException(503, f"MT5 no disponible: {mt5.last_error()}")
            ok = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
            if not ok:
                mt5.shutdown()
                raise HTTPException(503, f"Login MT5 fallido: {mt5.last_error()}")
            _conectado = True


def _simbolo_o_default(s: Optional[str]) -> str:
    sym = s or obtener_simbolo()
    if not sym:
        raise HTTPException(404, "Ningún símbolo disponible en MT5")
    return sym


# ── Startup / Shutdown ────────────────────────────────────────────────────────
@app.on_event("startup")
def startup() -> None:
    _asegurar_conexion()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] API iniciada — MT5 conectado")


@app.on_event("shutdown")
def shutdown() -> None:
    mt5.shutdown()
    print("API detenida — MT5 desconectado")


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Sistema"])
def health():
    """Estado del servidor."""
    _asegurar_conexion()
    return {
        "status": "ok",
        "mt5_conectado": True,
        "hora_servidor": datetime.now().isoformat(),
    }


@app.get("/cuenta", tags=["Cuenta"])
def get_cuenta():
    """Retorna balance, equity y margen de la cuenta."""
    _asegurar_conexion()
    info = mt5.account_info()
    if info is None:
        raise HTTPException(500, f"No se pudo obtener info: {mt5.last_error()}")
    return {
        "login":        info.login,
        "servidor":     info.server,
        "moneda":       info.currency,
        "balance":      info.balance,
        "equity":       info.equity,
        "margen":       info.margin,
        "margen_libre": info.margin_free,
        "nivel_margen": info.margin_level,
        "apalancamiento": info.leverage,
    }


@app.get("/analisis", tags=["Mercado"])
def get_analisis(simbolo: Optional[str] = None):
    """Indicadores y señal de trading para el símbolo."""
    _asegurar_conexion()
    sym = _simbolo_o_default(simbolo)
    resultado = mostrar_analisis(sym)
    if not resultado:
        raise HTTPException(500, "No se pudo calcular el análisis")
    return resultado


@app.get("/posiciones", tags=["Operaciones"])
def get_posiciones(simbolo: Optional[str] = None):
    """Lista de posiciones abiertas."""
    _asegurar_conexion()
    sym = _simbolo_o_default(simbolo)
    posiciones = mt5.positions_get(symbol=sym)
    if not posiciones:
        return {"simbolo": sym, "posiciones": []}

    resultado = []
    for p in posiciones:
        resultado.append({
            "ticket":     p.ticket,
            "tipo":       "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volumen":    p.volume,
            "apertura":   p.price_open,
            "sl":         p.sl,
            "tp":         p.tp,
            "ganancia":   p.profit,
            "swap":       p.swap,
            "comentario": p.comment,
        })
    return {"simbolo": sym, "posiciones": resultado}


@app.post("/orden", tags=["Operaciones"])
def post_orden(req: OrdenRequest):
    """Abre una orden de compra o venta."""
    _asegurar_conexion()
    sym = _simbolo_o_default(req.simbolo)
    ticket = abrir_orden(sym, req.tipo, sl_pips=req.sl_pips, tp_pips=req.tp_pips)
    if ticket is None:
        raise HTTPException(400, "La orden fue rechazada por MT5 — revisá los logs")
    return {"ok": True, "ticket": ticket, "simbolo": sym, "tipo": req.tipo}


@app.post("/cerrar", tags=["Operaciones"])
def post_cerrar(req: CerrarRequest):
    """Cierra todas las posiciones abiertas del símbolo."""
    _asegurar_conexion()
    sym = _simbolo_o_default(req.simbolo)
    cerrar_todas(sym)
    return {"ok": True, "simbolo": sym, "mensaje": "Posiciones cerradas"}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import socket
    ip_local = socket.gethostbyname(socket.gethostname())
    print("=" * 50)
    print("  BLSA Trading API")
    print(f"  PC  : http://localhost:8000/docs")
    print(f"  Red : http://{ip_local}:8000/docs")
    print("  (usá la IP de red desde tu celular)")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
