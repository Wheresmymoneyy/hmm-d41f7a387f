#!/usr/bin/env python3
"""Descarga los cierres diarios (5 años) y regenera la app "How's my money?".

Uso:
  python3 motor/actualizar.py --web     Solo la versión web (index.html del repositorio). Lo usa GitHub Actions.
  python3 motor/actualizar.py --mac     Solo las versiones de la Mac: panel-inversion.html (precios en vivo
                                        con Finnhub) y app/mi-panel-de-inversion.html (la de claude.ai).
No necesita claves. Los precios vienen del servicio público de gráficas de Yahoo Finance.
La lista de lo que se muestra está en motor/simbolos.json y las opiniones de expertos en motor/expertos.json.
"""
import base64
import datetime
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

MOTOR = pathlib.Path(__file__).resolve().parent
REPO = MOTOR.parent                 # carpeta sitio/ (el repositorio publicado en GitHub Pages)
CARPETA_MAC = REPO.parent           # carpeta "Mi Panel de Inversión" (solo existe en la Mac)
SALIDA_WEB = REPO / "index.html"
SALIDA_LOCAL = CARPETA_MAC / "panel-inversion.html"
SALIDA_APP = CARPETA_MAC / "app" / "mi-panel-de-inversion.html"
ITEMS = json.loads((MOTOR / "simbolos.json").read_text(encoding="utf-8"))["items"]
SIMBOLOS = [i["sym"] for i in ITEMS if i["kind"] != "cetes"] + ["MXN=X"]


def pedir(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.URLError:
        # Python de python.org en macOS a veces no trae certificados; curl del sistema sí.
        txt = subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", "--max-time", "30", url],
                             capture_output=True, text=True, check=True).stdout
        return json.loads(txt)


def descargar(sim):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sim)}?range=5y&interval=1d"
    res = pedir(url)["chart"]["result"][0]
    cierres = res["indicators"]["quote"][0]["close"]
    meta = res["meta"]
    pts = [(datetime.datetime.fromtimestamp(t, datetime.UTC).strftime("%Y-%m-%d"), round(c, 3))
           for t, c in zip(res["timestamp"], cierres) if c is not None]
    # El último precio de mercado reemplaza al cierre incompleto del día, si es del mismo día o posterior.
    ult, t_ult = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
    if ult and t_ult:
        f = datetime.datetime.fromtimestamp(t_ult, datetime.UTC).strftime("%Y-%m-%d")
        if f == pts[-1][0]:
            pts[-1] = (f, round(ult, 3))
        elif f > pts[-1][0]:
            pts.append((f, round(ult, 3)))
    return {"cur": meta.get("currency"), "d": [p[0] for p in pts], "c": [p[1] for p in pts]}


def datos_anteriores():
    """Datos de la última versión generada, para no romper la app si un símbolo falla."""
    for f in (SALIDA_WEB, SALIDA_LOCAL):
        if not f.exists():
            continue
        html = f.read_text(encoding="utf-8")
        i = html.find('<script id="datos" type="application/json">')
        if i < 0:
            continue
        try:
            return json.loads(html[html.find(">", i) + 1:html.find("</script>", i)])
        except Exception:
            continue
    return None


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "--mac"
    if modo not in ("--web", "--mac"):
        print(__doc__)
        return 2
    datos = {"s": {}, "generado": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")}
    anterior = datos_anteriores()
    for sim in SIMBOLOS:
        try:
            datos["s"][sim] = descargar(sim)
            print(f"ok   {sim}: {datos['s'][sim]['d'][-1]} {datos['s'][sim]['c'][-1]}")
        except Exception as e:
            if anterior and sim in anterior.get("s", {}):
                datos["s"][sim] = anterior["s"][sim]
                print(f"FALLO {sim} ({e}); uso el dato anterior")
            else:
                print(f"FALLO {sim} ({e}); sin dato anterior", file=sys.stderr)
                return 1
    datos["asof"] = datos["s"]["VOO"]["d"][-1]
    datos["items"] = [{k: v for k, v in i.items() if k != "analistas"} for i in ITEMS]
    datos["expertos"] = json.loads((MOTOR / "expertos.json").read_text(encoding="utf-8"))
    plantilla = (MOTOR / "plantilla.html").read_text(encoding="utf-8")
    logo = REPO / "icon-192.png"
    logo_uri = ("data:image/png;base64," + base64.b64encode(logo.read_bytes()).decode()) if logo.exists() else ""
    plantilla = plantilla.replace("__LOGO__", logo_uri)
    js = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    if modo == "--web":
        # GitHub Pages: con manifiesto e ícono para instalarla en la pantalla de inicio.
        web = plantilla.replace("__DATOS__", js).replace("__MODO__", "web").replace("<!--WEB-->", (
            '<link rel="manifest" href="manifest.webmanifest">\n'
            '<link rel="apple-touch-icon" sizes="180x180" href="icon-180.png">\n'
            '<meta name="apple-mobile-web-app-capable" content="yes">\n'
            '<meta name="mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-title" content="How\'s my money?">\n'
            '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
            '<meta name="theme-color" content="#0f1716">'))
        SALIDA_WEB.write_text(web, encoding="utf-8")
        print(f"Listo: index.html con datos al {datos['asof']}")
        return 0

    plantilla = plantilla.replace("<!--WEB-->\n", "")
    SALIDA_LOCAL.write_text(plantilla.replace("__DATOS__", js).replace("__MODO__", "local"), encoding="utf-8")
    # Versión de claude.ai: sin <html>/<head>/<body>, porque la publicación agrega su propio esqueleto.
    app = plantilla.replace("__DATOS__", js).replace("__MODO__", "app")
    cabeza = app[app.index("<head>") + 6:app.index("</head>")]
    cabeza = "\n".join(l for l in cabeza.splitlines() if "<meta charset" not in l and 'name="viewport"' not in l)
    cuerpo = app[app.index("<body>") + 6:app.rindex("</body>")]
    SALIDA_APP.parent.mkdir(exist_ok=True)
    SALIDA_APP.write_text(cabeza.strip() + '\n<meta name="claude:viewport-fit-sides" content="cover">\n' + cuerpo, encoding="utf-8")
    print(f"Listo: {SALIDA_LOCAL.name} y {SALIDA_APP.name} con datos al {datos['asof']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
