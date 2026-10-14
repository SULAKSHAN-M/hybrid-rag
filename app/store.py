"""SQLite metadata. Every private resource lookup includes its owner."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE, password TEXT NOT NULL, created REAL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, owner TEXT, expires REAL);
CREATE TABLE IF NOT EXISTS login_attempts(ip TEXT, created REAL);
CREATE TABLE IF NOT EXISTS folders(id TEXT PRIMARY KEY, owner TEXT, name TEXT, pinned INTEGER NOT NULL DEFAULT 0, UNIQUE(owner,name));
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, owner TEXT, folder TEXT, name TEXT, hash TEXT, path TEXT, status TEXT, chunks INTEGER DEFAULT 0, created REAL, UNIQUE(owner,folder,hash));
CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, owner TEXT, document TEXT, page INTEGER, text TEXT, boxes TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT, document TEXT, stage TEXT, progress INTEGER, error TEXT, created REAL);
CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY, owner TEXT, folder TEXT, title TEXT, created REAL, manual_title INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS turns(id TEXT PRIMARY KEY, owner TEXT, chat TEXT, question TEXT, result TEXT, created REAL);
CREATE TABLE IF NOT EXISTS feedback(turn TEXT, owner TEXT, rating INTEGER, note TEXT, created REAL, PRIMARY KEY(turn,owner));
CREATE TABLE IF NOT EXISTS usage(id TEXT PRIMARY KEY, owner TEXT, chat TEXT, model TEXT, latency REAL, attempts INTEGER, tokens INTEGER, token_scope TEXT, status TEXT, created REAL);
CREATE INDEX IF NOT EXISTS turns_chat ON turns(owner,chat,created);
CREATE INDEX IF NOT EXISTS docs_owner ON documents(owner,folder);
CREATE INDEX IF NOT EXISTS chunks_owner ON chunks(owner,document);
'''

class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'workspace.sqlite3'
        with self.db() as db:
            db.executescript(SCHEMA)
            if "manual_title" not in {row[1] for row in db.execute("PRAGMA table_info(chats)")}:
                db.execute("ALTER TABLE chats ADD COLUMN manual_title INTEGER NOT NULL DEFAULT 0")
            if "pinned" not in {row[1] for row in db.execute("PRAGMA table_info(folders)")}:
                db.execute("ALTER TABLE folders ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
            db.execute("UPDATE jobs SET stage='failed',error='Server restarted during upload. Remove the failed document and upload again.' WHERE stage NOT IN ('done','failed')")
            db.execute("UPDATE documents SET status='failed' WHERE status='processing'")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def all(self, sql, args=()):
        with self.db() as db:
            return [dict(x) for x in db.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        rows = self.all(sql, args)
        return rows[0] if rows else None

    def run(self, sql, args=()):
        with self.db() as db:
            db.execute(sql, args)
