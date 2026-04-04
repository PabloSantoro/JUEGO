"""
agente_forex.py — Agente de análisis forex con Claude AI
Usa fuentes públicas gratuitas (Yahoo Finance + RSS + APIs) y Claude para recomendar operaciones.

Uso:
    python agente_forex.py                    # análisis completo
    python agente_forex.py --par GBPUSD       # par específico
    python agente_forex.py --loop 15          # repetir cada 15 minutos

Configuración:
    export ANTHROPIC_API_KEY=tu_clave_aqui    # Linux/Mac
    set ANTHROPIC_API_KEY=tu_clave_aqui       # Windows

Obtené tu API key gratis en: https://console.anthropic.com
"""

import os
import sys
import time
import argparse
import json
from datetime import datetime, timedelta
from typing import Optional

import requests
import numpy as np
import pandas as pd
import anthropic

# ── Configuración ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL             = "claude-sonnet-4-6"
BALANCE_DEMO      = 3000.0      # balance cuenta demo USD
RIESGO_PCT        = 1.0         # % máximo de riesgo por operación

HEADERS_YF = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Símbolos Yahoo Finance → nombre legible
PARES = {
    "EURUSD=X":  "EUR/USD",
    "GBPUSD=X":  "GBP/USD",
    "USDJPY=X":  "USD/JPY",
    "USDCHF=X":  "USD/CHF",
    "AUDUSD=X":  "AUD/USD",
    "USDCAD=X":  "USD/CAD",
    "NZDUSD=X":  "NZD/USD",
    "NZDJPY=X":  "NZD/JPY",
    "GBPJPY=X":  "GBP/JPY",
    "EURJPY=X":  "EUR/JPY",
}


# ── Fuente 1: Yahoo Finance — Precios y velas ─────────────────────────────────

