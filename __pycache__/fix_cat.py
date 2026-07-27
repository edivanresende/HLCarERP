from app import app, db
from sqlalchemy import text

with app.app_context():
    r = db.session.execute(text("SELECT id, nome FROM categorias")).fetchall()
    print("antes:", r)

    if not r:
        db.session.execute(text("INSERT INTO categorias (nome) VALUES ('Geral')"))
        db.session.commit()
        r = db.session.execute(text("SELECT id, nome FROM categorias")).fetchall()
        print("criada:", r)
    else:
        print("ja tem:", r)