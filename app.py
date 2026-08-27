from flask import (
    Flask,
    render_template,
    request,
    redirect,
    send_file,
    jsonify,
    session
)

from datetime import datetime, date, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import text, func

from config import Config

from models import (
    db,
    Cliente,
    Veiculo,
    OrdemServico,
    Produto,
    Categoria,
    Fabricante,
    Fornecedor,
    Compra,
    ItemCompra,
    Inventario,
    ItemInventario,
    MovimentacaoEstoque,
    Mecanico,
    OrdemServicoMecanico,
    Agendamento,
    Usuario,
    Empresa,
    ItemOrdemServico,
    VendaRapida,
    ItemVendaRapida,
    LembreteEnvio,
    ChecklistVeiculo,
    ContaReceber,
    ContaPagar,
    Caixa,
)

from pdf_ordem_old import gerar_pdf_ordem


app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "hlcar-erp-secret-key-2026-change-me"

db.init_app(app)
# ============================================================
# COMISSÕES / PAGAMENTO MECÂNICOS
# ============================================================

def periodo_corte_comissao(empresa, ref_date=None):
    """Retorna (data_inicio, data_fim) do período de corte atual."""
    if ref_date is None:
        ref_date = date.today()
    dia = int(getattr(empresa, "dia_corte_comissao", None) or 15)
    dia = max(1, min(28, dia))

    if ref_date.day >= dia:
        ini = date(ref_date.year, ref_date.month, dia)
        if ref_date.month == 12:
            fim = date(ref_date.year + 1, 1, dia) - timedelta(days=1)
        else:
            fim = date(ref_date.year, ref_date.month + 1, dia) - timedelta(days=1)
    else:
        if ref_date.month == 1:
            ini = date(ref_date.year - 1, 12, dia)
        else:
            ini = date(ref_date.year, ref_date.month - 1, dia)
        fim = date(ref_date.year, ref_date.month, dia) - timedelta(days=1)
    return ini, fim


def calc_comissao_linha(valor_negociado, percentual, aliquota_imposto, tipo_remuneracao="COMISSAO"):
    base = float(valor_negociado or 0)
    pct = float(percentual or 0)
    aliq = float(aliquota_imposto if aliquota_imposto is not None else 10.0)
    tipo = (tipo_remuneracao or "COMISSAO").upper()

    if tipo == "PARCEIRO":
        return {"base_bruta": base, "imposto": 0.0, "base_liquida": base, "valor_comissao": base}
    if tipo == "SALARIO":
        return {
            "base_bruta": base,
            "imposto": round(base * aliq / 100.0, 2),
            "base_liquida": round(base * (1 - aliq / 100.0), 2),
            "valor_comissao": 0.0,
        }

    imposto = round(base * aliq / 100.0, 2)
    liquida = round(base - imposto, 2)
    comissao = round(liquida * pct / 100.0, 2)
    return {"base_bruta": base, "imposto": imposto, "base_liquida": liquida, "valor_comissao": comissao}


def resumo_comissoes_periodo(eid, data_ini, data_fim):
    empresa = Empresa.query.get(eid)
    aliq_padrao = float(getattr(empresa, "aliquota_imposto_comissao", None) or 10.0)

    vinculos = (
        db.session.query(OrdemServicoMecanico, OrdemServico, Mecanico)
        .join(OrdemServico, OrdemServicoMecanico.ordem_servico_id == OrdemServico.id)
        .join(Mecanico, OrdemServicoMecanico.mecanico_id == Mecanico.id)
        .filter(
            OrdemServico.empresa_id == eid,
            OrdemServico.data_abertura >= datetime.combine(data_ini, datetime.min.time()),
            OrdemServico.data_abertura < datetime.combine(data_fim + timedelta(days=1), datetime.min.time()),
        )
        .all()
    )

    por_mec = {}
    for osm, ordem, mec in vinculos:
        mid = mec.id
        if mid not in por_mec:
            tipo_rem = (getattr(mec, "tipo_remuneracao", None) or "COMISSAO").upper()
            if (mec.tipo or "").upper() == "PARCEIRO":
                tipo_rem = "PARCEIRO"
            por_mec[mid] = {
                "mecanico": mec,
                "tipo_remuneracao": tipo_rem,
                "salario": float(mec.salario or 0),
                "percentual_padrao": float(mec.percentual_comissao or 0),
                "qtd_servicos": 0,
                "base_bruta": 0.0,
                "imposto": 0.0,
                "base_liquida": 0.0,
                "comissao": 0.0,
                "linhas": [],
            }

        aliq = getattr(osm, "aliquota_imposto", None)
        if aliq is None:
            aliq = aliq_padrao
        pct = osm.percentual_comissao if osm.percentual_comissao is not None else mec.percentual_comissao
        tipo_rem = por_mec[mid]["tipo_remuneracao"]
        calc = calc_comissao_linha(osm.valor_negociado, pct, aliq, tipo_rem)

        osm.base_comissao = calc["base_liquida"]
        osm.valor_comissao = calc["valor_comissao"]

        por_mec[mid]["qtd_servicos"] += 1
        por_mec[mid]["base_bruta"] += calc["base_bruta"]
        por_mec[mid]["imposto"] += calc["imposto"]
        por_mec[mid]["base_liquida"] += calc["base_liquida"]
        por_mec[mid]["comissao"] += calc["valor_comissao"]
        por_mec[mid]["linhas"].append({
            "os_id": ordem.id,
            "os_numero": getattr(ordem, "numero", ordem.id),
            "descricao": osm.descricao_servico,
            **calc,
        })

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    lista = []
    for mid, d in por_mec.items():
        salario = d["salario"] if d["tipo_remuneracao"] in ("SALARIO", "MISTO") else 0.0
        total = round(salario + d["comissao"], 2)
        lista.append({**d, "salario_periodo": salario, "total_pagar": total})
    lista.sort(key=lambda x: x["total_pagar"], reverse=True)
    return lista


# ============================================================
# AUTENTICAÇÃO
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function
@app.route("/comissoes")
@login_required
def comissoes():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
 
    empresa = Empresa.query.get(eid)
    data_ini_s = request.args.get("data_ini")
    data_fim_s = request.args.get("data_fim")
 
    if data_ini_s and data_fim_s:
        try:
            data_ini = datetime.strptime(data_ini_s, "%Y-%m-%d").date()
            data_fim = datetime.strptime(data_fim_s, "%Y-%m-%d").date()
        except Exception:
            data_ini, data_fim = periodo_corte_comissao(empresa)
    else:
        data_ini, data_fim = periodo_corte_comissao(empresa)
 
    resumo = resumo_comissoes_periodo(eid, data_ini, data_fim)
    total_geral = sum(r["total_pagar"] for r in resumo)
    total_comissao = sum(r["comissao"] for r in resumo)
    total_salario = sum(r["salario_periodo"] for r in resumo)
    total_imposto = sum(r["imposto"] for r in resumo)
 
    return render_template(
        "comissoes.html",
        resumo=resumo,
        data_ini=data_ini.isoformat(),
        data_fim=data_fim.isoformat(),
        dia_corte=getattr(empresa, "dia_corte_comissao", 15) or 15,
        aliquota_padrao=getattr(empresa, "aliquota_imposto_comissao", 10) or 10,
        total_geral=total_geral,
        total_comissao=total_comissao,
        total_salario=total_salario,
        total_imposto=total_imposto,
    )


def empresa_atual():
    """Retorna o empresa_id da sessão. Se não tiver, força logout."""
    eid = session.get("empresa_id")
    if not eid:
        session.clear()
        return None
    return eid