def obtener_velas(simbolo: str, intervalo: str = "15m", periodo: str = "5d") -> Optional[pd.DataFrame]:
    """Descarga velas OHLCV de Yahoo Finance."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
           f"?interval={intervalo}&range={periodo}")
    try:
        r = requests.get(url, headers=HEADERS_YF, timeout=10)
        data = r.json()["chart"]["result"][0]
        ts    = data["timestamp"]
        ohlcv = data["indicators"]["quote"][0]
        df = pd.DataFrame({
            "time":   pd.to_datetime(ts, unit="s"),
            "open":   ohlcv["open"],
            "high":   ohlcv["high"],
            "low":    ohlcv["low"],
            "close":  ohlcv["close"],
            "volume": ohlcv.get("volume", [0]*len(ts)),
        }).dropna()
        return df
    except Exception as e:
        print(f"  [WARN] Yahoo Finance {simbolo}: {e}")
        return None


def calcular_indicadores(df: pd.DataFrame) -> dict:
    """Calcula SMA20, SMA50, RSI14, ATR y señal."""
    c = df["close"]

    sma20 = c.rolling(20).mean().iloc[-1]
    sma50 = c.rolling(50).mean().iloc[-1] if len(c) >= 50 else sma20

    # RSI 14
    delta = c.diff()
    g = delta.clip(lower=0).rolling(14).mean()
    p = (-delta).clip(lower=0).rolling(14).mean()
    rsi = (100 - 100 / (1 + g / p.replace(0, np.nan))).iloc[-1]

    # ATR 14
    high, low, prev_close = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]

    # Señal
    prev_sma20 = c.rolling(20).mean().iloc[-2]
    prev_sma50 = c.rolling(50).mean().iloc[-2] if len(c) >= 51 else prev_sma20
    precio_actual = c.iloc[-1]

    if prev_sma20 <= prev_sma50 and sma20 > sma50 and rsi < 65:
        senal = "BUY"
    elif prev_sma20 >= prev_sma50 and sma20 < sma50 and rsi > 35:
        senal = "SELL"
    elif sma20 < sma50 and rsi > 60:
        senal = "SELL"
    elif sma20 > sma50 and rsi < 40:
        senal = "BUY"
    else:
        senal = "NEUTRAL"

    return {
        "precio":  round(precio_actual, 5),
        "sma20":   round(sma20, 5),
        "sma50":   round(sma50, 5),
        "rsi14":   round(rsi, 2),
        "atr":     round(atr, 5),
        "senal":   senal,
        "cambio_pct": round(((precio_actual / c.iloc[-2]) - 1) * 100, 3),
    }


def analizar_todos_los_pares() -> str:
    """Descarga y analiza todos los pares. Retorna tabla de texto."""
    print("  → Yahoo Finance (precios + técnico)...")
    lineas = [f"{'Par':<12} {'Precio':<10} {'Cambio%':<9} {'SMA20':<10} {'RSI':<7} {'ATR':<8} {'Señal'}"]
    lineas.append("-" * 68)

    resultados = {}
    for sym, nombre in PARES.items():
        df = obtener_velas(sym)
        if df is None or len(df) < 21:
            lineas.append(f"{nombre:<12} Sin datos")
            continue
        ind = calcular_indicadores(df)
        lineas.append(
            f"{nombre:<12} {ind['precio']:<10} {ind['cambio_pct']:>+7.3f}%  "
            f"{ind['sma20']:<10} {ind['rsi14']:<7.1f} {ind['atr']:<8.5f} {ind['senal']}"
        )
        resultados[nombre] = ind

    return "\n".join(lineas), resultados


# ── Fuente 2: API Frankfurter — Tipos de cambio spot ─────────────────────────

def obtener_tipos_cambio() -> str:
    """Tipos de cambio actuales desde frankfurter.app (BCE, gratuito)."""
    print("  → Frankfurter API (tipos de cambio BCE)...")
    try:
        r = requests.get(
            "https://api.frankfurter.app/latest?from=USD",
            timeout=8
        )
        data = r.json()
        fecha = data.get("date", "N/A")
        rates = data.get("rates", {})
        lineas = [f"Tipos de cambio vs USD (fuente BCE, fecha: {fecha})"]
        for moneda in ["EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]:
            if moneda in rates:
                lineas.append(f"  USD/{moneda}: {rates[moneda]}")
        return "\n".join(lineas)
    except Exception as e:
        return f"Frankfurter no disponible: {e}"


# ── Fuente 3: RSS feeds de noticias ──────────────────────────────────────────

RSS_FEEDS = [
    ("Reuters Forex",  "https://feeds.reuters.com/reuters/businessNews"),
    ("Investing.com",  "https://www.investing.com/rss/news_301.rss"),
    ("FXStreet",       "https://www.fxstreet.com/rss/news"),
    ("MarketWatch FX", "https://feeds.marketwatch.com/marketwatch/realtimeheadlines/"),
]

KEYWORDS_FX = [
    "dollar", "USD", "EUR", "GBP", "JPY", "forex", "currency",
    "Fed", "ECB", "BOJ", "tariff", "inflation", "rate", "central bank",
    "dólar", "euro", "libra", "yen", "mercado", "divisa",
    "Iran", "war", "oil", "Trump", "NFP", "jobs", "employment",
]

def obtener_noticias_rss() -> str:
    """Extrae titulares de múltiples feeds RSS."""
    print("  → Feeds RSS (noticias)...")
    titulares = []

    for nombre_feed, url in RSS_FEEDS:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            # Parser XML simple sin dependencias extra
            from xml.etree import ElementTree as ET
            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            for item in items[:8]:
                titulo_el = item.find("title")
                if titulo_el is not None and titulo_el.text:
                    titulo = titulo_el.text.strip()
                    if any(k.lower() in titulo.lower() for k in KEYWORDS_FX):
                        titulares.append(f"[{nombre_feed}] {titulo}")
            if titulares:
                break  # con una fuente alcanza si hay suficientes
        except Exception:
            continue

    if not titulares:
        return "RSS no disponible — sin noticias en tiempo real."

    return "\n".join(titulares[:15])


# ── Fuente 4: Búsqueda DuckDuckGo Instant Answer ─────────────────────────────

def obtener_contexto_mercado() -> str:
    """Obtiene resumen del mercado forex vía API pública de DuckDuckGo."""
    print("  → DuckDuckGo (contexto de mercado)...")
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": "forex market today news", "format": "json", "no_html": 1},
            timeout=8,
        )
        data = r.json()
        abstract = data.get("AbstractText", "")
        related  = [t.get("Text", "") for t in data.get("RelatedTopics", [])[:5]]
        resultado = abstract
        if related:
            resultado += "\n" + "\n".join(f"- {t}" for t in related if t)
        return resultado or "Sin resumen disponible."
    except Exception as e:
        return f"DuckDuckGo no disponible: {e}"


# ── Agente Claude ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sos un analista de forex experto con 15 años de experiencia.
Recibís datos de múltiples fuentes y tenés que dar UNA sola recomendación de trading concreta.

CUENTA DEL USUARIO:
- Balance demo: {balance} USD
- Riesgo máximo: {riesgo}% del balance = {riesgo_usd:.0f} USD por operación

REGLAS:
1. Elegí el par con la señal más clara y fundamentación más fuerte
2. Si todos están neutros, decí "ESPERAR" y explicá por qué
3. Para calcular lotes: Lotes = Riesgo_USD / (SL_pips × pip_value)
   - Para pares XXX/USD: pip_value = $10 por lote estándar
   - Para USD/XXX: pip_value ≈ $10 / precio_actual por lote estándar
   - Para cruces: calcular según par base
4. Explicación simple, sin jerga — el usuario es principiante
5. Siempre incluir el ratio riesgo:ganancia (mínimo 1:1.5)

FORMATO OBLIGATORIO DE RESPUESTA:
## 🎯 [PAR] — [BUY/SELL/ESPERAR]

**Entrada:** [precio exacto]
**Stop Loss:** [precio] ([X] pips de distancia)
**Take Profit:** [precio] ([X] pips de distancia)
**Lotes:** [X.XX]
**Riesgo:** ~$[X] | **Ganancia posible:** ~$[X] | **Ratio:** 1:[X]

### Por qué este par:
[2-3 líneas simples explicando la lógica — sin tecnicismos]

### Señales detectadas:
- Técnico: [señal]
- RSI: [valor] ([sobrevendido/sobrecomprado/neutral])
- Tendencia: [SMA20 vs SMA50]
- Fundamental: [noticia o dato clave]

### ⚠️ Riesgo principal:
[Una línea sobre qué podría salir mal]

---
*Cuenta DEMO — dinero virtual únicamente.*
"""


