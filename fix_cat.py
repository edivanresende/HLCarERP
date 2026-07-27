from app import app, db
from sqlalchemy import text

with app.app_context():
    emp = db.session.execute(text("SELECT id FROM empresas LIMIT 1")).fetchone()
    print("empresa:", emp)
    if not emp:
        db.session.execute(text(
            "INSERT INTO empresas (id, razao_social, nome_fantasia, cnpj, ativo) "
            "VALUES (1, 'HL Car Auto Center', 'HL Car', '00000000000000', 1)"
        ))
        db.session.commit()
        print("empresa criada")

    cat = db.session.execute(text("SELECT id, nome FROM categorias")).fetchall()
    print("categorias antes:", cat)
    if not cat:
        db.session.execute(text(
            "INSERT INTO categorias (nome, empresa_id) VALUES ('Geral', 1)"
        ))
        db.session.commit()
        cat = db.session.execute(text("SELECT id, nome, empresa_id FROM categorias")).fetchall()
        print("categoria criada:", cat)
    else:
        print("categoria ja tem:", cat)
