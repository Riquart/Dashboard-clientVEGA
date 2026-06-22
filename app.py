"""
Application Flask — Dashboard de suivi clientèle (Licences & PS abonnés).

Sert le dashboard et expose les données extraites de l'Excel via /api/data.
Le fichier Excel peut être remplacé en ligne via /upload (protégé par un token),
ce qui met à jour le site SANS redéploiement — à condition d'avoir attaché un
volume Railway persistant (voir README).

Variables d'environnement :
  DATA_DIR      Répertoire de données persistant (Railway : /data). Défaut : ./data
  UPLOAD_TOKEN  Mot de passe pour la page d'upload. Si absent, l'upload est désactivé.
"""

import hashlib
import json
import os

from flask import Flask, jsonify, request, send_from_directory, abort, Response

import dashboard_data

app = Flask(__name__, static_folder="static")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLED_XLSX = os.path.join(BASE_DIR, "data", "source.xlsx")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
UPLOAD_TOKEN = os.environ.get("UPLOAD_TOKEN")

os.makedirs(DATA_DIR, exist_ok=True)

# Cache mémoire : {hash: data}
_cache = {}


def active_xlsx():
    """Excel uploadé (volume) en priorité, sinon le fichier livré avec le projet."""
    uploaded = os.path.join(DATA_DIR, "source.xlsx")
    return uploaded if os.path.exists(uploaded) else BUNDLED_XLSX


def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_write_path():
    return os.path.join(DATA_DIR, "cache.json")


def cache_read_paths():
    # 1) cache runtime (volume Railway)  2) cache livré avec le projet
    return [os.path.join(DATA_DIR, "cache.json"),
            os.path.join(BASE_DIR, "data", "cache.json")]


def get_data():
    """Renvoie les données extraites, avec cache par empreinte du fichier."""
    path = active_xlsx()
    digest = file_hash(path)

    if digest in _cache:
        return _cache[digest]

    # cache disque (survit aux redémarrages ; le cache livré rend le 1er chargement instantané)
    for dc in cache_read_paths():
        if os.path.exists(dc):
            try:
                with open(dc, "r", encoding="utf-8") as f:
                    blob = json.load(f)
                if blob.get("hash") == digest:
                    _cache[digest] = blob["data"]
                    return blob["data"]
            except (json.JSONDecodeError, KeyError, OSError):
                pass

    # parse complet (lent : ~15 s sur le gros fichier) puis cache
    data = dashboard_data.extract(path)
    _cache[digest] = data
    try:
        with open(cache_write_path(), "w", encoding="utf-8") as f:
            json.dump({"hash": digest, "data": data}, f, ensure_ascii=False)
    except OSError:
        pass
    return data


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/data")
def api_data():
    data = get_data()
    meta = {
        "last": data["Total"]["labels"][-1] if data["Total"]["labels"] else None,
        "weeks": len(data["Total"]["labels"]),
        "source": "uploadé" if active_xlsx() != BUNDLED_XLSX else "livré",
    }
    return jsonify({"meta": meta, "data": data})


UPLOAD_PAGE = """<!doctype html><html lang=fr><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Mettre à jour les données</title>
<style>body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#eef1f6;color:#1f2a44;
display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
.card{{background:#fff;padding:32px;border-radius:14px;box-shadow:0 6px 24px rgba(20,40,80,.12);width:380px}}
h1{{font-size:19px;margin:0 0 6px}}p{{color:#6b7689;font-size:14px;line-height:1.5;margin:0 0 18px}}
label{{font-size:13px;font-weight:600;display:block;margin:14px 0 6px}}
input{{width:100%;padding:10px;border:1px solid #d8dee9;border-radius:8px;font-size:14px}}
button{{margin-top:20px;width:100%;padding:11px;background:#2f5aa8;color:#fff;border:0;border-radius:8px;
font-size:15px;font-weight:600;cursor:pointer}}.msg{{margin-top:16px;font-size:14px}}
.ok{{color:#1f9d8f}}.err{{color:#d1495b}}a{{color:#2f5aa8}}</style></head>
<body><form class=card method=post enctype=multipart/form-data>
<h1>Mettre à jour les données</h1>
<p>Dépose ton fichier Excel à jour. Le dashboard se mettra à jour immédiatement (le 1er chargement reparse le fichier, ~15 s).</p>
<label>Fichier Excel (.xlsx)</label><input type=file name=file accept=".xlsx" required>
<label>Mot de passe</label><input type=password name=token required>
<button type=submit>Mettre à jour</button>
{msg}
<p style=margin-top:18px><a href="/">← Retour au dashboard</a></p>
</form></body></html>"""


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if not UPLOAD_TOKEN:
        return Response(
            "Upload désactivé : définissez la variable d'environnement UPLOAD_TOKEN sur Railway.",
            status=503, mimetype="text/plain")

    msg = ""
    if request.method == "POST":
        if request.form.get("token") != UPLOAD_TOKEN:
            msg = '<div class="msg err">Mot de passe incorrect.</div>'
        else:
            f = request.files.get("file")
            if not f or not f.filename.lower().endswith(".xlsx"):
                msg = '<div class="msg err">Merci de fournir un fichier .xlsx.</div>'
            else:
                dest = os.path.join(DATA_DIR, "source.xlsx")
                f.save(dest)
                # invalide le cache et reparse immédiatement
                _cache.clear()
                try:
                    get_data()
                    msg = '<div class="msg ok">✓ Données mises à jour.</div>'
                except Exception as e:  # noqa: BLE001
                    msg = f'<div class="msg err">Fichier enregistré mais erreur de lecture : {e}</div>'
    return UPLOAD_PAGE.format(msg=msg)


@app.route("/healthz")
def healthz():
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
