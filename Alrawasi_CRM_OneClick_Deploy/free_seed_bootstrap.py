import os, json, gzip, sqlite3
BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'crm.db')
SEED=os.path.join(BASE,'seed')

def build_seed_db():
    if os.path.exists(DB) and os.path.getsize(DB)>0:
        return
    # Import app after DB path resolves to BASE in Render Free mode; ensure_schema creates schema.
    import app
    app.ensure_schema()
    mf=json.load(open(os.path.join(SEED,'manifest.json'),encoding='utf-8'))
    con=sqlite3.connect(DB,timeout=30)
    con.row_factory=sqlite3.Row
    try:
        con.execute('PRAGMA busy_timeout=30000')
        con.execute('PRAGMA foreign_keys=OFF')
        con.execute('BEGIN IMMEDIATE')
        cleared=set()
        for name in mf['chunks']:
            with gzip.open(os.path.join(SEED,name),'rt',encoding='utf-8') as f:
                p=json.load(f)
            table=p['table']; rows=p['rows']
            exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
            if not exists: continue
            safe='"'+table.replace('"','""')+'"'
            if table not in cleared:
                con.execute('DELETE FROM '+safe); cleared.add(table)
            if not rows: continue
            actual=[r['name'] for r in con.execute('PRAGMA table_info('+safe+')')]
            cols=[c for c in rows[0].keys() if c in actual]
            if not cols: continue
            qcols=','.join('"'+c.replace('"','""')+'"' for c in cols)
            qs=','.join('?' for _ in cols)
            con.executemany('INSERT INTO '+safe+' ('+qcols+') VALUES ('+qs+')',
                            [[row.get(c) for c in cols] for row in rows])
        con.commit()
    except Exception:
        con.rollback()
        try: os.remove(DB)
        except Exception: pass
        raise
    finally: con.close()

build_seed_db()