def analizar_con_claude(tabla_tecnica: str, indicadores: dict,
                        tipos_cambio: str, noticias: str,
                        contexto: str, par_especifico: Optional[str] = None) -> str:
    """Sintetiza todos los datos con Claude y genera la recomendación."""
    if not ANTHROPIC_API_KEY:
        return (
            "\n[ERROR] No hay ANTHROPIC_API_KEY configurada.\n"
            "Pasos:\n"
            "  1. Registrate en https://console.anthropic.com\n"
            "  2. Creá una API key gratuita\n"
            "  3. Exportá: export ANTHROPIC_API_KEY=tu_clave\n"
            "  4. Volvé a correr: python agente_forex.py\n"
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    contexto_completo = f"""
FECHA Y HORA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
{'PAR ESPECÍFICO A ANALIZAR: ' + par_especifico if par_especifico else 'ANALIZAR TODOS LOS PARES'}

=== ANÁLISIS TÉCNICO (Yahoo Finance, velas M15) ===
{tabla_tecnica}

=== TIPOS DE CAMBIO SPOT (Banco Central Europeo) ===
{tipos_cambio}

=== NOTICIAS RECIENTES (RSS feeds) ===
{noticias}

=== CONTEXTO DE MERCADO ===
{contexto}
"""

    riesgo_usd = BALANCE_DEMO * RIESGO_PCT / 100
    system = SYSTEM_PROMPT.format(
        balance=BALANCE_DEMO,
        riesgo=RIESGO_PCT,
        riesgo_usd=riesgo_usd,
    )

    mensaje = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": contexto_completo}],
    )

    return mensaje.content[0].text


# ── Main ──────────────────────────────────────────────────────────────────────

def correr(par_especifico: Optional[str] = None) -> None:
    print("=" * 58)
    print(f"  BLSA Forex Agent  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Balance: ${BALANCE_DEMO:,.0f}  |  Riesgo: {RIESGO_PCT}%  |  Modelo: {MODEL}")
    print("=" * 58)

    # 1. Recopilar datos
    print("\n[DATOS] Consultando fuentes...")
    tabla_tecnica, indicadores = analizar_todos_los_pares()
    tipos_cambio = obtener_tipos_cambio()
    noticias     = obtener_noticias_rss()
    contexto     = obtener_contexto_mercado()

    # 2. Mostrar datos crudos
    print(f"\n[TÉCNICO]\n{tabla_tecnica}")
    print(f"\n[NOTICIAS]\n{noticias[:600]}...")

    # 3. Analizar con Claude
    print("\n[CLAUDE] Analizando y generando recomendación...")
    recomendacion = analizar_con_claude(
        tabla_tecnica, indicadores,
        tipos_cambio, noticias,
        contexto, par_especifico,
    )

    # 4. Mostrar resultado
    print("\n" + "=" * 58)
    print("  RECOMENDACIÓN DEL AGENTE")
    print("=" * 58)
    print(recomendacion)
    print("=" * 58)

    # 5. Guardar log
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forex_log.txt")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*58}\n[{datetime.now().isoformat()}]\n")
        f.write(tabla_tecnica + "\n\n")
        f.write(recomendacion + "\n")
    print(f"\n[LOG] → {log_path}")


def main():
    parser = argparse.ArgumentParser(
        description="BLSA Forex Agent — análisis automático con Claude AI"
    )
    parser.add_argument("--par", type=str, default=None,
                        help="Analizar un par específico (ej: GBPUSD, NZDUSD)")
    parser.add_argument("--loop", type=int, default=None,
                        help="Repetir cada X minutos (ej: --loop 15)")
    args = parser.parse_args()

    if args.loop:
        print(f"Modo automático: análisis cada {args.loop} min. Ctrl+C para detener.")
        while True:
            correr(par_especifico=args.par)
            print(f"\n⏳ Próximo análisis en {args.loop} minutos...\n")
            time.sleep(args.loop * 60)
    else:
        correr(par_especifico=args.par)


if __name__ == "__main__":
    main()