def criar_admin_se_nao_existir():



    """Cria a empresa e o usuário admin na primeira execução"""
    try:
        empresa = Empresa.query.first()
        if not empresa:
            empresa = Empresa(
                razao_social="HL Car Auto Center",
                nome_fantasia="HL Car Auto Center",
                cnpj="00.000.000/0001-00",
                ativo=True
            )
            db.session.add(empresa)
            db.session.commit()
            print("✅ Empresa criada")

        admin = Usuario.query.filter_by(login="admin").first()
        if not admin:
            admin = Usuario(
                empresa_id=empresa.id,
                nome="Administrador",
                login="admin",
                senha=generate_password_hash("admin123"),
                perfil="ADMIN",
                ativo=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuário admin criado!")
            print("   Login: admin")
            print("   Senha: admin123")
    except Exception as e:
        print("Erro ao criar admin:", e)
        db.session.rollback()


def corrigir_colunas_banco():
    """Adiciona colunas que faltam (sem apagar dados)"""
    try:
        # ========== USUARIOS ==========
        result = db.session.execute(text("PRAGMA table_info(usuarios)")).fetchall()
        colunas = [row[1] for row in result]

        if "email" not in colunas:
            db.session.execute(text("ALTER TABLE usuarios ADD COLUMN email VARCHAR(150)"))
            print("✅ usuarios.email adicionada")

        if "alterado_em" not in colunas:
            db.session.execute(text("ALTER TABLE usuarios ADD COLUMN alterado_em DATETIME"))
            print("✅ usuarios.alterado_em adicionada")

        if "criado_em" not in colunas:
            db.session.execute(text("ALTER TABLE usuarios ADD COLUMN criado_em DATETIME"))
            print("✅ usuarios.criado_em adicionada")

        if "perfil" not in colunas:
            db.session.execute(text("ALTER TABLE usuarios ADD COLUMN perfil VARCHAR(20) DEFAULT 'CONSULTOR'"))
            print("✅ usuarios.perfil adicionada")

        # ========== EMPRESAS ==========
        result = db.session.execute(text("PRAGMA table_info(empresas)")).fetchall()
        colunas = [row[1] for row in result]

        colunas_empresas = {
            "inscricao_estadual": "VARCHAR(30)",
            "telefone": "VARCHAR(30)",
            "whatsapp": "VARCHAR(30)",
            "email": "VARCHAR(150)",
            "site": "VARCHAR(200)",
                        "data_vencimento": "DATE",
            "status_pagamento": "VARCHAR(20)",
            "plano": "VARCHAR(50)",
            "observacoes_internas": "TEXT",
            "url_nfse": "VARCHAR(255)",
            "nfse_provedor": "VARCHAR(50)",
            "inscricao_municipal": "VARCHAR(30)",
            "certificado_path": "VARCHAR(255)",
            "senha_certificado": "VARCHAR(100)",
            "codigo_servico": "VARCHAR(20)",
            "aliquota_iss": "NUMERIC(5,2)",
            "regime_tributario": "VARCHAR(10)",
            "cep": "VARCHAR(15)",
            "endereco": "VARCHAR(200)",
            "numero": "VARCHAR(20)",
            "complemento": "VARCHAR(100)",
            "bairro": "VARCHAR(100)",
            "cidade": "VARCHAR(100)",
            "estado": "VARCHAR(2)",
            "logo": "VARCHAR(255)",
            "criado_em": "DATETIME",
            "alterado_em": "DATETIME",
        }

        for coluna, tipo in colunas_empresas.items():
            if coluna not in colunas:
                db.session.execute(text(f"ALTER TABLE empresas ADD COLUMN {coluna} {tipo}"))
                print(f"✅ empresas.{coluna} adicionada")

        # ========== CLIENTES ==========
        result = db.session.execute(text("PRAGMA table_info(clientes)")).fetchall()
        colunas = [row[1] for row in result]

        if "data_nascimento" not in colunas:
            db.session.execute(text("ALTER TABLE clientes ADD COLUMN data_nascimento DATE"))
            print("✅ clientes.data_nascimento adicionada")

        # ========== VEICULOS ==========
        result = db.session.execute(text("PRAGMA table_info(veiculos)")).fetchall()
        colunas = [row[1] for row in result]

        if "proxima_revisao_data" not in colunas:
            db.session.execute(text("ALTER TABLE veiculos ADD COLUMN proxima_revisao_data DATE"))
            print("✅ veiculos.proxima_revisao_data adicionada")

        if "proxima_revisao_km" not in colunas:
            db.session.execute(text("ALTER TABLE veiculos ADD COLUMN proxima_revisao_km INTEGER"))
            print("✅ veiculos.proxima_revisao_km adicionada")

        if "km" not in colunas:
            db.session.execute(text("ALTER TABLE veiculos ADD COLUMN km INTEGER"))
            print("✅ veiculos.km adicionada")
        # ========== ORDEM_SERVICO_MECANICOS ==========
        result = db.session.execute(text("PRAGMA table_info(ordem_servico_mecanicos)")).fetchall()
        colunas = [row[1] for row in result]
        if "descricao_servico" not in colunas:
            db.session.execute(text("ALTER TABLE ordem_servico_mecanicos ADD COLUMN descricao_servico VARCHAR(250)"))
            print("✅ ordem_servico_mecanicos.descricao_servico adicionada")
                    # ========== ITENS_ORDEM_SERVICO ==========
        try:
            result = db.session.execute(text("PRAGMA table_info(itens_ordem_servico)")).fetchall()
            colunas = [row[1] for row in result]

            colunas_itens = {
                "produto_id": "INTEGER",
                "fornecedor_id": "INTEGER",
                "origem": "VARCHAR(20)",
                "tipo_item": "VARCHAR(20)",
                "descricao": "VARCHAR(250)",
                "quantidade": "NUMERIC(18,3)",
                "custo_unitario": "NUMERIC(18,2)",
                "valor_parceiro": "NUMERIC(18,2)",
                "margem": "NUMERIC(18,2)",
                "lucro": "NUMERIC(18,2)",
                "valor_unitario": "NUMERIC(18,2)",
                "desconto": "NUMERIC(18,2)",
                "valor_total": "NUMERIC(18,2)",
                "observacoes": "TEXT",
            }

            if colunas:
                for coluna, tipo in colunas_itens.items():
                    if coluna not in colunas:
                        db.session.execute(text(f"ALTER TABLE itens_ordem_servico ADD COLUMN {coluna} {tipo}"))
                        print(f"✅ itens_ordem_servico.{coluna} adicionada")
        except Exception as e:
            print("Erro ao verificar itens_ordem_servico:", e)
                    # ========== CHECKLIST_VEICULO ==========
        try:
            result = db.session.execute(text("PRAGMA table_info(checklist_veiculo)")).fetchall()
            colunas = [row[1] for row in result]
            if "assinatura" not in colunas:
                db.session.execute(text("ALTER TABLE checklist_veiculo ADD COLUMN assinatura TEXT"))
                print("✅ checklist_veiculo.assinatura adicionada")
        except Exception as e:
            print("Erro checklist_veiculo:", e)
                    # ========== ITENS_VENDA_RAPIDA ==========
        try:
            result = db.session.execute(text("PRAGMA table_info(itens_venda_rapida)")).fetchall()
            colunas = [row[1] for row in result]
            if "custo_unitario" not in colunas:
                db.session.execute(text("ALTER TABLE itens_venda_rapida ADD COLUMN custo_unitario NUMERIC(18,2) DEFAULT 0"))
                print("✅ itens_venda_rapida.custo_unitario adicionada")
        except Exception as e:
            print("Erro itens_venda_rapida:", e)
                    # ========== MECANICOS ==========
        try:
            result = db.session.execute(text("PRAGMA table_info(mecanicos)")).fetchall()
            colunas = [row[1] for row in result]
            if "tipo" not in colunas:
                db.session.execute(text("ALTER TABLE mecanicos ADD COLUMN tipo VARCHAR(20) DEFAULT 'FUNCIONARIO'"))
                print("✅ mecanicos.tipo adicionada")
        except Exception as e:
            print("Erro mecanicos:", e)


        db.session.commit()
        print("✅ Tabelas verificadas e corrigidas")
    except Exception as e:
        print("Erro ao verificar/corrigir colunas:", e)
        db.session.rollback()


with app.app_context():
    db.create_all()
    corrigir_colunas_banco()
    criar_admin_se_nao_existir()


@app.route("/login", methods=["GET", "POST"])
def login():
    if "usuario_id" in session:
        return redirect("/")

    erro = None

    if request.method == "POST":
        login_digitado = request.form.get("login", "").strip()
        senha_digitada = request.form.get("senha", "")

        usuario = Usuario.query.filter_by(login=login_digitado, ativo=True).first()

        if usuario and check_password_hash(usuario.senha, senha_digitada):
            empresa = Empresa.query.get(usuario.empresa_id)
            if empresa and empresa.status_pagamento == "BLOQUEADO":
                erro = "Empresa bloqueada por atraso de pagamento. Entre em contato com o suporte."
            elif empresa and not empresa.ativo:
                erro = "Empresa inativa. Entre em contato com o suporte."
            else:
                session["usuario_id"] = usuario.id
                session["usuario_nome"] = usuario.nome
                session["usuario_perfil"] = usuario.perfil
                session["empresa_id"] = usuario.empresa_id
                return redirect("/")
        else:
            erro = "Usuário ou senha inválidos"

    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ============================================================
# DASHBOARD COM FILTRO DE DATA
# ============================================================
@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")

    from collections import defaultdict

    data_ini = request.args.get("data_ini") or date.today().replace(day=1).isoformat()
    data_fim = request.args.get("data_fim") or date.today().isoformat()
    try:
        d_ini = datetime.strptime(data_ini, "%Y-%m-%d")
        d_fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
    except Exception:
        d_ini = datetime.combine(date.today().replace(day=1), datetime.min.time())
        d_fim = datetime.now() + timedelta(days=1)
        data_ini = d_ini.date().isoformat()
        data_fim = date.today().isoformat()

    def _f(v):
        try:
            return float(v or 0)
        except Exception:
            return 0.0

    total_clientes = Cliente.query.filter_by(empresa_id=eid).count()
    total_veiculos = Veiculo.query.filter_by(empresa_id=eid).count()

    todas_os = OrdemServico.query.filter_by(empresa_id=eid)
    q_os = todas_os.filter(
        OrdemServico.data_abertura >= d_ini,
        OrdemServico.data_abertura < d_fim,
    )
    os_periodo = q_os.all()

    total_os = todas_os.count()
    os_abertas = todas_os.filter(
        func.upper(OrdemServico.status).in_(["ABERTA", "EM ANDAMENTO", "ANDAMENTO", "ORCAMENTO", "ORÇAMENTO"])
    ).count()
    os_concluidas = q_os.filter(
        func.upper(OrdemServico.status).in_(["CONCLUIDA", "CONCLUÍDA", "FINALIZADA", "FECHADA"])
    ).count()

    receita_servicos = sum(_f(getattr(o, "valor_servicos", 0)) for o in os_periodo)
    receita_pecas_os = sum(_f(getattr(o, "valor_produtos", 0)) for o in os_periodo)
    faturamento_os = sum(_f(getattr(o, "valor_total", 0)) for o in os_periodo)
    if faturamento_os == 0:
        faturamento_os = receita_servicos + receita_pecas_os

    faturamento_vendas = 0.0
    qtd_vendas = 0
    try:
        qv = VendaRapida.query.filter(
            VendaRapida.empresa_id == eid,
            VendaRapida.data_venda >= d_ini,
            VendaRapida.data_venda < d_fim,
        )
        vendas = qv.all()
        qtd_vendas = len(vendas)
        faturamento_vendas = sum(_f(getattr(v, "valor_total", 0)) for v in vendas)
    except Exception as e:
        print("Erro vendas dashboard:", e)

    faturamento_total = faturamento_os + faturamento_vendas
    ticket_medio = (faturamento_os / len(os_periodo)) if os_periodo else 0

    lucro_estoque = lucro_parceiro = 0.0
    receita_estoque = receita_parceiro = 0.0
    custo_estoque = custo_parceiro = 0.0

    try:
        itens_os = (
            db.session.query(ItemOrdemServico)
            .join(OrdemServico, ItemOrdemServico.ordem_servico_id == OrdemServico.id)
            .filter(
                OrdemServico.empresa_id == eid,
                OrdemServico.data_abertura >= d_ini,
                OrdemServico.data_abertura < d_fim,
            )
            .all()
        )
        for item in itens_os:
            venda = _f(getattr(item, "valor_total", 0))
            if venda == 0:
                venda = _f(getattr(item, "valor_unitario", 0)) * _f(getattr(item, "quantidade", 1))
            custo = _f(getattr(item, "custo_unitario", 0)) * _f(getattr(item, "quantidade", 1) or 1)
            origem = str(getattr(item, "origem", "") or "").upper()
            if origem in ("ESTOQUE", "PROPRIO", "PRÓPRIO", ""):
                lucro_estoque += (venda - custo)
                receita_estoque += venda
                custo_estoque += custo
            else:
                lucro_parceiro += (venda - custo)
                receita_parceiro += venda
                custo_parceiro += custo
    except Exception as e:
        print("Erro itens OS:", e)

    try:
        itens_vr = (
            db.session.query(ItemVendaRapida)
            .join(VendaRapida)
            .filter(
                VendaRapida.empresa_id == eid,
                VendaRapida.data_venda >= d_ini,
                VendaRapida.data_venda < d_fim,
            )
            .all()
        )
        for item in itens_vr:
            venda = _f(getattr(item, "valor_total", 0))
            custo = _f(getattr(item, "custo_unitario", 0)) * _f(getattr(item, "quantidade", 1) or 1)
            origem = str(getattr(item, "origem", "") or "").upper()
            if origem in ("ESTOQUE", "PROPRIO", "PRÓPRIO", ""):
                lucro_estoque += (venda - custo)
                receita_estoque += venda
                custo_estoque += custo
            else:
                lucro_parceiro += (venda - custo)
                receita_parceiro += venda
                custo_parceiro += custo
    except Exception as e:
        print("Erro itens VR:", e)

    lucro_pecas_total = lucro_estoque + lucro_parceiro
    lucro_servicos = receita_servicos
    lucro_geral = lucro_pecas_total + lucro_servicos

    gastos_compras = 0.0
    try:
        for c in Compra.query.filter(
            Compra.empresa_id == eid,
            Compra.data_entrada >= d_ini,
            Compra.data_entrada < d_fim,
        ).all():
            gastos_compras += _f(getattr(c, "valor_total", 0))
    except Exception as e:
        print("Erro compras:", e)

    resultado = lucro_geral - gastos_compras

    try:
        estoque_baixo = Produto.query.filter(Produto.empresa_id == eid, Produto.estoque_atual <= 5).count()
    except Exception:
        estoque_baixo = 0

    os_antigas = todas_os.filter(
        func.upper(OrdemServico.status) == "ABERTA",
        func.date(OrdemServico.data_abertura) <= (date.today() - timedelta(days=7)),
    ).count()

    try:
        os_retrabalho = todas_os.filter(
            db.or_(OrdemServico.is_retrabalho == True, func.upper(OrdemServico.status) == "RETRABALHO")
        ).count()
    except Exception:
        os_retrabalho = todas_os.filter(func.upper(OrdemServico.status) == "RETRABALHO").count()

    ranking = []
    try:
        mapa = defaultdict(lambda: {"qtd": 0, "faturamento": 0.0, "retrabalho": 0, "nome": "Sem mecânico"})
        for vinculo in OrdemServicoMecanico.query.join(OrdemServico).filter(OrdemServico.empresa_id == eid).all():
            mid = vinculo.mecanico_id or 0
            mec = Mecanico.query.get(mid)
            nome = mec.nome if mec else f"ID {mid}"
            o = vinculo.ordem_servico
            mapa[mid]["nome"] = nome
            mapa[mid]["qtd"] += 1
            mapa[mid]["faturamento"] += _f(getattr(o, "valor_total", 0))
            if getattr(o, "is_retrabalho", False) or str(getattr(o, "status", "")).upper() == "RETRABALHO":
                mapa[mid]["retrabalho"] += 1
        if not mapa:
            for o in todas_os.all():
                mid = getattr(o, "mecanico_id", None) or 0
                nome = getattr(o, "mecanico", None) or "Sem mecânico"
                if mid:
                    mec = Mecanico.query.get(mid)
                    nome = mec.nome if mec else nome
                chave = mid or nome
                mapa[chave]["nome"] = nome
                mapa[chave]["qtd"] += 1
                mapa[chave]["faturamento"] += _f(getattr(o, "valor_total", 0))
                if getattr(o, "is_retrabalho", False) or str(getattr(o, "status", "")).upper() == "RETRABALHO":
                    mapa[chave]["retrabalho"] += 1
        ranking = sorted(mapa.values(), key=lambda x: x["faturamento"], reverse=True)
    except Exception as e:
        print("Erro ranking:", e)

    os_recentes = todas_os.order_by(OrdemServico.data_abertura.desc()).limit(8).all()

    labels_status, valores_status = [], []
    try:
        for st, qtd in db.session.query(OrdemServico.status, func.count(OrdemServico.id)).filter_by(empresa_id=eid).group_by(OrdemServico.status).all():
            labels_status.append(st or "Sem status")
            valores_status.append(int(qtd))
    except Exception:
        pass

    labels_meses, valores_meses = [], []
    try:
        seis = datetime.now() - timedelta(days=180)
        rows = db.session.query(
            func.strftime("%Y-%m", OrdemServico.data_abertura).label("mes"),
            func.coalesce(func.sum(OrdemServico.valor_total), 0),
        ).filter(OrdemServico.empresa_id == eid, OrdemServico.data_abertura >= seis).group_by("mes").order_by("mes").all()
        for mes, valor in rows:
            labels_meses.append(mes or "")
            valores_meses.append(float(valor or 0))
    except Exception as e:
        print("Erro grafico:", e)
            # ========== RODADA A: FINANCEIRO + OPERAÇÃO ==========
    hoje = date.today()
    em_7 = hoje + timedelta(days=7)
    em_30 = hoje + timedelta(days=30)

    # --- Contas a Receber ---
    receber_vencidas = 0.0
    receber_7 = 0.0
    receber_30 = 0.0
    receber_total_pendente = 0.0
    try:
        for cr in ContaReceber.query.filter(
            ContaReceber.empresa_id == eid,
            ContaReceber.status.in_(["PENDENTE", "PARCIAL", "ABERTA"]),
        ).all():
            valor_aberto = _f(getattr(cr, "valor", 0)) - _f(getattr(cr, "valor_recebido", 0))
            if valor_aberto <= 0:
                continue
            receber_total_pendente += valor_aberto
            venc = getattr(cr, "data_vencimento", None)
            if not venc:
                continue
            if hasattr(venc, "date"):
                venc = venc.date()
            if venc < hoje:
                receber_vencidas += valor_aberto
            elif venc <= em_7:
                receber_7 += valor_aberto
            elif venc <= em_30:
                receber_30 += valor_aberto
    except Exception as e:
        print("Erro contas receber dashboard:", e)

    # --- Contas a Pagar ---
    pagar_vencidas = 0.0
    pagar_7 = 0.0
    pagar_30 = 0.0
    pagar_total_pendente = 0.0
    try:
        for cp in ContaPagar.query.filter(
            ContaPagar.empresa_id == eid,
            ContaPagar.status.in_(["PENDENTE", "PARCIAL", "ABERTA"]),
        ).all():
            valor_aberto = _f(getattr(cp, "valor", 0)) - _f(getattr(cp, "valor_pago", 0))
            if valor_aberto <= 0:
                continue
            pagar_total_pendente += valor_aberto
            venc = getattr(cp, "data_vencimento", None)
            if not venc:
                continue
            if hasattr(venc, "date"):
                venc = venc.date()
            if venc < hoje:
                pagar_vencidas += valor_aberto
            elif venc <= em_7:
                pagar_7 += valor_aberto
            elif venc <= em_30:
                pagar_30 += valor_aberto
    except Exception as e:
        print("Erro contas pagar dashboard:", e)

    # --- Caixa do período ---
    caixa_entradas = 0.0
    caixa_saidas = 0.0
    try:
        for cx in Caixa.query.filter(
            Caixa.empresa_id == eid,
            Caixa.data_movimento >= d_ini,
            Caixa.data_movimento < d_fim,
        ).all():
            v = _f(getattr(cx, "valor", 0))
            tipo = str(getattr(cx, "tipo", "") or "").upper()
            if tipo in ("ENTRADA", "C", "CREDITO", "CRÉDITO", "+"):
                caixa_entradas += abs(v)
            elif tipo in ("SAIDA", "SAÍDA", "D", "DEBITO", "DÉBITO", "-"):
                caixa_saidas += abs(v)
            else:
                if v >= 0:
                    caixa_entradas += v
                else:
                    caixa_saidas += abs(v)
    except Exception as e:
        print("Erro caixa dashboard:", e)
    caixa_saldo = caixa_entradas - caixa_saidas

    # --- Inadimplência ---
    inadimplencia_valor = receber_vencidas
    try:
        faturado_base = faturamento_total if faturamento_total > 0 else 1
        inadimplencia_pct = (inadimplencia_valor / faturado_base) * 100
    except Exception:
        inadimplencia_pct = 0.0

    # --- OS paradas (+7 e +15 dias) ---
    os_paradas_7 = 0
    os_paradas_15 = 0
    valor_preso_7 = 0.0
    valor_preso_15 = 0.0
    try:
        limite_7 = hoje - timedelta(days=7)
        limite_15 = hoje - timedelta(days=15)
        for o in todas_os.filter(
            func.upper(OrdemServico.status).in_(["ABERTA", "EM ANDAMENTO", "ANDAMENTO", "ORCAMENTO", "ORÇAMENTO", "RETRABALHO"])
        ).all():
            da = getattr(o, "data_abertura", None)
            if not da:
                continue
            if hasattr(da, "date"):
                da = da.date()
            vt = _f(getattr(o, "valor_total", 0))
            if da <= limite_15:
                os_paradas_15 += 1
                valor_preso_15 += vt
            elif da <= limite_7:
                os_paradas_7 += 1
                valor_preso_7 += vt
    except Exception as e:
        print("Erro OS paradas:", e)

    # --- Comparativo mês anterior ---
    try:
        mes_atual_ini = hoje.replace(day=1)
        if mes_atual_ini.month == 1:
            mes_ant_ini = mes_atual_ini.replace(year=mes_atual_ini.year - 1, month=12)
        else:
            mes_ant_ini = mes_atual_ini.replace(month=mes_atual_ini.month - 1)
        mes_ant_fim = mes_atual_ini

        fat_mes_atual = 0.0
        for o in OrdemServico.query.filter(
            OrdemServico.empresa_id == eid,
            OrdemServico.data_abertura >= datetime.combine(mes_atual_ini, datetime.min.time()),
            OrdemServico.data_abertura < datetime.combine(hoje + timedelta(days=1), datetime.min.time()),
        ).all():
            fat_mes_atual += _f(getattr(o, "valor_total", 0))
        try:
            for v in VendaRapida.query.filter(
                VendaRapida.empresa_id == eid,
                VendaRapida.data_venda >= datetime.combine(mes_atual_ini, datetime.min.time()),
                VendaRapida.data_venda < datetime.combine(hoje + timedelta(days=1), datetime.min.time()),
            ).all():
                fat_mes_atual += _f(getattr(v, "valor_total", 0))
        except Exception:
            pass

        fat_mes_anterior = 0.0
        for o in OrdemServico.query.filter(
            OrdemServico.empresa_id == eid,
            OrdemServico.data_abertura >= datetime.combine(mes_ant_ini, datetime.min.time()),
            OrdemServico.data_abertura < datetime.combine(mes_ant_fim, datetime.min.time()),
        ).all():
            fat_mes_anterior += _f(getattr(o, "valor_total", 0))
        try:
            for v in VendaRapida.query.filter(
                VendaRapida.empresa_id == eid,
                VendaRapida.data_venda >= datetime.combine(mes_ant_ini, datetime.min.time()),
                VendaRapida.data_venda < datetime.combine(mes_ant_fim, datetime.min.time()),
            ).all():
                fat_mes_anterior += _f(getattr(v, "valor_total", 0))
        except Exception:
            pass

        if fat_mes_anterior > 0:
            variacao_mes_pct = ((fat_mes_atual - fat_mes_anterior) / fat_mes_anterior) * 100
        else:
            variacao_mes_pct = 100.0 if fat_mes_atual > 0 else 0.0
        variacao_mes_valor = fat_mes_atual - fat_mes_anterior
    except Exception as e:
        print("Erro comparativo mês:", e)
        fat_mes_atual = fat_mes_anterior = variacao_mes_pct = variacao_mes_valor = 0.0
            # ========== RODADA B: COMERCIAL + ESTOQUE + PESSOAS ==========
    # --- Top 5 produtos mais vendidos (OS + Venda Rápida) ---
    top_produtos = []
    try:
        from collections import defaultdict
        mapa_prod = defaultdict(lambda: {"nome": "", "qtd": 0.0, "faturamento": 0.0})

        for item in (
            db.session.query(ItemOrdemServico)
            .join(OrdemServico, ItemOrdemServico.ordem_servico_id == OrdemServico.id)
            .filter(
                OrdemServico.empresa_id == eid,
                OrdemServico.data_abertura >= d_ini,
                OrdemServico.data_abertura < d_fim,
            )
            .all()
        ):
            nome = getattr(item, "descricao", None) or "Item"
            if getattr(item, "produto_id", None):
                p = Produto.query.get(item.produto_id)
                if p:
                    nome = getattr(p, "descricao", None) or getattr(p, "nome", None) or nome
            qtd = _f(getattr(item, "quantidade", 1) or 1)
            fat = _f(getattr(item, "valor_total", 0))
            if fat == 0:
                fat = _f(getattr(item, "valor_unitario", 0)) * qtd
            chave = nome.strip().upper()
            mapa_prod[chave]["nome"] = nome
            mapa_prod[chave]["qtd"] += qtd
            mapa_prod[chave]["faturamento"] += fat

        try:
            for item in (
                db.session.query(ItemVendaRapida)
                .join(VendaRapida)
                .filter(
                    VendaRapida.empresa_id == eid,
                    VendaRapida.data_venda >= d_ini,
                    VendaRapida.data_venda < d_fim,
                )
                .all()
            ):
                nome = getattr(item, "descricao", None) or "Item"
                if getattr(item, "produto_id", None):
                    p = Produto.query.get(item.produto_id)
                    if p:
                        nome = getattr(p, "descricao", None) or getattr(p, "nome", None) or nome
                qtd = _f(getattr(item, "quantidade", 1) or 1)
                fat = _f(getattr(item, "valor_total", 0))
                chave = nome.strip().upper()
                mapa_prod[chave]["nome"] = nome
                mapa_prod[chave]["qtd"] += qtd
                mapa_prod[chave]["faturamento"] += fat
        except Exception:
            pass

        top_produtos = sorted(mapa_prod.values(), key=lambda x: x["faturamento"], reverse=True)[:5]
    except Exception as e:
        print("Erro top produtos:", e)

    # --- Estoque crítico (lista) ---
    produtos_criticos = []
    try:
        for p in Produto.query.filter(Produto.empresa_id == eid).order_by(Produto.estoque_atual.asc()).limit(20).all():
            estoque = _f(getattr(p, "estoque_atual", 0))
            minimo = _f(getattr(p, "estoque_minimo", 5) or 5)
            if estoque <= minimo:
                produtos_criticos.append({
                    "nome": getattr(p, "descricao", None) or getattr(p, "nome", None) or f"ID {p.id}",
                    "estoque": estoque,
                    "minimo": minimo,
                })
        produtos_criticos = produtos_criticos[:8]
    except Exception as e:
        print("Erro estoque crítico:", e)

    # --- Margem média de peças (%) ---
    try:
        if (receita_estoque + receita_parceiro) > 0:
            margem_pecas_pct = (lucro_pecas_total / (receita_estoque + receita_parceiro)) * 100
        else:
            margem_pecas_pct = 0.0
    except Exception:
        margem_pecas_pct = 0.0

    # --- Top 5 clientes por faturamento ---
    top_clientes = []
    try:
        mapa_cli = defaultdict(lambda: {"nome": "", "qtd_os": 0, "faturamento": 0.0})
        for o in os_periodo:
            cid = getattr(o, "cliente_id", None) or 0
            nome = "Cliente"
            if o.cliente:
                nome = o.cliente.nome or nome
            mapa_cli[cid]["nome"] = nome
            mapa_cli[cid]["qtd_os"] += 1
            mapa_cli[cid]["faturamento"] += _f(getattr(o, "valor_total", 0))
        top_clientes = sorted(mapa_cli.values(), key=lambda x: x["faturamento"], reverse=True)[:5]
    except Exception as e:
        print("Erro top clientes:", e)

    # --- Comissões estimadas dos mecânicos ---
    comissoes = []
    total_comissoes = 0.0
    try:
        mapa_com = defaultdict(lambda: {"nome": "", "os": 0, "comissao": 0.0})
        for v in OrdemServicoMecanico.query.join(OrdemServico).filter(
            OrdemServico.empresa_id == eid,
            OrdemServico.data_abertura >= d_ini,
            OrdemServico.data_abertura < d_fim,
        ).all():
            mid = v.mecanico_id or 0
            mec = Mecanico.query.get(mid)
            nome = mec.nome if mec else f"ID {mid}"
            valor_com = _f(getattr(v, "comissao", 0) or getattr(v, "valor_comissao", 0))
            if valor_com == 0:
                # fallback: 10% do valor da OS se não tiver comissão cadastrada
                o = v.ordem_servico
                valor_com = _f(getattr(o, "valor_servicos", 0)) * 0.10
            mapa_com[mid]["nome"] = nome
            mapa_com[mid]["os"] += 1
            mapa_com[mid]["comissao"] += valor_com
        comissoes = sorted(mapa_com.values(), key=lambda x: x["comissao"], reverse=True)
        total_comissoes = sum(c["comissao"] for c in comissoes)
    except Exception as e:
        print("Erro comissões:", e)

    # --- Agendamentos hoje / amanhã ---
    agendamentos_hoje = []
    agendamentos_amanha = []
    try:
        amanha = hoje + timedelta(days=1)
        for a in Agendamento.query.filter(Agendamento.empresa_id == eid).all():
            data_ag = getattr(a, "data", None) or getattr(a, "data_agendamento", None)
            if not data_ag:
                continue
            if hasattr(data_ag, "date"):
                data_ag = data_ag.date()
            cliente_nome = "-"
            if getattr(a, "cliente_id", None):
                c = Cliente.query.get(a.cliente_id)
                if c:
                    cliente_nome = c.nome
            item = {
                "hora": getattr(a, "hora", None) or getattr(a, "horario", "") or "",
                "cliente": cliente_nome,
                "placa": getattr(a, "placa", "") or "",
                "obs": getattr(a, "observacao", None) or getattr(a, "observacoes", "") or "",
            }
            if data_ag == hoje:
                agendamentos_hoje.append(item)
            elif data_ag == amanha:
                agendamentos_amanha.append(item)
    except Exception as e:
        print("Erro agendamentos:", e)

    return render_template(
        "dashboard.html",
        data_ini=data_ini,
        data_fim=data_fim,
        total_clientes=total_clientes,
        total_veiculos=total_veiculos,
        total_os=total_os,
        os_abertas=os_abertas,
        os_concluidas=os_concluidas,
        os_antigas=os_antigas,
        os_retrabalho=os_retrabalho,
        faturamento_os=faturamento_os,
        faturamento_vendas=faturamento_vendas,
        faturamento_total=faturamento_total,
        qtd_vendas=qtd_vendas,
        ticket_medio=ticket_medio,
        receita_servicos=receita_servicos,
        receita_pecas_os=receita_pecas_os,
        receita_estoque=receita_estoque,
        receita_parceiro=receita_parceiro,
        custo_estoque=custo_estoque,
        custo_parceiro=custo_parceiro,
        lucro_estoque=lucro_estoque,
        lucro_parceiro=lucro_parceiro,
        lucro_pecas_total=lucro_pecas_total,
        lucro_servicos=lucro_servicos,
        lucro_geral=lucro_geral,
        gastos_compras=gastos_compras,
        resultado=resultado,
        estoque_baixo=estoque_baixo,
        ranking=ranking,
        os_recentes=os_recentes,
        labels_status=labels_status,
        valores_status=valores_status,
        labels_meses=labels_meses,
        valores_meses=valores_meses,
                receber_vencidas=receber_vencidas,
        receber_7=receber_7,
        receber_30=receber_30,
        receber_total_pendente=receber_total_pendente,
        pagar_vencidas=pagar_vencidas,
        pagar_7=pagar_7,
        pagar_30=pagar_30,
        pagar_total_pendente=pagar_total_pendente,
        caixa_entradas=caixa_entradas,
        caixa_saidas=caixa_saidas,
        caixa_saldo=caixa_saldo,
        inadimplencia_valor=inadimplencia_valor,
        inadimplencia_pct=inadimplencia_pct,
        os_paradas_7=os_paradas_7,
        os_paradas_15=os_paradas_15,
        valor_preso_7=valor_preso_7,
        valor_preso_15=valor_preso_15,
        fat_mes_atual=fat_mes_atual,
        fat_mes_anterior=fat_mes_anterior,
        variacao_mes_pct=variacao_mes_pct,
        variacao_mes_valor=variacao_mes_valor,
        top_produtos=top_produtos,
        produtos_criticos=produtos_criticos,
        margem_pecas_pct=margem_pecas_pct,
        top_clientes=top_clientes,
        comissoes=comissoes,
        total_comissoes=total_comissoes,
        agendamentos_hoje=agendamentos_hoje,
        agendamentos_amanha=agendamentos_amanha,
    )


@app.route("/ordens/retrabalho/<int:id>", methods=["POST"])
@login_required
def abrir_retrabalho(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    origem = OrdemServico.query.filter_by(id=id, empresa_id=eid).first()
    if not origem:
        return redirect("/ordens")
    try:
        ano = date.today().year
        prefixo = ano * 10000
        ultimo = db.session.query(func.max(OrdemServico.numero)).scalar() or 0
        numero = prefixo + 1 if ultimo < prefixo else ultimo + 1
        nova = OrdemServico(
            numero=numero,
            cliente_id=origem.cliente_id,
            veiculo_id=origem.veiculo_id,
            km=getattr(origem, "km", None),
            status="RETRABALHO",
            data_abertura=datetime.now(),
            empresa_id=eid,
            mecanico_id=getattr(origem, "mecanico_id", None),
            mecanico=getattr(origem, "mecanico", None),
            os_origem_id=origem.id,
            is_retrabalho=True,
            defeito_relatado=f"RETRABALHO da OS {origem.numero or origem.id}",
            valor_servicos=0,
            valor_produtos=0,
            desconto=0,
            valor_total=0,
        )
        db.session.add(nova)
        db.session.commit()
        return redirect(f"/ordens/editar/{nova.id}")
    except Exception as e:
        db.session.rollback()
        print("Erro retrabalho:", e)
        return redirect(f"/ordens/editar/{origem.id}")

@app.route("/clientes")
@login_required
def clientes():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    lista_clientes = Cliente.query.filter_by(empresa_id=eid).order_by(Cliente.nome).all()
    return render_template("clientes.html", clientes=lista_clientes)


@app.route("/clientes/novo", methods=["GET", "POST"])
@login_required
def novo_cliente():
    if request.method == "POST":
        cpf = (request.form.get("cpf_cnpj") or "").strip()
        if cpf:
            eid = empresa_atual()
            existente = Cliente.query.filter(
                Cliente.cpf_cnpj == cpf,
                Cliente.empresa_id == eid
            ).first()
            if existente:
                return redirect(f"/clientes/editar/{existente.id}?aviso=cpf_existente")

        data_nasc = request.form.get("data_nascimento")
        cliente = Cliente(
            empresa_id=empresa_atual() or 1,
            nome=request.form.get("nome"),
            cpf_cnpj=cpf or None,
            telefone=request.form.get("telefone"),
            whatsapp=request.form.get("whatsapp"),
            email=request.form.get("email"),
            endereco=request.form.get("endereco"),
            cidade=request.form.get("cidade"),
            estado=request.form.get("estado"),
            observacoes=request.form.get("observacoes"),
            data_nascimento=datetime.strptime(data_nasc, "%Y-%m-%d").date() if data_nasc else None
        )
        db.session.add(cliente)
        db.session.commit()
        return redirect("/clientes")
    return render_template("novo_cliente.html")


@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_cliente(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    cliente = Cliente.query.filter_by(id=id, empresa_id=eid).first_or_404()

    if request.method == "POST":
        data_nasc = request.form.get("data_nascimento")
        cliente.nome = request.form.get("nome")
        cliente.cpf_cnpj = request.form.get("cpf_cnpj")
        cliente.telefone = request.form.get("telefone")
        cliente.whatsapp = request.form.get("whatsapp")
        cliente.email = request.form.get("email")
        cliente.endereco = request.form.get("endereco")
        if data_nasc:
            try:
                cliente.data_nascimento = datetime.strptime(data_nasc, "%Y-%m-%d").date()
            except Exception:
                pass
        db.session.commit()
        return redirect("/clientes")

    return render_template("editar_cliente.html", cliente=cliente)


@app.route("/clientes/excluir/<int:id>")
@login_required
def excluir_cliente(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    cliente = Cliente.query.filter_by(id=id, empresa_id=eid).first_or_404()
    db.session.delete(cliente)
    db.session.commit()
    return redirect("/clientes")

@app.route("/veiculos")
@login_required
def veiculos():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    lista_veiculos = Veiculo.query.filter_by(empresa_id=eid).order_by(Veiculo.placa).all()
    return render_template("veiculos.html", veiculos=lista_veiculos)


@app.route("/veiculos/novo", methods=["GET", "POST"])
@login_required
def novo_veiculo():
    if request.method == "POST":
        placa = request.form["placa"].upper().strip()

        existente = Veiculo.query.filter(
            Veiculo.placa == placa,
            Veiculo.empresa_id == (empresa_atual() or 1)
        ).first()
        if existente:
            return redirect(f"/veiculos/editar/{existente.id}?aviso=placa_existente")

        data_rev = request.form.get("proxima_revisao_data")
        km_rev = request.form.get("proxima_revisao_km")

        veiculo = Veiculo(
            empresa_id=empresa_atual() or 1,
            cliente_id=int(request.form["cliente_id"]),
            placa=placa,
            marca=request.form.get("marca"),
            modelo=request.form.get("modelo"),
            cor=request.form.get("cor"),
            km=int(request.form["km"]) if request.form.get("km") else None,
            chassi=request.form.get("chassi"),
            renavam=request.form.get("renavam", ""),
            motor=request.form.get("motor"),
            combustivel=request.form.get("combustivel"),
            observacoes=request.form.get("observacoes", ""),
            proxima_revisao_data=datetime.strptime(data_rev, "%Y-%m-%d").date() if data_rev else None,
            proxima_revisao_km=int(km_rev) if km_rev else None,
        )
        db.session.add(veiculo)
        db.session.commit()
        return redirect("/veiculos")
    eid = empresa_atual()
    clientes = (
        Cliente.query.filter_by(empresa_id=eid)
        .order_by(Cliente.nome)
        .all()
    )
    return render_template("novo_veiculo.html", clientes=clientes)


@app.route("/veiculos/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_veiculo(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    veiculo = Veiculo.query.filter_by(id=id, empresa_id=eid).first_or_404()
    aviso = request.args.get("aviso")

    if request.method == "POST":
        data_rev = request.form.get("proxima_revisao_data")
        km_rev = request.form.get("proxima_revisao_km")

        veiculo.cliente_id = int(request.form["cliente_id"])
        veiculo.placa = request.form["placa"].upper()
        veiculo.marca = request.form.get("marca")
        veiculo.modelo = request.form.get("modelo")
        veiculo.cor = request.form.get("cor")
        veiculo.km = int(request.form["km"]) if request.form.get("km") else None
        veiculo.chassi = request.form.get("chassi")
        veiculo.renavam = request.form.get("renavam", "")
        veiculo.motor = request.form.get("motor")
        veiculo.combustivel = request.form.get("combustivel")
        veiculo.observacoes = request.form.get("observacoes", "")
        veiculo.proxima_revisao_data = datetime.strptime(data_rev, "%Y-%m-%d").date() if data_rev else None
        veiculo.proxima_revisao_km = int(km_rev) if km_rev else None
        db.session.commit()
        return redirect("/veiculos")

    clientes = (
        Cliente.query.filter_by(empresa_id=eid)
        .order_by(Cliente.nome)
        .all()
    )
    return render_template(
        "novo_veiculo.html",
        veiculo=veiculo,
        clientes=clientes,
        aviso=aviso,
    )


@app.route("/veiculos/excluir/<int:id>")
@login_required
def excluir_veiculo(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    veiculo = Veiculo.query.filter_by(id=id, empresa_id=eid).first_or_404()
    db.session.delete(veiculo)
    db.session.commit()
    return redirect("/veiculos")


# ============================================================
# ORDENS COM FILTRO DE DATA + STATUS
# ============================================================
@app.route("/ordens")
@login_required
def ordens():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")

    periodo = request.args.get("periodo")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    status = request.args.get("status")

    query = OrdemServico.query.filter_by(empresa_id=eid)
    hoje = date.today()

    if periodo == "hoje":
        query = query.filter(func.date(OrdemServico.data_abertura) == hoje)
    elif periodo == "semana":
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        query = query.filter(func.date(OrdemServico.data_abertura) >= inicio_semana)
    elif periodo == "mes":
        inicio_mes = hoje.replace(day=1)
        query = query.filter(func.date(OrdemServico.data_abertura) >= inicio_mes)
    elif periodo == "ano":
        inicio_ano = hoje.replace(month=1, day=1)
        query = query.filter(func.date(OrdemServico.data_abertura) >= inicio_ano)
    elif data_inicio:
        try:
            di = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            query = query.filter(func.date(OrdemServico.data_abertura) >= di)
            if data_fim:
                df = datetime.strptime(data_fim, "%Y-%m-%d").date()
                query = query.filter(func.date(OrdemServico.data_abertura) <= df)
        except:
            pass

    if status:
        query = query.filter(OrdemServico.status == status)

    lista_ordens = query.order_by(OrdemServico.id.desc()).all()

    return render_template(
        "ordens.html",
        ordens=lista_ordens,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        status=status
    )
@app.route("/abrir-os-placa", methods=["GET", "POST"])
@login_required
def ordens_por_placa():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    placa = None

    if request.args.get("placa"):
        placa = request.args.get("placa").strip().upper().replace("-", "").replace(" ", "")
    elif request.method == "POST":
        placa = (request.form.get("placa") or "").strip().upper().replace("-", "").replace(" ", "")

    if not placa:
        return render_template("ordens_por_placa.html")

    if len(placa) < 7:
        return render_template(
            "ordens_por_placa.html",
            mensagem="Digite uma placa válida (mínimo 7 caracteres).",
            tipo_alerta="warning",
            placa_digitada=placa
        )

    placa_limpa = placa.replace("-", "").replace(" ", "")
    veiculo = Veiculo.query.filter(
        Veiculo.empresa_id == eid,
        db.func.replace(db.func.replace(Veiculo.placa, "-", ""), " ", "") == placa_limpa
    ).first()

    if not veiculo:
        return render_template(
            "ordens_por_placa.html",
            mensagem=f"Nenhum veículo encontrado com a placa {placa}.",
            tipo_alerta="danger",
            mostrar_botao_cadastro=True,
            placa_digitada=placa
        )
    try:
        ano = date.today().year
        prefixo = ano * 10000
        ultimo = db.session.query(func.max(OrdemServico.numero)).scalar() or 0
        numero = prefixo + 1 if ultimo < prefixo else ultimo + 1

        ordem = OrdemServico(
            numero=numero,
            cliente_id=veiculo.cliente_id,
            veiculo_id=veiculo.id,
            km=veiculo.km,
            status="ABERTA",
            data_abertura=datetime.now(),
            empresa_id=session.get("empresa_id") or 1,
            valor_servicos=0,
            valor_produtos=0,
            desconto=0,
            valor_total=0,
        )
        db.session.add(ordem)
        db.session.commit()
        return redirect(f"/ordens/editar/{ordem.id}")
    except Exception as e:
        db.session.rollback()
        return render_template(
            "ordens_por_placa.html",
            mensagem=f"Erro ao criar a OS: {str(e)}",
            tipo_alerta="danger",
            placa_digitada=placa
        )


@app.route("/api/ler-placa", methods=["POST"])
@login_required
def api_ler_placa():
    if "foto" not in request.files:
        return jsonify({"sucesso": False, "mensagem": "Nenhuma foto enviada"})

    foto = request.files["foto"]
    if foto.filename == "":
        return jsonify({"sucesso": False, "mensagem": "Arquivo inválido"})

    try:
        import easyocr
        import numpy as np
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(foto.read()))
        img_np = np.array(img)

        reader = easyocr.Reader(['pt', 'en'], gpu=False)
        results = reader.readtext(img_np)

        placa = ""
        for (bbox, texto, conf) in results:
            texto_limpo = texto.replace(" ", "").replace("-", "").upper()
            if conf > 0.35 and 7 <= len(texto_limpo) <= 8:
                placa = texto_limpo[:7]
                break

        if not placa:
            return jsonify({
                "sucesso": False, 
                "mensagem": "Não foi possível identificar a placa. Tente uma foto mais nítida e centralizada."
            })

        return jsonify({"sucesso": True, "placa": placa})

    except Exception as e:
        print("Erro OCR:", e)
        return jsonify({"sucesso": False, "mensagem": f"Erro ao processar imagem: {str(e)}"})


@app.route("/ordens/nova", methods=["GET", "POST"])
@login_required
def nova_ordem():
    if request.method == "POST":
        valor_pecas = float(request.form.get("valor_pecas") or 0)
        desconto = float(request.form.get("desconto") or 0)

        descs = request.form.getlist("servico_desc")
        mecs = request.form.getlist("servico_mecanico_id")
        horas_list = request.form.getlist("servico_horas")
        minutos_list = request.form.getlist("servico_minutos")
        vals = request.form.getlist("servico_valor")
        comissoes = request.form.getlist("servico_comissao")

        nomes = []
        total_servicos = 0.0
        detalhes = []

        for i in range(len(descs)):
            try:
                mid = int(mecs[i]) if i < len(mecs) and mecs[i] else 0
                if mid <= 0:
                    continue
                m = Mecanico.query.get(mid)
                if not m:
                    continue
                serv = (descs[i] or "").strip() or m.nome
                horas = int(horas_list[i] or 0) if i < len(horas_list) else 0
                minutos = int(minutos_list[i] or 0) if i < len(minutos_list) else 40
                dur = (horas * 60) + minutos
                if dur < 5:
                    dur = 40
                val = float(vals[i]) if i < len(vals) and vals[i] else 0

                try:
                    perc_form = float(comissoes[i]) if i < len(comissoes) and comissoes[i] else None
                except Exception:
                    perc_form = None

                nomes.append(m.nome)
                total_servicos += val
                detalhes.append({
                    "mecanico": m,
                    "duracao": dur,
                    "valor": val,
                    "servico": serv,
                    "comissao": perc_form if perc_form is not None else float(m.percentual_comissao or 20),
                })
            except Exception:
                pass

        total = total_servicos + valor_pecas - desconto

        # Número no padrão 20260001, 20260002...
        ano = date.today().year
        prefixo = ano * 10000  # 20260000
        ultimo = db.session.query(func.max(OrdemServico.numero)).scalar() or 0
        if ultimo < prefixo:
            numero = prefixo + 1
        else:
            numero = ultimo + 1

        ordem = OrdemServico(
            numero=numero,
            cliente_id=int(request.form["cliente_id"]),
            veiculo_id=int(request.form["veiculo_id"]),
            km=int(request.form["km"]) if request.form.get("km") else None,
            defeito_relatado=request.form.get("defeito_relatado"),
            diagnostico=request.form.get("diagnostico"),
            servico_executado=request.form.get("servico_executado"),
            mecanico=", ".join(dict.fromkeys(nomes)) if nomes else None,
            valor_servicos=total_servicos,
            valor_produtos=valor_pecas,
            desconto=desconto,
            valor_total=total,
            status="ABERTA",
        )
        try:
            ordem.empresa_id = session.get("empresa_id") or 1
        except Exception:
            pass

        db.session.add(ordem)
        db.session.flush()

        agendar = request.form.get("agendar_auto") == "sim"
        hoje = date.today()

        for d in detalhes:
            m = d["mecanico"]
            perc = float(d.get("comissao") if d.get("comissao") is not None else (m.percentual_comissao or 20))
            base = d["valor"]
            comissao = round(base * perc / 100.0, 2)
            db.session.add(OrdemServicoMecanico(
                ordem_servico_id=ordem.id,
                mecanico_id=m.id,
                duracao_estimada_min=d["duracao"],
                valor_mercado=0,
                valor_negociado=d["valor"],
                percentual_comissao=perc,
                base_comissao=base,
                valor_comissao=comissao,
                descricao_servico=d["servico"],
            ))
            if agendar:
                entrada = int(m.hora_entrada or 9)
                almoco_i = int(m.almoco_inicio or 12)
                almoco_f = int(m.almoco_fim or 14)
                ocupados = Agendamento.query.filter_by(
                    mecanico_id=m.id, data=hoje
                ).order_by(Agendamento.hora_inicio).all()
                cursor = entrada * 60
                for ag in ocupados:
                    try:
                        h, mi = map(int, ag.hora_inicio.split(":"))
                        ini = h * 60 + mi
                        dur_ag = ag.duracao_real_min or ag.duracao_estimada_min or 40
                        fim = ini + dur_ag
                        if fim > cursor:
                            cursor = fim
                    except Exception:
                        pass
                if cursor >= almoco_i * 60 and cursor < almoco_f * 60:
                    cursor = almoco_f * 60
                h_ini = f"{cursor // 60:02d}:{cursor % 60:02d}"
                fim_min = cursor + d["duracao"]
                h_fim = f"{fim_min // 60:02d}:{fim_min % 60:02d}"
                placa = ""
                try:
                    v = Veiculo.query.get(ordem.veiculo_id)
                    if v:
                        placa = v.placa or ""
                except Exception:
                    pass
                desc = d["servico"]
                if placa:
                    desc = f"{desc} - {placa}"
                db.session.add(Agendamento(
                    mecanico_id=m.id,
                    ordem_servico_id=ordem.id,
                    data=hoje,
                    hora_inicio=h_ini,
                    duracao_estimada_min=d["duracao"],
                    duracao_real_min=d["duracao"],
                    hora_fim=h_fim,
                    descricao=desc,
                    status="AGENDADO",
                ))
                # ===== PEÇAS / PRODUTOS =====
        produtos_ids = request.form.getlist("item_produto_id")
        tipos = request.form.getlist("item_tipo")
        descricoes = request.form.getlist("item_descricao")
        qtds = request.form.getlist("item_qtd")
        valores_unit = request.form.getlist("item_valor_unit")
        custos = request.form.getlist("item_custo")

        n = max(len(produtos_ids), len(tipos), len(descricoes), len(qtds), len(valores_unit))

        for i in range(n):
            try:
                tipo = (tipos[i] if i < len(tipos) else "ESTOQUE") or "ESTOQUE"
                tipo = tipo.upper().strip()

                try:
                    pid = int(produtos_ids[i] or 0) if i < len(produtos_ids) else 0
                except Exception:
                    pid = 0

                desc = (descricoes[i] if i < len(descricoes) else "") or ""
                desc = desc.strip()

                try:
                    qtd = float(qtds[i] if i < len(qtds) else 1)
                except Exception:
                    qtd = 1.0

                try:
                    vu = float(valores_unit[i] if i < len(valores_unit) else 0)
                except Exception:
                    vu = 0.0

                if qtd <= 0:
                    continue

                prod = None
                if tipo == "ESTOQUE" and pid > 0:
                    prod = Produto.query.get(pid)
                    if prod and not desc:
                        desc = prod.descricao or f"Produto #{pid}"
                elif not desc:
                    continue

                if not desc:
                    desc = "Peça"
                try:
                    custo = float(custos[i] if i < len(custos) else 0)
                except Exception:
                    custo = 0.0

                if custo == 0 and tipo == "ESTOQUE" and prod:
                    custo = float(prod.preco_compra or 0)

                item = ItemOrdemServico(
                    ordem_servico_id=ordem.id,
                    produto_id=pid if pid > 0 else None,
                    origem=tipo if tipo in ("ESTOQUE", "PARCEIRO") else "ESTOQUE",
                    tipo_item="PRODUTO",
                    descricao=desc,
                    quantidade=qtd,
                    custo_unitario=custo,
                    valor_unitario=vu,
                    valor_total=qtd * vu,
                )
                db.session.add(item)

                if prod is not None and hasattr(prod, "estoque_atual"):
                    atual = float(prod.estoque_atual or 0)
                    prod.estoque_atual = max(0, atual - qtd)

            except Exception as e:
                print("Erro item OS:", e)

        db.session.commit()
        return redirect("/ordens")

        eid = empresa_atual()
    if not eid:
        return redirect("/login")

    clientes = Cliente.query.filter_by(empresa_id=eid).order_by(Cliente.nome).all()
    veiculos = Veiculo.query.filter_by(empresa_id=eid).order_by(Veiculo.placa).all()

    try:
        lista_mecanicos = Mecanico.query.filter_by(empresa_id=eid, ativo=True).order_by(Mecanico.nome).all()
    except Exception:
        lista_mecanicos = []

    try:
        lista_produtos = Produto.query.filter_by(empresa_id=eid).order_by(Produto.descricao).all()
    except Exception:
        lista_produtos = []

    try:
        lista_fornecedores = Fornecedor.query.filter_by(empresa_id=eid).order_by(Fornecedor.razao_social).all()
    except Exception:
        lista_fornecedores = []

    return render_template(
        "nova_ordem.html",
        clientes=clientes,
        veiculos=veiculos,
        mecanicos=lista_mecanicos,
        produtos=lista_produtos,
        fornecedores=lista_fornecedores,
    )


@app.route("/ordens/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_ordem(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    ordem = OrdemServico.query.filter_by(id=id, empresa_id=eid).first_or_404()

    # BLOQUEIA EDIÇÃO SE JÁ ESTIVER FINALIZADA
    if ordem.status == "FINALIZADA":
        return redirect("/ordens")

    if request.method == "POST":
        valor_pecas = float(request.form.get("valor_pecas") or 0)
        desconto = float(request.form.get("desconto") or 0)

        descs = request.form.getlist("servico_desc")
        mecs = request.form.getlist("servico_mecanico_id")
        horas_list = request.form.getlist("servico_horas")
        minutos_list = request.form.getlist("servico_minutos")
        vals = request.form.getlist("servico_valor")
        comissoes = request.form.getlist("servico_comissao")

        nomes = []
        total_servicos = 0.0
        detalhes = []

        for i in range(len(descs)):
            try:
                mid = int(mecs[i]) if i < len(mecs) and mecs[i] else 0
                if mid <= 0:
                    continue
                m = Mecanico.query.get(mid)
                if not m:
                    continue
                serv = (descs[i] or "").strip() or m.nome
                horas = int(horas_list[i] or 0) if i < len(horas_list) else 0
                minutos = int(minutos_list[i] or 0) if i < len(minutos_list) else 40
                dur = (horas * 60) + minutos
                if dur < 5:
                    dur = 40
                val = float(vals[i]) if i < len(vals) and vals[i] else 0

                try:
                    perc_form = float(comissoes[i]) if i < len(comissoes) and comissoes[i] else None
                except Exception:
                    perc_form = None

                nomes.append(m.nome)
                total_servicos += val
                detalhes.append({
                    "mecanico": m,
                    "duracao": dur,
                    "valor": val,
                    "servico": serv,
                    "comissao": perc_form if perc_form is not None else float(m.percentual_comissao or 20),
                })
            except Exception:
                pass

        total = total_servicos + valor_pecas - desconto

        ordem.cliente_id = int(request.form["cliente_id"])
        ordem.veiculo_id = int(request.form["veiculo_id"])
        ordem.km = int(request.form["km"]) if request.form.get("km") else None
        ordem.defeito_relatado = request.form.get("defeito_relatado")
        ordem.diagnostico = request.form.get("diagnostico")
        ordem.servico_executado = request.form.get("servico_executado")
        ordem.mecanico = ", ".join(nomes) if nomes else ordem.mecanico
        ordem.valor_servicos = total_servicos
        ordem.valor_produtos = valor_pecas
        ordem.desconto = desconto
        ordem.valor_total = total
        ordem.status = request.form.get("status") or "ABERTA"

        # Remove serviços e peças antigos
        OrdemServicoMecanico.query.filter_by(ordem_servico_id=ordem.id).delete()
        ItemOrdemServico.query.filter_by(ordem_servico_id=ordem.id).delete()
        db.session.flush()

        # Serviços novos
        for d in detalhes:
            m = d["mecanico"]
            perc = float(d.get("comissao") if d.get("comissao") is not None else (m.percentual_comissao or 20))
            base = d["valor"]
            comissao = round(base * perc / 100.0, 2)
            db.session.add(OrdemServicoMecanico(
                ordem_servico_id=ordem.id,
                mecanico_id=m.id,
                duracao_estimada_min=d["duracao"],
                valor_mercado=0,
                valor_negociado=d["valor"],
                percentual_comissao=perc,
                base_comissao=base,
                valor_comissao=comissao,
                descricao_servico=d["servico"],
            ))

        # Peças novas
        produtos_ids = request.form.getlist("item_produto_id")
        tipos = request.form.getlist("item_tipo")
        descricoes = request.form.getlist("item_descricao")
        qtds = request.form.getlist("item_qtd")
        valores_unit = request.form.getlist("item_valor_unit")
        custos = request.form.getlist("item_custo")

        n = max(len(produtos_ids), len(tipos), len(descricoes), len(qtds), len(valores_unit))

        for i in range(n):
            try:
                tipo = (tipos[i] if i < len(tipos) else "ESTOQUE") or "ESTOQUE"
                tipo = tipo.upper().strip()

                try:
                    pid = int(produtos_ids[i] or 0) if i < len(produtos_ids) else 0
                except Exception:
                    pid = 0

                desc = (descricoes[i] if i < len(descricoes) else "") or ""
                desc = desc.strip()

                try:
                    qtd = float(qtds[i] if i < len(qtds) else 1)
                except Exception:
                    qtd = 1.0

                try:
                    vu = float(valores_unit[i] if i < len(valores_unit) else 0)
                except Exception:
                    vu = 0.0

                if qtd <= 0:
                    continue

                prod = None
                if tipo == "ESTOQUE" and pid > 0:
                    prod = Produto.query.get(pid)
                    if prod and not desc:
                        desc = prod.descricao or f"Produto #{pid}"
                elif not desc:
                    continue

                if not desc:
                    desc = "Peça"
                try:
                    custo = float(custos[i] if i < len(custos) else 0)
                except Exception:
                    custo = 0.0

                if custo == 0 and tipo == "ESTOQUE" and prod:
                    custo = float(prod.preco_compra or 0)

                db.session.add(ItemOrdemServico(
                    ordem_servico_id=ordem.id,
                    produto_id=pid if pid > 0 else None,
                    origem=tipo if tipo in ("ESTOQUE", "PARCEIRO") else "ESTOQUE",
                    tipo_item="PRODUTO",
                    descricao=desc,
                    quantidade=qtd,
                    custo_unitario=custo,
                    valor_unitario=vu,
                    valor_total=qtd * vu,
                ))
            except Exception as e:
                print("Erro item OS (edit):", e)

        db.session.commit()
        return redirect("/ordens")

    eid = empresa_atual()
    if not eid:
        return redirect("/login")

    clientes = Cliente.query.filter_by(empresa_id=eid).order_by(Cliente.nome).all()
    veiculos = Veiculo.query.filter_by(empresa_id=eid).order_by(Veiculo.placa).all()

    try:
        mecanicos = Mecanico.query.filter_by(empresa_id=eid, ativo=True).order_by(Mecanico.nome).all()
    except Exception:
        mecanicos = []

    try:
        produtos = Produto.query.filter_by(empresa_id=eid).order_by(Produto.descricao).all()
    except Exception:
        produtos = []

    servicos_os = OrdemServicoMecanico.query.filter_by(ordem_servico_id=ordem.id).all()
    itens_os = ItemOrdemServico.query.filter_by(ordem_servico_id=ordem.id).all()

    return render_template(
        "editar_ordem.html",
        ordem=ordem,
        clientes=clientes,
        veiculos=veiculos,
        mecanicos=mecanicos,
        produtos=produtos,
        servicos_os=servicos_os,
        itens_os=itens_os,
    )



@app.route("/ordens/finalizar/<int:id>")
@login_required
def finalizar_ordem(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    ordem = OrdemServico.query.filter_by(id=id, empresa_id=eid).first_or_404()
    ordem.status = "FINALIZADA"
    db.session.commit()
    return redirect("/ordens")


@app.route("/ordens/excluir/<int:id>")
@login_required
def excluir_ordem(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    ordem = OrdemServico.query.filter_by(id=id, empresa_id=eid).first_or_404()

    # Apaga primeiro tudo que está ligado à ordem
    OrdemServicoMecanico.query.filter_by(ordem_servico_id=ordem.id).delete()
    ItemOrdemServico.query.filter_by(ordem_servico_id=ordem.id).delete()
    Agendamento.query.filter_by(ordem_servico_id=ordem.id).delete()

    db.session.delete(ordem)
    db.session.commit()
    return redirect("/ordens")


@app.route("/ordens/pdf/<int:id>")
@login_required
def pdf_ordem(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    ordem = OrdemServico.query.filter_by(id=id, empresa_id=eid).first_or_404()
    try:
        pdf = gerar_pdf_ordem(ordem)
        return send_file(
            pdf,
            download_name=f"OS_{ordem.numero or ordem.id}.pdf",
            as_attachment=False,
            mimetype="application/pdf",
        )
    except Exception as e:
        print("Erro PDF ordem:", e)
        return f"<h1>OS #{ordem.numero or ordem.id}</h1><p>Total: R$ {ordem.valor_total or 0}</p>"


@app.route("/api/veiculos/<int:cliente_id>")
@login_required
def api_veiculos(cliente_id):
    lista = Veiculo.query.filter_by(cliente_id=cliente_id).order_by(Veiculo.placa).all()
    return jsonify([
        {"id": v.id, "placa": v.placa, "marca": getattr(v, "marca", None), "modelo": getattr(v, "modelo", None), "km": getattr(v, "km", None)}
        for v in lista
    ])


@app.route("/estoque")
@login_required
def estoque():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    try:
        lista_produtos = Produto.query.filter_by(empresa_id=eid).order_by(Produto.descricao).all()
    except Exception:
        lista_produtos = []
    try:
        categorias = Categoria.query.filter_by(empresa_id=eid).order_by(Categoria.nome).all()
    except Exception:
        categorias = []
    try:
        fabricantes = Fabricante.query.filter_by(empresa_id=eid).order_by(Fabricante.nome).all()
    except Exception:
        fabricantes = []
    try:
        fornecedores = Fornecedor.query.filter_by(empresa_id=eid).order_by(Fornecedor.razao_social).all()
    except Exception:
        fornecedores = []
    total_produtos = len(lista_produtos)
    valor_total_estoque = 0
    estoque_baixo = 0
    for p in lista_produtos:
        try:
            estoque_atual = float(getattr(p, "estoque_atual", 0) or 0)
            preco = float(getattr(p, "preco_venda", 0) or 0)
            valor_total_estoque += estoque_atual * preco
            minimo = float(getattr(p, "estoque_minimo", 0) or 0)
            if estoque_atual <= minimo:
                estoque_baixo += 1
        except Exception:
            pass
    return render_template(
        "estoque.html",
        produtos=lista_produtos,
        categorias=categorias,
        fabricantes=fabricantes,
        fornecedores=fornecedores,
        total_produtos=total_produtos,
        valor_total_estoque=valor_total_estoque,
        estoque_baixo=estoque_baixo,
        total_categorias=len(categorias)
    )


@app.route("/produtos")
@login_required
def produtos():
        eid = empresa_atual()
        if not eid:
           return redirect("/login")
        return redirect("/estoque")


@app.route("/produtos/novo", methods=["GET", "POST"])
@login_required
def novo_produto():
    if request.method == "POST":
        try:
            produto = Produto(
                codigo=(request.form.get("codigo") or "").strip() or None,
                descricao=(request.form.get("descricao") or "").strip(),
                unidade=request.form.get("unidade") or "UN",
                estoque_atual=float(request.form.get("estoque_atual") or 0),
                estoque_minimo=float(request.form.get("estoque_minimo") or 0),
                preco_venda=float(request.form.get("preco_venda") or 0),
                ativo=True,
            )
            produto.empresa_id = empresa_atual() or 1
            produto.categoria_id = int(request.form.get("categoria_id") or 1)
            if request.form.get("fabricante_id"):
                produto.fabricante_id = int(request.form.get("fabricante_id"))
            if hasattr(produto, "preco_compra"):
                produto.preco_compra = float(request.form.get("preco_compra") or 0)
            db.session.add(produto)
            db.session.commit()
            return redirect("/estoque")
        except Exception as e:
            db.session.rollback()
            print("Erro produto:", e)
    try:
        categorias = Categoria.query.filter_by(empresa_id=eid).order_by(Categoria.nome).all()
    except Exception:
        categorias = []
    try:
        fabricantes = Fabricante.query.filter_by(empresa_id=eid).order_by(Fabricante.nome).all()
    except Exception:
        fabricantes = []
    return render_template("novo_produto.html", categorias=categorias, fabricantes=fabricantes)


@app.route("/produtos/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_produto(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    produto = Produto.query.filter_by(id=id, empresa_id=eid).first_or_404()

    if request.method == "POST":
        try:
            produto.codigo = (request.form.get("codigo") or "").strip() or None
            produto.descricao = (request.form.get("descricao") or "").strip()
            produto.unidade = request.form.get("unidade") or "UN"
            produto.estoque_atual = float(request.form.get("estoque_atual") or 0)
            produto.estoque_minimo = float(request.form.get("estoque_minimo") or 0)
            produto.preco_venda = float(request.form.get("preco_venda") or 0)
            if hasattr(produto, "preco_compra"):
                produto.preco_compra = float(request.form.get("preco_compra") or 0)
            produto.categoria_id = int(request.form.get("categoria_id") or 1)
            produto.empresa_id = getattr(produto, "empresa_id", None) or 1
            if request.form.get("fabricante_id"):
                produto.fabricante_id = int(request.form.get("fabricante_id"))
            else:
                produto.fabricante_id = None
            db.session.commit()
            return redirect("/estoque")
        except Exception as e:
            db.session.rollback()
            print("Erro editar produto:", e)
    try:
        categorias = Categoria.query.filter_by(empresa_id=eid).order_by(Categoria.nome).all()
    except Exception:
        categorias = []
    try:
        fabricantes = Fabricante.query.filter_by(empresa_id=eid).order_by(Fabricante.nome).all()
    except Exception:
        fabricantes = []
    return render_template("editar_produto.html", produto=produto, categorias=categorias, fabricantes=fabricantes)


@app.route("/produtos/excluir/<int:id>")
@login_required
def excluir_produto(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    produto = Produto.query.filter_by(id=id, empresa_id=eid).first_or_404()
    try:
        db.session.delete(produto)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro excluir produto:", e)
    return redirect("/estoque")
@app.route("/categorias")
@login_required
def categorias():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    try:
        lista = Categoria.query.filter_by(empresa_id=eid).order_by(Categoria.nome).all()
    except Exception:
        lista = []
    return render_template("categorias.html", categorias=lista)


@app.route("/categorias/novo", methods=["GET", "POST"])
@app.route("/categorias/salvar", methods=["POST"])
@login_required
def nova_categoria():
    if request.method == "POST":
        try:
            cat_id = request.form.get("id")
            nome = (request.form.get("nome") or request.form.get("descricao") or "").strip()
            if not nome:
                return redirect("/categorias")
            if cat_id:
                cat = Categoria.query.get(int(cat_id))
                if cat:
                    cat.nome = nome
                    if hasattr(cat, "descricao"):
                        cat.descricao = request.form.get("descricao")
                    if hasattr(cat, "ativo"):
                        cat.ativo = True if request.form.get("ativo") else True
            else:
                cat = Categoria(nome=nome)
                if hasattr(cat, "empresa_id"):
                    cat.empresa_id = 1
                if hasattr(cat, "descricao"):
                    cat.descricao = request.form.get("descricao")
                if hasattr(cat, "ativo"):
                    cat.ativo = True
                db.session.add(cat)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("Erro categoria:", e)
        return redirect("/categorias")
    return redirect("/categorias")


@app.route("/categorias/excluir/<int:id>")
@login_required
def excluir_categoria(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    try:
        cat = Categoria.query.filter_by(id=id, empresa_id=eid).first_or_404()
        db.session.delete(cat)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro excluir categoria:", e)
    return redirect("/categorias")


@app.route("/fabricantes")
@login_required
def fabricantes():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    try:
        lista = Fabricante.query.filter_by(empresa_id=eid).order_by(Fabricante.nome).all()
    except Exception:
        lista = []
    return render_template("fabricantes.html", fabricantes=lista)


@app.route("/fabricantes/novo", methods=["GET", "POST"])
@app.route("/fabricantes/salvar", methods=["POST"])
@login_required
def novo_fabricante():
    if request.method == "POST":
        try:
            fab = Fabricante(
                nome=request.form.get("nome"),
                site=request.form.get("site"),
                telefone=request.form.get("telefone"),
                email=request.form.get("email"),
                observacoes=request.form.get("observacoes"),
                ativo=True
            )
            if hasattr(fab, "empresa_id"):
                fab.empresa_id = 1
            db.session.add(fab)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("Erro fabricante:", e)
        return redirect("/fabricantes")
    return redirect("/fabricantes")


@app.route("/fabricantes/excluir/<int:id>")
@login_required
def excluir_fabricante(id):
    try:
        fab = Fabricante.query.filter_by(id=id, empresa_id=eid).first_or_404()
        db.session.delete(fab)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro excluir fabricante:", e)
    return redirect("/fabricantes")


@app.route("/fornecedores")
@login_required
def fornecedores():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")

    try:
        lista = Fornecedor.query.filter_by(empresa_id=eid).order_by(Fornecedor.razao_social).all()
    except Exception:
        lista = []
    return render_template("fornecedores.html", fornecedores=lista)


@app.route("/fornecedores/novo", methods=["GET", "POST"])
@app.route("/fornecedores/salvar", methods=["POST"])
@login_required
def novo_fornecedor():
    if request.method == "POST":
        try:
            razao = (
                request.form.get("razao_social")
                or request.form.get("nome")
                or request.form.get("nome_fantasia")
                or ""
            ).strip()
            if not razao:
                return redirect("/fornecedores")

            forn = Fornecedor()
            if hasattr(forn, "empresa_id"):
                forn.empresa_id = empresa_atual() or 1
            if hasattr(forn, "razao_social"):
                forn.razao_social = razao
            if hasattr(forn, "nome_fantasia"):
                forn.nome_fantasia = request.form.get("nome_fantasia") or razao
            if hasattr(forn, "cnpj"):
                forn.cnpj = request.form.get("cnpj")
            if hasattr(forn, "inscricao_estadual"):
                forn.inscricao_estadual = request.form.get("inscricao_estadual")
            if hasattr(forn, "telefone"):
                forn.telefone = request.form.get("telefone")
            if hasattr(forn, "whatsapp"):
                forn.whatsapp = request.form.get("whatsapp")
            if hasattr(forn, "email"):
                forn.email = request.form.get("email")
            if hasattr(forn, "site"):
                forn.site = request.form.get("site")
            if hasattr(forn, "cep"):
                forn.cep = request.form.get("cep")
            if hasattr(forn, "endereco"):
                forn.endereco = request.form.get("endereco")
            if hasattr(forn, "numero"):
                forn.numero = request.form.get("numero")
            if hasattr(forn, "bairro"):
                forn.bairro = request.form.get("bairro")
            if hasattr(forn, "cidade"):
                forn.cidade = request.form.get("cidade")
            if hasattr(forn, "estado"):
                forn.estado = request.form.get("estado") or request.form.get("uf")
            if hasattr(forn, "observacoes"):
                forn.observacoes = request.form.get("observacoes")
            if hasattr(forn, "contato"):
                forn.contato = request.form.get("contato")
            if hasattr(forn, "ativo"):
                forn.ativo = True

            db.session.add(forn)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("Erro fornecedor:", e)
        return redirect("/fornecedores")
    return redirect("/fornecedores")


@app.route("/fornecedores/excluir/<int:id>")
@login_required
def excluir_fornecedor(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    try:
        forn = Fornecedor.query.filter_by(id=id, empresa_id=eid).first_or_404()
        db.session.delete(forn)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro excluir fornecedor:", e)
    return redirect("/fornecedores")


@app.route("/compras")
@login_required
def compras():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")

    try:
        lista = Compra.query.filter_by(empresa_id=eid).order_by(Compra.id.desc()).all()
    except Exception:
        lista = []
    valor_compras = 0
    for c in lista:
        try:
            valor_compras += float(getattr(c, "valor_total", 0) or 0)
        except Exception:
            pass
        try:
            c.itens = ItemCompra.query.filter_by(compra_id=c.id).all()
        except Exception:
            c.itens = []
    try:
        fornecedores = Fornecedor.query.filter_by(empresa_id=eid).order_by(Fornecedor.razao_social).all()
    except Exception:
        fornecedores = []
    try:
        produtos = Produto.query.filter_by(empresa_id=eid).order_by(Produto.descricao).all()
    except Exception:
        produtos = []
    return render_template(
        "compras.html",
        compras=lista,
        valor_compras=valor_compras,
        total_compras=len(lista),
        fornecedores=fornecedores,
        produtos=produtos,
        hoje=date.today().isoformat(),
    )


@app.route("/compras/salvar", methods=["POST"])
@login_required
def salvar_compra():
    try:
        fornecedor_id = int(request.form.get("fornecedor_id") or 0)
        if not fornecedor_id:
            return redirect("/compras")

        data_str = request.form.get("data_compra") or ""
        try:
            y, m, d = map(int, data_str.split("-"))
            data_compra = date(y, m, d)
        except Exception:
            data_compra = date.today()

        numero_nf = (request.form.get("numero_nota") or "").strip() or None
        observacoes = request.form.get("observacoes")
        atualizar_estoque = True if request.form.get("atualizar_estoque") else False

        def to_float(v):
            if v is None:
                return 0.0
            s = str(v).strip().replace("R$", "").replace(" ", "")
            if "," in s and "." in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", ".")
            try:
                return float(s)
            except Exception:
                return 0.0

        produtos_ids = request.form.getlist("item_produto_id")
        qtds = request.form.getlist("item_qtd")
        custos = request.form.getlist("item_custo")

        mapa = {}
        for i in range(len(produtos_ids)):
            try:
                pid = int(produtos_ids[i] or 0)
            except Exception:
                continue
            qtd = to_float(qtds[i] if i < len(qtds) else 0)
            custo = to_float(custos[i] if i < len(custos) else 0)
            if pid <= 0 or qtd <= 0:
                continue
            if pid in mapa:
                mapa[pid]["qtd"] += qtd
                if custo > 0:
                    mapa[pid]["custo"] = custo
            else:
                mapa[pid] = {"produto_id": pid, "qtd": qtd, "custo": custo}

        itens = list(mapa.values())
        valor_total = sum(it["qtd"] * it["custo"] for it in itens)

        if not itens:
            return redirect("/compras")

        compra = Compra()
        if hasattr(compra, "empresa_id"):
            compra.empresa_id = empresa_atual() or 1
        if hasattr(compra, "fornecedor_id"):
            compra.fornecedor_id = fornecedor_id
        if hasattr(compra, "numero_nf"):
            compra.numero_nf = numero_nf
        if hasattr(compra, "data_emissao"):
            compra.data_emissao = data_compra
        if hasattr(compra, "data_entrada"):
            compra.data_entrada = data_compra
        if hasattr(compra, "valor_total"):
            compra.valor_total = valor_total
        if hasattr(compra, "observacoes"):
            compra.observacoes = observacoes
        if hasattr(compra, "status"):
            compra.status = "FINALIZADA"

        db.session.add(compra)
        db.session.flush()

        for it in itens:
            item = ItemCompra()
            if hasattr(item, "compra_id"):
                item.compra_id = compra.id
            if hasattr(item, "produto_id"):
                item.produto_id = it["produto_id"]
            if hasattr(item, "quantidade"):
                item.quantidade = it["qtd"]
            if hasattr(item, "valor_unitario"):
                item.valor_unitario = it["custo"]
            if hasattr(item, "valor_total"):
                item.valor_total = it["qtd"] * it["custo"]
            if hasattr(item, "custo_final"):
                item.custo_final = it["custo"]
            db.session.add(item)

            if atualizar_estoque:
                prod = db.session.get(Produto, it["produto_id"])
                if prod is not None:
                    atual = float(getattr(prod, "estoque_atual", 0) or 0)
                    prod.estoque_atual = atual + it["qtd"]
                    if hasattr(prod, "preco_compra") and it["custo"] > 0:
                        prod.preco_compra = it["custo"]

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro compra:", type(e).__name__, e)

    return redirect("/compras")


@app.route("/compras/ver/<int:id>")
@login_required
def ver_compra(id):
    compra = Compra.query.filter_by(id=id, empresa_id=eid).first_or_404()
    try:
        itens = ItemCompra.query.filter_by(compra_id=id).all()
    except Exception:
        itens = []
    return render_template("ver_compra.html", compra=compra, itens=itens)


@app.route("/compras/excluir/<int:id>")
@login_required
def excluir_compra(id):
    try:
        compra = Compra.query.filter_by(id=id, empresa_id=eid).first_or_404()
        try:
            ItemCompra.query.filter_by(compra_id=id).delete()
        except Exception:
            pass
        db.session.delete(compra)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro excluir compra:", e)
    return redirect("/compras")


@app.route("/inventario")
@login_required
def inventario():
    try:
        lista = Inventario.query.order_by(Inventario.id.desc()).all()
    except Exception:
        lista = []
    return render_template("inventario.html", inventarios=lista, total_inventarios=len(lista))


@app.route("/movimentacoes")
@login_required
def movimentacoes():
    try:
        lista = MovimentacaoEstoque.query.order_by(MovimentacaoEstoque.id.desc()).all()
    except Exception:
        lista = []
    return render_template("movimentacoes.html", movimentacoes=lista, total_movimentacoes=len(lista))


# ============================================================
# FINANCEIRO
# ============================================================
@app.route("/financeiro")
@login_required
def financeiro():
    periodo = request.args.get("periodo")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = OrdemServico.query
    hoje = date.today()

    if periodo == "hoje":
        query = query.filter(func.date(OrdemServico.data_abertura) == hoje)
    elif periodo == "semana":
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        query = query.filter(func.date(OrdemServico.data_abertura) >= inicio_semana)
    elif periodo == "mes":
        inicio_mes = hoje.replace(day=1)
        query = query.filter(func.date(OrdemServico.data_abertura) >= inicio_mes)
    elif periodo == "ano":
        inicio_ano = hoje.replace(month=1, day=1)
        query = query.filter(func.date(OrdemServico.data_abertura) >= inicio_ano)
    elif data_inicio:
        try:
            di = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            query = query.filter(func.date(OrdemServico.data_abertura) >= di)
            if data_fim:
                df = datetime.strptime(data_fim, "%Y-%m-%d").date()
                query = query.filter(func.date(OrdemServico.data_abertura) <= df)
        except:
            pass

    try:
        total_ordens = query.count()
        faturamento = query.with_entities(func.coalesce(func.sum(OrdemServico.valor_total), 0)).scalar() or 0
        abertas = query.filter(OrdemServico.status == "ABERTA").count()
        finalizadas = query.filter(OrdemServico.status == "FINALIZADA").count()
    except Exception:
        total_ordens = 0
        faturamento = 0
        abertas = 0
        finalizadas = 0

    return render_template(
        "financeiro.html",
        total_ordens=total_ordens,
        faturamento=faturamento,
        abertas=abertas,
        finalizadas=finalizadas,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim
    )


# ============================================================
# USUÁRIOS
# ============================================================
@app.route("/usuarios")
@login_required
def usuarios():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")

    lista = Usuario.query.filter_by(empresa_id=eid).order_by(Usuario.nome).all()
    return render_template("usuarios.html", usuarios=lista)


@app.route("/usuarios/novo", methods=["GET", "POST"])
@login_required
def novo_usuario():
    if request.method == "POST":
        try:
            login = request.form.get("login", "").strip()
            if Usuario.query.filter_by(login=login).first():
                return render_template("novo_usuario.html", erro="Login já existe")

            usuario = Usuario(
                empresa_id=session.get("empresa_id") or 1,
                nome=request.form.get("nome"),
                login=login,
                senha=generate_password_hash(request.form.get("senha") or "123456"),
                email=request.form.get("email"),
                perfil=request.form.get("perfil") or "CONSULTOR",
                ativo=True if request.form.get("ativo") == "on" else False
            )
            db.session.add(usuario)
            db.session.commit()
            return redirect("/usuarios")
        except Exception as e:
            db.session.rollback()
            print("Erro novo usuário:", e)
            return render_template("novo_usuario.html", erro=str(e))
    return render_template("novo_usuario.html")


@app.route("/usuarios/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_usuario(id):
    usuario = Usuario.query.filter_by(id=id, empresa_id=eid).first_or_404()
    if request.method == "POST":
        try:
            usuario.nome = request.form.get("nome")
            usuario.email = request.form.get("email")
            usuario.perfil = request.form.get("perfil") or "CONSULTOR"
            usuario.ativo = True if request.form.get("ativo") == "on" else False

            nova_senha = request.form.get("senha")
            if nova_senha:
                usuario.senha = generate_password_hash(nova_senha)

            db.session.commit()
            return redirect("/usuarios")
        except Exception as e:
            db.session.rollback()
            print("Erro editar usuário:", e)
    return render_template("novo_usuario.html", usuario=usuario)


@app.route("/usuarios/resetar-senha/<int:id>")
@login_required
def resetar_senha(id):
    usuario = Usuario.query.filter_by(id=id, empresa_id=eid).first_or_404()
    usuario.senha = generate_password_hash("123456")
    db.session.commit()
    return redirect("/usuarios")


@app.route("/usuarios/excluir/<int:id>")
@login_required
def excluir_usuario(id):
    if id == session.get("usuario_id"):
        return redirect("/usuarios")
    usuario = Usuario.query.filter_by(id=id, empresa_id=eid).first_or_404()
    db.session.delete(usuario)
    db.session.commit()
    return redirect("/usuarios")


# ============================================================
# CONFIGURAÇÕES
# ============================================================
@app.route("/configuracoes", methods=["GET", "POST"])
@login_required
def configuracoes():
    empresa = Empresa.query.first()
    usuario = Usuario.query.get(session.get("usuario_id"))
    mensagem = None
    erro = None

    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "empresa":
            try:
                if not empresa:
                    empresa = Empresa(cnpj=request.form.get("cnpj") or "00.000.000/0001-00")
                    db.session.add(empresa)

                empresa.razao_social = request.form.get("razao_social")
                empresa.nome_fantasia = request.form.get("nome_fantasia")
                empresa.cnpj = request.form.get("cnpj")
                empresa.inscricao_estadual = request.form.get("inscricao_estadual")
                empresa.telefone = request.form.get("telefone")
                empresa.whatsapp = request.form.get("whatsapp")
                empresa.email = request.form.get("email")
                empresa.site = request.form.get("site")
                empresa.cep = request.form.get("cep")
                empresa.endereco = request.form.get("endereco")
                empresa.numero = request.form.get("numero")
                empresa.complemento = request.form.get("complemento")
                empresa.bairro = request.form.get("bairro")
                empresa.cidade = request.form.get("cidade")
                empresa.estado = request.form.get("estado")
                empresa.url_nfse = request.form.get("url_nfse") or None

                db.session.commit()
                mensagem = "Dados da empresa salvos com sucesso!"
            except Exception as e:
                db.session.rollback()
                erro = f"Erro ao salvar empresa: {e}"

        elif acao == "senha":
            senha_atual = request.form.get("senha_atual")
            nova_senha = request.form.get("nova_senha")
            confirma = request.form.get("confirma_senha")

            if not check_password_hash(usuario.senha, senha_atual):
                erro = "Senha atual incorreta"
            elif nova_senha != confirma:
                erro = "Nova senha e confirmação não conferem"
            elif len(nova_senha) < 6:
                erro = "A nova senha deve ter no mínimo 6 caracteres"
            else:
                usuario.senha = generate_password_hash(nova_senha)
                db.session.commit()
                mensagem = "Senha alterada com sucesso!"

        elif acao == "nfse":
            try:
                if not empresa:
                    erro = "Empresa não encontrada"
                else:
                    empresa.nfse_provedor = request.form.get("nfse_provedor") or None
                    empresa.inscricao_municipal = request.form.get("inscricao_municipal") or None
                    empresa.codigo_servico = request.form.get("codigo_servico") or None
                    empresa.aliquota_iss = request.form.get("aliquota_iss") or 5.00
                    empresa.regime_tributario = request.form.get("regime_tributario") or "1"

                    senha = request.form.get("senha_certificado")
                    if senha:
                        empresa.senha_certificado = senha

                    if "certificado" in request.files:
                        arquivo = request.files["certificado"]
                        if arquivo and arquivo.filename:
                            import os
                            pasta = os.path.join("uploads", "certificados")
                            os.makedirs(pasta, exist_ok=True)
                            nome_arquivo = f"certificado_{empresa.id}.pfx"
                            caminho = os.path.join(pasta, nome_arquivo)
                            arquivo.save(caminho)
                            empresa.certificado_path = caminho

                    db.session.commit()
                    mensagem = "Configurações de NFS-e salvas com sucesso!"
            except Exception as e:
                db.session.rollback()
                erro = f"Erro ao salvar NFS-e: {str(e)}"

    return render_template(
        "configuracoes.html",
        empresa=empresa,
        usuario=usuario,
        mensagem=mensagem,
        erro=erro
    )


@app.route("/mecanicos")
@login_required
def mecanicos():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    lista = Mecanico.query.filter_by(empresa_id=eid).order_by(Mecanico.nome).all()
    return render_template("mecanicos.html", mecanicos=lista)


@app.route("/mecanicos/novo", methods=["GET", "POST"])
@login_required
def novo_mecanico():
    if request.method == "POST":
        try:
            m = Mecanico(
                empresa_id=empresa_atual() or 1,
                nome=request.form.get("nome"),
                telefone=request.form.get("telefone"),
                whatsapp=request.form.get("whatsapp"),
                tipo=request.form.get("tipo") or "FUNCIONARIO",
                ativo=True if request.form.get("ativo") == "on" else False,
                forma_pagamento=request.form.get("forma_pagamento") or "comissao",
                tipo_remuneracao=(request.form.get("tipo_remuneracao") or "COMISSAO").upper(),
                salario=float(request.form.get("salario") or 0),
                percentual_comissao=float(request.form.get("percentual_comissao") or 20),
                hora_entrada=int(request.form.get("hora_entrada") or 9),
                hora_saida=int(request.form.get("hora_saida") or 18),
                almoco_inicio=int(request.form.get("almoco_inicio") or 12),
                almoco_fim=int(request.form.get("almoco_fim") or 14),
                observacoes=request.form.get("observacoes"),
            )
            db.session.add(m)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("Erro mecânico:", e)
        return redirect("/mecanicos")
    return render_template("novo_mecanico.html", mecanico=None)


@app.route("/mecanicos/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_mecanico(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    mecanico = Mecanico.query.filter_by(id=id, empresa_id=eid).first_or_404()
    if request.method == "POST":
        try:
            mecanico.nome = request.form.get("nome")
            mecanico.telefone = request.form.get("telefone")
            mecanico.whatsapp = request.form.get("whatsapp")
            mecanico.tipo = request.form.get("tipo") or "FUNCIONARIO"
            mecanico.ativo = True if request.form.get("ativo") == "on" else False
            mecanico.forma_pagamento = request.form.get("forma_pagamento") or "comissao"
            mecanico.tipo_remuneracao = (request.form.get("tipo_remuneracao") or "COMISSAO").upper()
            mecanico.salario = float(request.form.get("salario") or 0)
            mecanico.percentual_comissao = float(request.form.get("percentual_comissao") or 20)
            mecanico.hora_entrada = int(request.form.get("hora_entrada") or 9)
            mecanico.hora_saida = int(request.form.get("hora_saida") or 18)
            mecanico.almoco_inicio = int(request.form.get("almoco_inicio") or 12)
            mecanico.almoco_fim = int(request.form.get("almoco_fim") or 14)
            mecanico.observacoes = request.form.get("observacoes")
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("Erro editar mecânico:", e)
        return redirect("/mecanicos")
    return render_template("novo_mecanico.html", mecanico=mecanico)


@app.route("/mecanicos/excluir/<int:id>")
@login_required
def excluir_mecanico(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    m = Mecanico.query.filter_by(id=id, empresa_id=eid).first_or_404()
    db.session.delete(m)
    db.session.commit()
    return redirect("/mecanicos")


@app.route("/api/agenda")
@login_required
def api_agenda():
    try:
        mecanico_id = int(request.args.get("mecanico_id") or 0)
    except Exception:
        return jsonify([])
    data_str = request.args.get("data")
    if data_str:
        try:
            y, m, d = map(int, data_str.split("-"))
            dia = date(y, m, d)
        except Exception:
            dia = date.today()
    else:
        dia = date.today()
    lista = Agendamento.query.filter_by(mecanico_id=mecanico_id, data=dia).order_by(Agendamento.hora_inicio).all()
    return jsonify([{
        "id": a.id,
        "hora_inicio": a.hora_inicio,
        "hora_fim": a.hora_fim,
        "duracao_min": a.duracao_real_min or a.duracao_estimada_min or 40,
        "descricao": a.descricao or "",
        "status": a.status,
        "ordem_servico_id": a.ordem_servico_id,
    } for a in lista])


@app.route("/api/agenda/criar", methods=["POST"])
@login_required
def api_agenda_criar():
    data = request.get_json(silent=True) or {}
    try:
        mecanico_id = int(data.get("mecanico_id"))
    except Exception:
        return jsonify({"erro": "Mecânico inválido"}), 400
    hora_inicio = data.get("hora_inicio") or "09:00"
    duracao = int(data.get("duracao_min") or 40)
    descricao = (data.get("descricao") or "").strip()
    if not descricao:
        return jsonify({"erro": "Informe a descrição"}), 400
    hoje = date.today()
    h, mi = map(int, hora_inicio.split(":"))
    ini = h * 60 + mi
    fim = ini + duracao
    for a in Agendamento.query.filter_by(mecanico_id=mecanico_id, data=hoje).all():
        try:
            ah, am = map(int, a.hora_inicio.split(":"))
            a_ini = ah * 60 + am
            a_dur = a.duracao_real_min or a.duracao_estimada_min or 40
            a_fim = a_ini + a_dur
            if ini < a_fim and fim > a_ini:
                return jsonify({"erro": f"Horário indisponível (conflito com {a.hora_inicio})"}), 409
        except Exception:
            pass
    h_fim = f"{fim // 60:02d}:{fim % 60:02d}"
    ag = Agendamento(
        mecanico_id=mecanico_id,
        data=hoje,
        hora_inicio=hora_inicio,
        duracao_estimada_min=duracao,
        duracao_real_min=duracao,
        hora_fim=h_fim,
        descricao=descricao,
        status="AGENDADO",
    )
    db.session.add(ag)
    db.session.commit()
    return jsonify({"ok": True, "id": ag.id})


@app.route("/api/agenda/atualizar/<int:id>", methods=["POST"])
@login_required
def api_agenda_atualizar(id):
    ag = Agendamento.query.filter_by(id=id, empresa_id=eid).first_or_404()
    data = request.get_json(silent=True) or {}
    if "duracao_min" in data:
        try:
            dur = int(data["duracao_min"])
            ag.duracao_real_min = dur
            h, mi = map(int, ag.hora_inicio.split(":"))
            fim = h * 60 + mi + dur
            ag.hora_fim = f"{fim // 60:02d}:{fim % 60:02d}"
        except Exception:
            pass
    if "hora_inicio" in data and data["hora_inicio"]:
        ag.hora_inicio = data["hora_inicio"]
        dur = ag.duracao_real_min or ag.duracao_estimada_min or 40
        try:
            h, mi = map(int, ag.hora_inicio.split(":"))
            fim = h * 60 + mi + dur
            ag.hora_fim = f"{fim // 60:02d}:{fim % 60:02d}"
        except Exception:
            pass
    if "descricao" in data:
        ag.descricao = data["descricao"]
    if "status" in data:
        ag.status = data["status"]
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/agenda/excluir/<int:id>", methods=["POST"])
@login_required
def api_agenda_excluir(id):
    ag = Agendamento.query.filter_by(id=id, empresa_id=eid).first_or_404()
    db.session.delete(ag)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/offline.html")
def offline_page():
    return render_template("offline.html")


@app.route("/api/offline/clientes")
def api_offline_clientes():
    eid = session.get("empresa_id")
    if not eid:
        return jsonify([])
    lista = Cliente.query.filter_by(empresa_id=eid).order_by(Cliente.nome).all()
    return jsonify([{
        "id": c.id, "nome": c.nome,
        "cpf_cnpj": getattr(c, "cpf_cnpj", None),
        "telefone": getattr(c, "telefone", None),
        "whatsapp": getattr(c, "whatsapp", None),
        "email": getattr(c, "email", None),
        "cidade": getattr(c, "cidade", None),
        "estado": getattr(c, "estado", None),
    } for c in lista])


@app.route("/api/offline/veiculos")
def api_offline_veiculos():
    eid = session.get("empresa_id")
    if not eid:
        return jsonify([])
    lista = Veiculo.query.filter_by(empresa_id=eid).order_by(Veiculo.placa).all()
    return jsonify([{
        "id": v.id, "cliente_id": v.cliente_id, "placa": v.placa,
        "marca": getattr(v, "marca", None), "modelo": getattr(v, "modelo", None),
        "cor": getattr(v, "cor", None), "km": getattr(v, "km", None),
    } for v in lista])


@app.route("/api/offline/produtos")
def api_offline_produtos():
    eid = session.get("empresa_id")
    if not eid:
        return jsonify([])
    try:
        lista = Produto.query.filter_by(empresa_id=eid).order_by(Produto.descricao).all()
        return jsonify([{
            "id": p.id,
            "codigo": getattr(p, "codigo", None),
            "descricao": getattr(p, "descricao", None),
            "estoque_atual": float(getattr(p, "estoque_atual", 0) or 0),
            "ativo": getattr(p, "ativo", True),
        } for p in lista])
    except Exception:
        return jsonify([])


@app.route("/api/offline/ordens")
def api_offline_ordens():
    eid = session.get("empresa_id")
    if not eid:
        return jsonify([])
    lista = OrdemServico.query.filter_by(empresa_id=eid).order_by(OrdemServico.data_abertura.desc()).all()
    return jsonify([{
        "id": o.id,
        "numero": o.numero,
        "cliente_id": o.cliente_id,
        "veiculo_id": o.veiculo_id,
        "status": o.status,
    } for o in lista])
# ============================================================
# API - BUSCA PRODUTO POR CÓDIGO DE BARRAS (BIPE)
# ============================================================
@app.route("/api/produto/codigo/<codigo>")
@login_required
def api_produto_por_codigo(codigo):
    eid = empresa_atual()
    if not eid:
        return jsonify({"erro": "Sem empresa"}), 401

    codigo = (codigo or "").strip()
    if not codigo:
        return jsonify({"erro": "Código vazio"}), 400

    produto = Produto.query.filter(
        Produto.empresa_id == eid,
        (Produto.codigo == codigo) | (Produto.codigo == codigo.lstrip("0"))
    ).first()

    if not produto and hasattr(Produto, "codigo_barras"):
        produto = Produto.query.filter(
            Produto.empresa_id == eid,
            (Produto.codigo_barras == codigo) | (Produto.codigo_barras == codigo.lstrip("0"))
        ).first()

    if not produto:
        return jsonify({"erro": "Produto não encontrado"}), 404

    return jsonify({
        "id": produto.id,
        "codigo": produto.codigo,
        "descricao": produto.descricao,
        "estoque_atual": float(getattr(produto, "estoque_atual", 0) or 0),
        "preco_venda": float(getattr(produto, "preco_venda", 0) or 0),
        "preco_compra": float(getattr(produto, "preco_compra", 0) or 0),
    })
@app.route("/api/produtos/buscar")
@login_required
def api_produtos_buscar():
    eid = empresa_atual()
    if not eid:
        return jsonify([])

    termo = (request.args.get("q") or "").strip()
    if len(termo) < 2:
        return jsonify([])

    produtos = Produto.query.filter(
        Produto.empresa_id == eid,
        (
            Produto.descricao.ilike(f"%{termo}%") |
            Produto.codigo.ilike(f"%{termo}%")
        )
    ).order_by(Produto.descricao).limit(30).all()

    return jsonify([{
        "id": p.id,
        "codigo": p.codigo,
        "descricao": p.descricao,
        "estoque_atual": float(getattr(p, "estoque_atual", 0) or 0),
        "preco_venda": float(getattr(p, "preco_venda", 0) or 0),
        "preco_compra": float(getattr(p, "preco_compra", 0) or 0),
    } for p in produtos])
@app.route("/estoque/entrada-rapida", methods=["GET", "POST"])
@login_required
def entrada_rapida():
    if request.method == "POST":
        try:
            produto_id = int(request.form.get("produto_id") or 0)
            quantidade = float(request.form.get("quantidade") or 0)
            custo = float(request.form.get("custo") or 0)

            if produto_id <= 0 or quantidade <= 0:
                return redirect("/estoque/entrada-rapida")

            produto = Produto.query.filter_by(id=produto_id, empresa_id=eid).first_or_404()
            atual = float(getattr(produto, "estoque_atual", 0) or 0)
            produto.estoque_atual = atual + quantidade

            if custo > 0 and hasattr(produto, "preco_compra"):
                produto.preco_compra = custo

            # Registra movimentação
            mov = MovimentacaoEstoque(
                produto_id=produto.id,
                tipo="ENTRADA",
                quantidade=quantidade,
                observacao="Entrada rápida por bipe"
            )
            db.session.add(mov)
            db.session.commit()

            return redirect("/estoque/entrada-rapida?sucesso=1")
        except Exception as e:
            db.session.rollback()
            print("Erro entrada rápida:", e)
            return redirect("/estoque/entrada-rapida")

    return render_template("entrada_rapida.html")
# ============================================================
# VENDA RÁPIDA DE PEÇAS
# ============================================================

@app.route("/venda-rapida", methods=["GET", "POST"])
@login_required
def venda_rapida():
    if request.method == "POST":
        try:
            cliente_id = request.form.get("cliente_id") or None
            if cliente_id:
                cliente_id = int(cliente_id)

            produtos_ids = request.form.getlist("produto_id[]")
            quantidades = request.form.getlist("quantidade[]")
            valores = request.form.getlist("valor_unitario[]")
            origens = request.form.getlist("origem[]")
            descricoes = request.form.getlist("descricao[]")

            if not produtos_ids:
                return redirect("/venda-rapida")

            venda = VendaRapida(
                empresa_id=session.get("empresa_id") or 1,
                cliente_id=cliente_id,
                usuario_id=session.get("usuario_id"),
                valor_total=0
            )
            db.session.add(venda)
            db.session.flush()

            total = 0.0

            for i in range(len(produtos_ids)):
                try:
                    pid = int(produtos_ids[i] or 0)
                    qtd = float(quantidades[i] or 0)
                    valor = float(valores[i] or 0)
                    origem = origens[i] if i < len(origens) else "ESTOQUE"
                    desc = descricoes[i] if i < len(descricoes) else ""

                    if qtd <= 0:
                        continue

                      # Busca o custo (sempre pega do formulário primeiro)
                    custo = 0.0
                    custos = request.form.getlist("custo_unitario[]")
                    if i < len(custos):
                        try:
                            custo = float(custos[i] or 0)
                        except:
                            custo = 0.0

                    # Se não veio do formulário e for estoque, pega do produto
                    if custo == 0 and origem == "ESTOQUE" and pid > 0:
                        produto_custo = Produto.query.get(pid)
                        if produto_custo:
                            custo = float(produto_custo.preco_compra or 0)

                    item = ItemVendaRapida(
                        venda_id=venda.id,
                        produto_id=pid if pid > 0 else None,
                        descricao=desc,
                        quantidade=qtd,
                        custo_unitario=custo,
                        valor_unitario=valor,
                        valor_total=qtd * valor,
                        origem=origem
                    )
                    db.session.add(item)
                    total += qtd * valor

                    # Baixa estoque somente se for ESTOQUE próprio
                    if origem == "ESTOQUE" and pid > 0:
                        produto = Produto.query.get(pid)
                        if produto:
                            atual = float(produto.estoque_atual or 0)
                            produto.estoque_atual = max(0, atual - qtd)

                            # Registra movimentação
                            mov = MovimentacaoEstoque(
                                empresa_id=session.get("empresa_id") or 1,
                                produto_id=pid,
                                tipo="SAIDA",
                                tipo_movimento="SAIDA",
                                origem="VENDA_RAPIDA",
                                quantidade=qtd,
                                saldo_anterior=atual,
                                saldo_atual=max(0, atual - qtd),
                                custo_unitario=float(produto.preco_compra or 0),
                                valor_total=qtd * float(produto.preco_compra or 0),
                                observacoes=f"Venda Rápida #{venda.id}"
                            )
                            db.session.add(mov)

                except Exception as e:
                    print("Erro item venda:", e)
                    continue

            venda.valor_total = total
            db.session.commit()
            return redirect("/venda-rapida?sucesso=1")

        except Exception as e:
            db.session.rollback()
            print("Erro venda rápida:", e)
            return redirect("/venda-rapida")

    # ===== GET =====
    eid = empresa_atual()
    if not eid:
        return redirect("/login")

    clientes = Cliente.query.filter_by(empresa_id=eid).order_by(Cliente.nome).all()
    return render_template("venda_rapida.html", clientes=clientes)


@app.route("/vendas-rapidas")
@login_required
def listar_vendas_rapidas():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")

    vendas = VendaRapida.query.filter_by(empresa_id=eid).order_by(VendaRapida.id.desc()).limit(100).all()
    return render_template("vendas_rapidas.html", vendas=vendas)


@app.route("/ordens/pdf/<int:id>")
@login_required
def ordem_pdf(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    ordem = OrdemServico.query.filter_by(id=id, empresa_id=eid).first_or_404()
    try:
        from pdf_ordem import gerar_pdf_ordem
        pdf = gerar_pdf_ordem(ordem)
        return send_file(
            pdf,
            as_attachment=False,
            download_name=f"OS_{ordem.numero or ordem.id}.pdf",
        )
    except Exception as e:
        print("Erro PDF ordem:", e)
        return f"<h1>OS #{ordem.numero or ordem.id}</h1><p>Total: R$ {ordem.valor_total or 0}</p>"


@app.route("/lembretes")
@login_required
def lembretes():
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    hoje = date.today()
    ano = hoje.year

    aniversariantes = []
    try:
        for c in Cliente.query.filter_by(empresa_id=eid).all():
            dn = getattr(c, "data_nascimento", None)
            if dn and dn.month == hoje.month and dn.day == hoje.day:
                envio = LembreteEnvio.query.filter_by(
                    tipo="ANIVERSARIO",
                    cliente_id=c.id,
                    ano=ano
                ).first()
                aniversariantes.append({
                    "id": c.id,
                    "nome": c.nome,
                    "whatsapp": getattr(c, "whatsapp", None),
                    "telefone": getattr(c, "telefone", None),
                    "enviado": envio is not None,
                })
    except Exception as e:
        print("Erro aniversariantes:", e)

    revisoes = []
    try:
        for v in Veiculo.query.filter_by(empresa_id=eid).all():
            data_rev = getattr(v, "proxima_revisao_data", None)
            km_rev = getattr(v, "proxima_revisao_km", None)
            km_atual = getattr(v, "km", None) or 0

            precisa = False
            motivo = ""
            if data_rev and data_rev <= hoje + timedelta(days=30):
                precisa = True
                motivo = f"Data: {data_rev.strftime('%d/%m/%Y')}"
            if km_rev and km_atual and (km_rev - km_atual) <= 1000:
                precisa = True
                motivo = (motivo + " | " if motivo else "") + f"KM: {km_rev}"

            if not precisa:
                continue

            # Se foi dispensado para esta data de revisão, não mostra
            dispensa = LembreteEnvio.query.filter_by(
                tipo="DISPENSA_REVISAO",
                veiculo_id=v.id,
                data_revisao_ref=data_rev
            ).first()
            if dispensa:
                continue

            cliente = None
            try:
                cliente = v.cliente
            except Exception:
                pass
            if not cliente and getattr(v, "cliente_id", None):
                cliente = Cliente.query.get(v.cliente_id)

            fone = None
            nome = "-"
            cliente_id = None
            if cliente:
                nome = cliente.nome or "-"
                fone = getattr(cliente, "whatsapp", None) or getattr(cliente, "telefone", None) or ""
                cliente_id = cliente.id

            atrasada = False
            if data_rev and data_rev < hoje:
                atrasada = True
            if km_rev and km_atual and km_atual >= km_rev:
                atrasada = True

            envios = LembreteEnvio.query.filter_by(
                tipo="REVISAO",
                veiculo_id=v.id,
                data_revisao_ref=data_rev
            ).all()
            qtd_envios = sum(e.quantidade or 1 for e in envios)

            revisoes.append({
                "veiculo_id": v.id,
                "placa": v.placa,
                "marca": getattr(v, "marca", "") or "",
                "modelo": getattr(v, "modelo", "") or "",
                "cliente_id": cliente_id,
                "cliente_nome": nome,
                "cliente_whatsapp": fone,
                "motivo": motivo,
                "atrasada": atrasada,
                "data_rev": data_rev,
                "qtd_envios": qtd_envios,
            })
    except Exception as e:
        print("Erro revisoes:", e)
        revisoes = []

    return render_template(
        "lembretes.html",
        aniversariantes=aniversariantes,
        revisoes=revisoes,
        hoje=hoje,
    )


@app.route("/lembretes/marcar-enviado", methods=["POST"])
@login_required
def lembretes_marcar_enviado():
    tipo = request.form.get("tipo")
    cliente_id = request.form.get("cliente_id")
    veiculo_id = request.form.get("veiculo_id")
    data_rev = request.form.get("data_rev") or None

    try:
        if tipo == "ANIVERSARIO" and cliente_id:
            ano = date.today().year
            existe = LembreteEnvio.query.filter_by(
                tipo="ANIVERSARIO",
                cliente_id=int(cliente_id),
                ano=ano
            ).first()
            if not existe:
                db.session.add(LembreteEnvio(
                    tipo="ANIVERSARIO",
                    cliente_id=int(cliente_id),
                    ano=ano,
                    quantidade=1
                ))
                db.session.commit()

        elif tipo == "REVISAO" and veiculo_id:
            data_ref = None
            if data_rev:
                try:
                    data_ref = datetime.strptime(data_rev, "%Y-%m-%d").date()
                except Exception:
                    pass
            envio = LembreteEnvio.query.filter_by(
                tipo="REVISAO",
                veiculo_id=int(veiculo_id),
                data_revisao_ref=data_ref
            ).first()
            if envio:
                envio.quantidade = (envio.quantidade or 1) + 1
                envio.enviado_em = datetime.utcnow()
            else:
                db.session.add(LembreteEnvio(
                    tipo="REVISAO",
                    veiculo_id=int(veiculo_id),
                    cliente_id=int(cliente_id) if cliente_id else None,
                    data_revisao_ref=data_ref,
                    quantidade=1
                ))
            db.session.commit()

        elif tipo == "DISPENSA_REVISAO" and veiculo_id:
            data_ref = None
            if data_rev:
                try:
                    data_ref = datetime.strptime(data_rev, "%Y-%m-%d").date()
                except Exception:
                    pass
            existe = LembreteEnvio.query.filter_by(
                tipo="DISPENSA_REVISAO",
                veiculo_id=int(veiculo_id),
                data_revisao_ref=data_ref
            ).first()
            if not existe:
                db.session.add(LembreteEnvio(
                    tipo="DISPENSA_REVISAO",
                    veiculo_id=int(veiculo_id),
                    data_revisao_ref=data_ref,
                    quantidade=1
                ))
                db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro marcar enviado:", e)

    return redirect("/lembretes")
@app.context_processor
def inject_lembretes_pendentes():
    try:
        eid = session.get("empresa_id")
        if not eid:
            return {"lembretes_pendentes": 0}
        hoje = date.today()
        ano = hoje.year
        pendentes = 0

        # Aniversários não enviados
        for c in Cliente.query.filter_by(empresa_id=eid).all():
            dn = getattr(c, "data_nascimento", None)
            if dn and dn.month == hoje.month and dn.day == hoje.day:
                envio = LembreteEnvio.query.filter_by(
                    tipo="ANIVERSARIO", cliente_id=c.id, ano=ano
                ).first()
                if not envio:
                    pendentes += 1

        # Revisões não dispensadas
        for v in Veiculo.query.filter_by(empresa_id=eid).all():
            data_rev = getattr(v, "proxima_revisao_data", None)
            km_rev = getattr(v, "proxima_revisao_km", None)
            km_atual = getattr(v, "km", None) or 0
            precisa = False
            if data_rev and data_rev <= hoje + timedelta(days=30):
                precisa = True
            if km_rev and km_atual and (km_rev - km_atual) <= 1000:
                precisa = True
            if not precisa:
                continue
            dispensa = LembreteEnvio.query.filter_by(
                tipo="DISPENSA_REVISAO",
                veiculo_id=v.id,
                data_revisao_ref=data_rev
            ).first()
            if not dispensa:
                pendentes += 1

        return {"lembretes_pendentes": pendentes}
    except Exception:
        return {"lembretes_pendentes": 0}
@app.route("/ordens/<int:id>/nfse")
@login_required
def ordem_nfse(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    ordem = OrdemServico.query.filter_by(id=id, empresa_id=eid).first_or_404()
    empresa = Empresa.query.filter_by(id=eid).first()
    return render_template("ordem_nfse.html", ordem=ordem, empresa=empresa)
@app.route("/vendas-rapidas/<int:id>/nfse")
@login_required
def venda_rapida_nfse(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    venda = VendaRapida.query.filter_by(id=id, empresa_id=eid).first_or_404()
    empresa = Empresa.query.filter_by(id=eid).first()
    return render_template("venda_rapida_nfse.html", venda=venda, empresa=empresa)
# ============================================================
# CHECKLIST DO VEÍCULO
# ============================================================

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    from flask import send_from_directory
    import os
    return send_from_directory(os.path.join(app.root_path, "uploads"), filename)


@app.route("/ordens/<int:id>/checklist", methods=["GET", "POST"])
@login_required
def checklist_veiculo(id):
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    ordem = OrdemServico.query.filter_by(id=id, empresa_id=eid).first_or_404()
    checklist = ChecklistVeiculo.query.filter_by(ordem_servico_id=id).first()

    if request.method == "POST":
        try:
            if not checklist:
                checklist = ChecklistVeiculo(ordem_servico_id=id)
                db.session.add(checklist)

            itens = [
                "farois", "lanternas", "setas", "pneus", "lataria",
                "para_choques", "vidros", "retrovisores", "interior",
                "bancos", "painel", "tapetes", "estepe", "macaco",
                "triangulo", "documentos", "chave_reserva"
            ]
            for item in itens:
                setattr(checklist, item, request.form.get(item) or "OK")

            checklist.observacoes = request.form.get("observacoes")
            checklist.assinatura = request.form.get("assinatura") or checklist.assinatura

            fotos_salvas = []
            if checklist.fotos:
                fotos_salvas = checklist.fotos.split(",")

            if "fotos" in request.files:
                arquivos = request.files.getlist("fotos")
                import os
                pasta = os.path.join("uploads", "checklist", str(id))
                os.makedirs(pasta, exist_ok=True)

                for arquivo in arquivos:
                    if arquivo and arquivo.filename:
                        nome = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{arquivo.filename}"
                        caminho = os.path.join(pasta, nome)
                        arquivo.save(caminho)
                        fotos_salvas.append(caminho)

            checklist.fotos = ",".join(fotos_salvas) if fotos_salvas else None

            db.session.commit()
            return redirect(f"/ordens/{id}/checklist?sucesso=1")
        except Exception as e:
            db.session.rollback()
            print("Erro checklist:", e)

    return render_template(
        "checklist_veiculo.html",
        ordem=ordem,
        checklist=checklist
    )


@app.route("/ordens/<int:id>/checklist/pdf")
@login_required
def checklist_pdf(id):
    from flask import make_response
    eid = empresa_atual()
    if not eid:
        return redirect("/login")
    ordem = OrdemServico.query.filter_by(id=id, empresa_id=eid).first_or_404()
    checklist = ChecklistVeiculo.query.filter_by(ordem_servico_id=id).first()
    empresa = Empresa.query.filter_by(id=eid).first()

    if not checklist:
        return "Checklist ainda não foi preenchido", 404

    fotos_html = ""
    if checklist.fotos:
        labels = ["Frente", "Traseira", "Lateral Esquerda", "Lateral Direita", "Painel / Interior"]
        fotos = [f.strip() for f in checklist.fotos.split(",") if f.strip()]
        fotos_html += '<div style="display:flex; flex-wrap:wrap; gap:15px; margin-top:10px;">'
        for i, foto in enumerate(fotos):
            label = labels[i] if i < len(labels) else f"Foto {i+1}"
            fotos_html += f'''
                <div style="text-align:center;">
                    <div style="font-size:12px; font-weight:bold; margin-bottom:4px;">{label}</div>
                    <img src="/{foto}" style="width:180px; height:130px; object-fit:cover; border:1px solid #999;">
                </div>
            '''
        fotos_html += '</div>'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Checklist de Entrada - OS {ordem.numero}</title>
        <style>
            body {{ font-family: Arial, sans-serif; font-size: 13px; margin: 30px; color: #222; }}
            h1 {{ font-size: 20px; margin-bottom: 5px; color: #111; }}
            .header {{ border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #444; padding: 7px 10px; text-align: left; }}
            th {{ background: #f0f0f0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Checklist de Entrada do Veículo</h1>
            <div><strong>{empresa.nome_fantasia if empresa else 'HL Car Auto Center'}</strong></div>
        </div>
        <p><strong>OS nº:</strong> {ordem.numero}<br>
        <strong>Cliente:</strong> {ordem.cliente.nome if ordem.cliente else '-'}<br>
        <strong>Veículo:</strong> {ordem.veiculo.placa if ordem.veiculo else '-'}</p>
        <table>
            <tr><th>Item</th><th>Estado</th></tr>
    """

    itens = [
        ("Faróis", checklist.farois),
        ("Lanternas", checklist.lanternas),
        ("Setas", checklist.setas),
        ("Pneus", checklist.pneus),
        ("Lataria", checklist.lataria),
        ("Para-choques", checklist.para_choques),
        ("Vidros", checklist.vidros),
        ("Retrovisores", checklist.retrovisores),
        ("Interior", checklist.interior),
        ("Bancos", checklist.bancos),
        ("Painel", checklist.painel),
        ("Tapetes", checklist.tapetes),
        ("Estepe", checklist.estepe),
        ("Macaco", checklist.macaco),
        ("Triângulo", checklist.triangulo),
        ("Documentos", checklist.documentos),
        ("Chave Reserva", checklist.chave_reserva),
    ]
    for nome, valor in itens:
        html += f"<tr><td>{nome}</td><td><strong>{valor or 'OK'}</strong></td></tr>"

    html += f"""
        </table>
        <p><strong>Observações:</strong><br>{checklist.observacoes or 'Nenhuma'}</p>
        {fotos_html}
    </body>
    </html>
    """

    try:
        from weasyprint import HTML
        pdf = HTML(string=html, base_url=request.host_url).write_pdf()
        response = make_response(pdf)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f"inline; filename=checklist_os_{ordem.numero}.pdf"
        return response
    except Exception:
        return html


# ============================================================
# EMPRESAS (Multi-empresa)
# ============================================================

@app.route("/empresas")
@login_required
def listar_empresas():
    # Só ADMIN pode ver
    if session.get("usuario_perfil") != "ADMIN":
        return redirect("/")

    empresas = Empresa.query.order_by(Empresa.nome_fantasia).all()
    return render_template("empresas.html", empresas=empresas)


@app.route("/empresas/nova", methods=["GET", "POST"])
@login_required
def nova_empresa():
    if session.get("usuario_perfil") != "ADMIN":
        return redirect("/")

    if request.method == "POST":
        try:
            # Cria a empresa
            empresa = Empresa(
                razao_social=request.form.get("razao_social"),
                nome_fantasia=request.form.get("nome_fantasia"),
                cnpj=request.form.get("cnpj"),
                telefone=request.form.get("telefone"),
                whatsapp=request.form.get("whatsapp"),
                email=request.form.get("email"),
                cidade=request.form.get("cidade"),
                estado=request.form.get("estado"),
                ativo=True
            )
            db.session.add(empresa)
            db.session.flush()  # pega o ID da empresa

            # Cria o primeiro usuário ADMIN da nova empresa
            login = request.form.get("login_admin")
            senha = request.form.get("senha_admin")

            usuario = Usuario(
                empresa_id=empresa.id,
                nome=request.form.get("nome_admin"),
                login=login,
                senha=generate_password_hash(senha),
                perfil="ADMIN",
                ativo=True
            )
            db.session.add(usuario)
            db.session.commit()

            return redirect("/empresas?sucesso=1")
        except Exception as e:
            db.session.rollback()
            print("Erro ao criar empresa:", e)
            return render_template("nova_empresa.html", erro="Erro ao salvar. Verifique se o login já existe.")

    return render_template("nova_empresa.html")
@app.route("/empresas/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_empresa(id):
    if session.get("usuario_perfil") != "ADMIN":
        return redirect("/")

    empresa = Empresa.query.get_or_404(id)

    if request.method == "POST":
        try:
            empresa.razao_social = request.form.get("razao_social")
            empresa.nome_fantasia = request.form.get("nome_fantasia")
            empresa.cnpj = request.form.get("cnpj")
            empresa.telefone = request.form.get("telefone")
            empresa.whatsapp = request.form.get("whatsapp")
            empresa.email = request.form.get("email")
            empresa.cidade = request.form.get("cidade")
            empresa.estado = request.form.get("estado")
            empresa.plano = request.form.get("plano") or "BASICO"
            empresa.status_pagamento = request.form.get("status_pagamento") or "ATIVO"
            empresa.ativo = True if request.form.get("ativo") == "on" else False
            empresa.observacoes_internas = request.form.get("observacoes_internas")

            data_venc = request.form.get("data_vencimento")
            if data_venc:
                empresa.data_vencimento = datetime.strptime(data_venc, "%Y-%m-%d").date()
            else:
                empresa.data_vencimento = None

            db.session.commit()
            return redirect("/empresas?sucesso=1")
        except Exception as e:
            db.session.rollback()
            print("Erro ao editar empresa:", e)

    return render_template("editar_empresa.html", empresa=empresa)
if __name__ == "__main__":
    app.run(debug=True)