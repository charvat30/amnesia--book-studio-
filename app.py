import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Literal
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field

DB_PATH = os.getenv("AMNESIA_DB_PATH", "amnesia_books.db")
API_KEY = os.getenv("AMNESIA_API_KEY")
app = FastAPI(
    title="Amnesia Book Studio API",
    description="Czech-first book workflow API for a custom ChatGPT GPT Action.",
    version="0.1.0",
)

STAGES = [
    "Idea", "Manuscript", "Editing", "Layout", "Proof",
    "Printer quote", "Approved for print", "Printed"
]
DEFAULT_CHECKLIST = [
    ("manuscript_uploaded", "Rukopis uložen a verze označena"),
    ("editorial_review", "Redakční a jazyková kontrola dokončena"),
    ("author_approval", "Autor schválil redakční změny"),
    ("trim_size_confirmed", "Formát knihy potvrzen s tiskárnou"),
    ("margins_checked", "Okraje a zrcadlo sazby ověřeny"),
    ("fonts_embedded", "Písma vložena do tiskového PDF"),
    ("images_checked", "Rozlišení a barevnost obrázků ověřeny"),
    ("page_count_final", "Konečný počet stran potvrzen"),
    ("cover_specs_received", "Rozměry obálky a hřbetu potvrzeny tiskárnou"),
    ("proof_reviewed", "Zkušební PDF / nátisk zkontrolován"),
    ("printer_approval", "Tiskárna potvrdila tiskové podklady"),
    ("final_author_approval", "Autor schválil finální verzi pro tisk"),
]

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, author TEXT NOT NULL,
            genre TEXT DEFAULT '', trim_size TEXT DEFAULT 'A5',
            binding TEXT DEFAULT 'Pevná vazba', stage TEXT DEFAULT 'Idea',
            publisher TEXT DEFAULT '', printer TEXT DEFAULT '',
            target_copies INTEGER, notes TEXT DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS checklist (
            book_id INTEGER NOT NULL, item_key TEXT NOT NULL,
            label TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
            note TEXT DEFAULT '', updated_at TEXT NOT NULL,
            PRIMARY KEY(book_id, item_key),
            FOREIGN KEY(book_id) REFERENCES books(id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL,
            printer TEXT NOT NULL, amount_czk REAL, copies INTEGER,
            details TEXT DEFAULT '', received_at TEXT NOT NULL,
            FOREIGN KEY(book_id) REFERENCES books(id)
        )""")
init_db()

def require_key(x_api_key: Optional[str] = Header(default=None)):
    if not API_KEY:
        raise HTTPException(503, "Server není nakonfigurován: nastavte AMNESIA_API_KEY.")
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(401, "Neplatný nebo chybějící API klíč.")
    return True

class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    author: str = Field(min_length=1, max_length=200)
    genre: str = ""
    trim_size: str = "A5"
    binding: str = "Pevná vazba"
    stage: Literal["Idea","Manuscript","Editing","Layout","Proof","Printer quote","Approved for print","Printed"] = "Idea"
    publisher: str = ""
    printer: str = ""
    target_copies: Optional[int] = Field(default=None, ge=1, le=1000000)
    notes: str = ""

class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    genre: Optional[str] = None
    trim_size: Optional[str] = None
    binding: Optional[str] = None
    stage: Optional[Literal["Idea","Manuscript","Editing","Layout","Proof","Printer quote","Approved for print","Printed"]] = None
    publisher: Optional[str] = None
    printer: Optional[str] = None
    target_copies: Optional[int] = Field(default=None, ge=1, le=1000000)
    notes: Optional[str] = None

class ChecklistUpdate(BaseModel):
    done: bool
    note: str = ""

class QuoteCreate(BaseModel):
    printer: str = Field(min_length=1, max_length=200)
    amount_czk: Optional[float] = Field(default=None, ge=0)
    copies: Optional[int] = Field(default=None, ge=1)
    details: str = ""

def row_dict(row):
    return dict(row) if row else None

def get_book_or_404(db, book_id):
    row = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Projekt knihy nebyl nalezen.")
    return row

@app.get("/health")
def health():
    return {"status": "ok", "service": "Amnesia Book Studio API", "version": "0.1.0"}

@app.get("/books", dependencies=[Depends(require_key)], operation_id="listBooks")
def list_books():
    with connect() as db:
        rows = db.execute("SELECT * FROM books ORDER BY updated_at DESC").fetchall()
    return {"books": [dict(r) for r in rows], "workflow_stages": STAGES}

@app.post("/books", dependencies=[Depends(require_key)], operation_id="createBook")
def create_book(payload: BookCreate):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        cur = db.execute("""INSERT INTO books
        (title,author,genre,trim_size,binding,stage,publisher,printer,target_copies,notes,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (payload.title,payload.author,payload.genre,payload.trim_size,payload.binding,payload.stage,
         payload.publisher,payload.printer,payload.target_copies,payload.notes,now,now))
        book_id = cur.lastrowid
        for key, label in DEFAULT_CHECKLIST:
            db.execute("INSERT INTO checklist VALUES (?,?,?,?,?,?)",
                       (book_id,key,label,0,"",now))
        book = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    return {"book": dict(book), "message": "Projekt knihy vytvořen. Obsah rukopisu nebyl automaticky doplněn."}

@app.get("/books/{book_id}", dependencies=[Depends(require_key)], operation_id="getBook")
def get_book(book_id: int):
    with connect() as db:
        book = get_book_or_404(db, book_id)
        checklist = db.execute("SELECT * FROM checklist WHERE book_id=? ORDER BY rowid", (book_id,)).fetchall()
        quotes = db.execute("SELECT * FROM quotes WHERE book_id=? ORDER BY received_at DESC", (book_id,)).fetchall()
    return {"book": dict(book), "checklist": [dict(r) for r in checklist], "quotes": [dict(r) for r in quotes]}

@app.patch("/books/{book_id}", dependencies=[Depends(require_key)], operation_id="updateBook")
def update_book(book_id: int, payload: BookUpdate):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Nebyla zadána žádná změna.")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        get_book_or_404(db, book_id)
        sql = ", ".join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE books SET {sql} WHERE id=?", (*updates.values(), book_id))
        book = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    return {"book": dict(book), "message": "Projekt aktualizován."}

@app.get("/books/{book_id}/checklist", dependencies=[Depends(require_key)], operation_id="getChecklist")
def get_checklist(book_id: int):
    with connect() as db:
        get_book_or_404(db, book_id)
        rows = db.execute("SELECT * FROM checklist WHERE book_id=? ORDER BY rowid", (book_id,)).fetchall()
    items = [dict(r) for r in rows]
    done = sum(bool(x["done"]) for x in items)
    return {"book_id": book_id, "items": items, "completed": done, "total": len(items), "percent": round(done/len(items)*100) if items else 0}

@app.patch("/books/{book_id}/checklist/{item_key}", dependencies=[Depends(require_key)], operation_id="updateChecklist")
def update_checklist(book_id: int, item_key: str, payload: ChecklistUpdate):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        get_book_or_404(db, book_id)
        cur = db.execute("UPDATE checklist SET done=?,note=?,updated_at=? WHERE book_id=? AND item_key=?",
                         (int(payload.done), payload.note, now, book_id, item_key))
        if cur.rowcount == 0:
            raise HTTPException(404, "Položka kontrolního seznamu nebyla nalezena.")
        row = db.execute("SELECT * FROM checklist WHERE book_id=? AND item_key=?", (book_id,item_key)).fetchone()
    return {"item": dict(row), "message": "Kontrolní seznam aktualizován."}

@app.get("/books/{book_id}/printer-brief", dependencies=[Depends(require_key)], operation_id="generatePrinterBrief")
def printer_brief(book_id: int):
    with connect() as db:
        book = dict(get_book_or_404(db, book_id))
        checklist = [dict(r) for r in db.execute("SELECT * FROM checklist WHERE book_id=? ORDER BY rowid", (book_id,)).fetchall()]
        quotes = [dict(r) for r in db.execute("SELECT * FROM quotes WHERE book_id=? ORDER BY received_at DESC", (book_id,)).fetchall()]
    lines = [
        f"ZADÁNÍ PRO TISKÁRNU — {book['title']}",
        f"Autor: {book['author']}",
        f"Formát: {book['trim_size']}",
        f"Vazba: {book['binding']}",
        f"Náklad: {book['target_copies'] if book['target_copies'] else 'bude upřesněn'}",
        f"Tiskárna: {book['printer'] or 'bude vybrána'}",
        f"Vydavatel: {book['publisher'] or 'neuveden'}",
        f"Poznámky: {book['notes'] or '—'}",
        "",
        "PROSÍME O POTVRZENÍ SPECIFIKACÍ:",
        "- přesný rozměr čistého formátu a spadávka",
        "- požadovaný PDF standard, barevný profil a rozlišení obrázků",
        "- papír, počet stran a výpočet šířky hřbetu",
        "- rozměry obálky a požadavky na tisková data",
        "- cena, termín, doprava a počet kontrolních výtisků",
        "",
        "Tiskové parametry musí potvrdit tiskárna před finálním exportem."
    ]
    return {"book_id": book_id, "title": book["title"], "brief_text": "\n".join(lines),
            "checklist_completed": sum(bool(x["done"]) for x in checklist),
            "checklist_total": len(checklist), "quotes": quotes}

@app.post("/books/{book_id}/quotes", dependencies=[Depends(require_key)], operation_id="addPrinterQuote")
def add_quote(book_id: int, payload: QuoteCreate):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        get_book_or_404(db, book_id)
        cur = db.execute("INSERT INTO quotes (book_id,printer,amount_czk,copies,details,received_at) VALUES (?,?,?,?,?,?)",
                         (book_id,payload.printer,payload.amount_czk,payload.copies,payload.details,now))
        row = db.execute("SELECT * FROM quotes WHERE id=?", (cur.lastrowid,)).fetchone()
    return {"quote": dict(row), "message": "Cenová nabídka uložena."}
