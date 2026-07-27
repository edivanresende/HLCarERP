from app import app, db
from sqlalchemy import text

with app.app_context():
    cols = [
        ("descricao", "TEXT"),
        ("ativo", "INTEGER DEFAULT 1"),
        ("criado_em", "DATETIME"),
        ("alterado_em", "DATETIME"),
        ("empresa_id", "INTEGER"),
    ]
    for nome, tipo in cols:
        try:
            db.session.execute(text(f"ALTER TABLE categorias ADD COLUMN {nome} {tipo}"))
            db.session.commit()
            print("OK:", nome)
        except Exception as e:
            db.session.rollback()
            print("ja existe:", nome)
    print("FIM")
