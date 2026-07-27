from app import app, db
from sqlalchemy import text

cols = [
    ("compra_id", "INTEGER"),
    ("produto_id", "INTEGER"),
    ("quantidade", "REAL DEFAULT 0"),
    ("valor_unitario", "REAL DEFAULT 0"),
    ("valor_total", "REAL DEFAULT 0"),
    ("custo_final", "REAL DEFAULT 0"),
    ("desconto", "REAL DEFAULT 0"),
    ("ipi", "REAL DEFAULT 0"),
    ("icms", "REAL DEFAULT 0"),
    ("frete_rateado", "REAL DEFAULT 0"),
    ("observacoes", "TEXT"),
]

with app.app_context():
    for nome, tipo in cols:
        try:
            db.session.execute(text(f"ALTER TABLE itens_compra ADD COLUMN {nome} {tipo}"))
            db.session.commit()
            print("OK:", nome)
        except Exception:
            db.session.rollback()
            print("ja existe:", nome)
    print("FIM")