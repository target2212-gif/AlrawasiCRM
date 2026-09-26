import os, shutil, sqlite3, gzip

BASE = os.path.dirname(os.path.abspath(__file__))
SEED_DB = os.path.join(BASE, "crm.db")
SEED_GZ = os.path.join(BASE, "crm.db.gz")
DATA_DIR = os.environ.get("DATA_DIR") or "/tmp/alrawasi-data"
LIVE_DB = os.path.join(DATA_DIR, "crm.db")
REQUIRED = {"users", "companies", "interactions", "templates"}

os.makedirs(DATA_DIR, exist_ok=True)

def tables(path):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return set()
    try:
        c = sqlite3.connect(path)
        try:
            return {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        finally:
            c.close()
    except Exception:
        return set()

def prepare_seed():
    if REQUIRED.issubset(tables(SEED_DB)):
        return
    if not os.path.isfile(SEED_GZ):
        raise RuntimeError("crm.db.gz seed is missing")
    tmp = SEED_DB + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    with gzip.open(SEED_GZ, "rb") as src, open(tmp, "wb") as out:
        shutil.copyfileobj(src, out)
    os.replace(tmp, SEED_DB)
    if not REQUIRED.issubset(tables(SEED_DB)):
        raise RuntimeError("Decompressed crm.db is invalid")

prepare_seed()

# On Render Free the runtime filesystem is ephemeral.
# Build the runtime database BEFORE importing app.py.
if not REQUIRED.issubset(tables(LIVE_DB)):
    tmp = LIVE_DB + ".seedtmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    shutil.copy2(SEED_DB, tmp)
    os.replace(tmp, LIVE_DB)

if not REQUIRED.issubset(tables(LIVE_DB)):
    raise RuntimeError("Runtime crm.db preparation failed")

import app as crm_app
flask_app = crm_app.app

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
