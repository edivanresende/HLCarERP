from app import app, db
from sqlalchemy import text

with app.app_context():
    cols = [
        ("empresa_id", "INTEGER"),
        ("whatsapp", "TEXT"),
        ("email", "TEXT"),
        ("site", "TEXT"),
        ("observacoes", "TEXT"),
        ("ativo", "INTEGER DEFAULT 1"),
        ("criado_em", "DATETIME"),
        ("alterado_em", "DATETIME"),
        ("telefone", "TEXT"),
    ]
    for nome, tipo in cols:
        try:
            db.session.execute(text(f"ALTER TABLE fabricantes ADD COLUMN {nome} {tipo}"))
            db.session.commit()
            print("OK:", nome)
        except Exception as e:
            db.session.rollback()
            print("ja existe:", nome)
    print("FIM")
