from app import app, db
from sqlalchemy import text

cmds = [
    "ALTER TABLE mecanicos ADD COLUMN tipo_remuneracao VARCHAR(20) DEFAULT 'COMISSAO'",
    "ALTER TABLE ordem_servico_mecanicos ADD COLUMN aliquota_imposto FLOAT DEFAULT 10.0",
    "ALTER TABLE empresas ADD COLUMN dia_corte_comissao INTEGER DEFAULT 15",
    "ALTER TABLE empresas ADD COLUMN aliquota_imposto_comissao FLOAT DEFAULT 10.0",
]

with app.app_context():
    for c in cmds:
        try:
            db.session.execute(text(c))
            db.session.commit()
            print("OK:", c)
        except Exception as e:
            db.session.rollback()
            print("skip:", str(e)[:80])
print("Fim.")