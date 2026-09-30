import os, shutil, sqlite3, gzip, sys

BASE=os.path.dirname(os.path.abspath(__file__))
SEED_DB=os.path.join(BASE,"crm.db")
SEED_GZ=os.path.join(BASE,"crm.db.gz")
DATA_DIR=os.environ.get("DATA_DIR") or "/tmp/alrawasi-data"
LIVE_DB=os.path.join(DATA_DIR,"crm.db")
REQUIRED={"users","companies","interactions","templates"}

def tables(path):
    if not os.path.isfile(path) or os.path.getsize(path)==0:
        return set()
    try:
        c=sqlite3.connect(path)
        try:
            return {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        finally:
            c.close()
    except Exception:
        return set()

os.makedirs(DATA_DIR, exist_ok=True)

# Rebuild packaged seed once, atomically, before gunicorn starts.
if not REQUIRED.issubset(tables(SEED_DB)):
    if not os.path.isfile(SEED_GZ):
        raise RuntimeError("Missing crm.db.gz")
    tmp=SEED_DB+".init"
    try:
        if os.path.exists(tmp): os.remove(tmp)
        with gzip.open(SEED_GZ,"rb") as src, open(tmp,"wb") as out:
            shutil.copyfileobj(src,out)
        if not REQUIRED.issubset(tables(tmp)):
            raise RuntimeError("Invalid decompressed seed database")
        os.replace(tmp,SEED_DB)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

# Free Render runtime DB: initialize only when absent/incomplete.
if not REQUIRED.issubset(tables(LIVE_DB)):
    tmp=LIVE_DB+".init"
    try:
        if os.path.exists(tmp): os.remove(tmp)
        shutil.copy2(SEED_DB,tmp)
        if not REQUIRED.issubset(tables(tmp)):
            raise RuntimeError("Invalid runtime seed copy")
        os.replace(tmp,LIVE_DB)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

missing=REQUIRED-tables(LIVE_DB)
if missing:
    raise RuntimeError("Runtime DB missing tables: "+", ".join(sorted(missing)))

print("Database initialization OK:", LIVE_DB, flush=True)
