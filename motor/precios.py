#!/usr/bin/env python3
"""Guarda en precios.json el último precio de cada símbolo (Yahoo Finance, con unos 15 minutos de retraso).

Lo corre GitHub Actions cada 15 minutos mientras la bolsa está abierta. La app lee precios.json
al abrirse y cada 5 minutos, así se actualiza aunque no tengas clave de Finnhub (y las empresas
mexicanas, que Finnhub gratis no cubre).
Solo reescribe el archivo si algún precio cambió, para no publicar versiones idénticas.
"""
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from actualizar import SIMBOLOS, REPO, pedir  # noqa: E402

SALIDA = REPO / "precios.json"


def serie(sim, rango, intervalo):
    res = pedir(f"https://query1.finance.yahoo.com/v8/finance/chart/{sim}?range={rango}&interval={intervalo}")["chart"]["result"][0]
    cierres = (res["indicators"]["quote"][0] or {}).get("close") or []
    return [(t, c) for t, c in zip(res.get("timestamp") or [], cierres) if c is not None]


def ultimo(sim):
    try:
        pares = serie(sim, "1d", "5m")
    except Exception:
        pares = []
    # Algunos símbolos (como NAFTRAC) no tienen datos cada 5 minutos: se usa el precio diario.
    if not pares:
        pares = serie(sim, "5d", "1d")
    if not pares:
        return None
    t, c = pares[-1]
    # Descarta precios viejos (algunos símbolos mexicanos traen datos atrasados de Yahoo).
    if datetime.datetime.now(datetime.UTC).timestamp() - t > 5 * 86400:
        return None
    return {"c": round(c, 3), "t": t}


def main():
    precios = {}
    for sim in SIMBOLOS:
        try:
            p = ultimo(sim)
            if p:
                precios[sim] = p
        except Exception as e:
            print(f"FALLO {sim}: {e}")
    if not precios:
        print("Sin precios; no cambio nada.")
        return 1
    anterior = json.loads(SALIDA.read_text(encoding="utf-8")).get("p") if SALIDA.exists() else None
    if anterior == precios:
        print("Sin cambios.")
        return 0
    doc = {"generado": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "p": precios}
    SALIDA.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    print(f"Listo: {len(precios)} precios.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
