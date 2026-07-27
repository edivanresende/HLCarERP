from app import app, db
from sqlalchemy import text

with app.app_context():
    cols = [
        ("empresa_id", "INTEGER"),
        ("razao_social", "TEXT"),
        ("nome_fantasia", "TEXT"),
        ("cnpj", "TEXT"),
        ("inscricao_estadual", "TEXT"),
        ("telefone", "TEXT"),
        ("whatsapp", "TEXT"),
        ("email", "TEXT"),
        ("site", "TEXT"),
        ("cep", "TEXT"),
        ("endereco", "TEXT"),
        ("numero", "TEXT"),
        ("bairro", "TEXT"),
        ("cidade", "TEXT"),
        ("estado", "TEXT"),
        ("observacoes", "TEXT"),
        ("ativo", "INTEGER DEFAULT 1"),
        ("criado_em", "DATETIME"),
        ("alterado_em", "DATETIME"),
        ("contato", "TEXT"),
    ]
    for nome, tipo in cols:
        try:
            db.session.execute(text(f"ALTER TABLE fornecedores ADD COLUMN {nome} {tipo}"))
            db.session.commit()
            print("OK:", nome)
        except Exception:
            db.session.rollback()
            print("ja existe:", nome)
    print("FIM")
