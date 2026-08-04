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
)

from pdf_ordem_old import gerar_pdf_ordem


app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "hlcar-erp-secret-key-2026-change-me"

db.init_app(app)


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
@login_required
def dashboard():
    periodo = request.args.get("periodo")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query_os = OrdemServico.query
    hoje = date.today()

    if periodo == "hoje":
        query_os = query_os.filter(func.date(OrdemServico.data_abertura) == hoje)
    elif periodo == "semana":
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        query_os = query_os.filter(func.date(OrdemServico.data_abertura) >= inicio_semana)
    elif periodo == "mes":
        inicio_mes = hoje.replace(day=1)
        query_os = query_os.filter(func.date(OrdemServico.data_abertura) >= inicio_mes)
    elif periodo == "ano":
        inicio_ano = hoje.replace(month=1, day=1)
        query_os = query_os.filter(func.date(OrdemServico.data_abertura) >= inicio_ano)
    elif data_inicio:
        try:
            di = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            query_os = query_os.filter(func.date(OrdemServico.data_abertura) >= di)
            if data_fim:
                df = datetime.strptime(data_fim, "%Y-%m-%d").date()
                query_os = query_os.filter(func.date(OrdemServico.data_abertura) <= df)
        except Exception:
            pass

    total_clientes = Cliente.query.count()
    total_veiculos = Veiculo.query.count()
    total_ordens = query_os.count()
    faturamento = query_os.with_entities(func.coalesce(func.sum(OrdemServico.valor_total), 0)).scalar() or 0

    # Ordens em andamento (ABERTA)
    ordens_andamento = query_os.filter(OrdemServico.status == "ABERTA").count()

    # Contas a receber = valor das OS abertas
    contas_receber = query_os.filter(OrdemServico.status == "ABERTA").with_entities(
        func.coalesce(func.sum(OrdemServico.valor_total), 0)
    ).scalar() or 0

    # Últimas 8 OS
    ultimas_ordens = OrdemServico.query.order_by(OrdemServico.id.desc()).limit(8).all()

    # Veículos em atendimento (OS abertas)
    veiculos_atendimento = (
        db.session.query(OrdemServico, Veiculo, Cliente)
        .join(Veiculo, OrdemServico.veiculo_id == Veiculo.id)
        .join(Cliente, OrdemServico.cliente_id == Cliente.id)
        .filter(OrdemServico.status == "ABERTA")
        .order_by(OrdemServico.id.desc())
        .limit(8)
        .all()
    )

    # Produtos com estoque baixo
    try:
        produtos_baixo = []
        for p in Produto.query.order_by(Produto.descricao).all():
            estoque = float(getattr(p, "estoque_atual", 0) or 0)
            minimo = float(getattr(p, "estoque_minimo", 0) or 0)
            if minimo > 0 and estoque <= minimo:
                produtos_baixo.append(p)
            elif minimo <= 0 and estoque <= 2:
                produtos_baixo.append(p)
        produtos_baixo = produtos_baixo[:8]
    except Exception:
        produtos_baixo = []

    # Dados do gráfico — últimos 7 dias
    labels_grafico = []
    valores_grafico = []
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        labels_grafico.append(dia.strftime("%d/%m"))
        fat_dia = (
            OrdemServico.query
            .filter(func.date(OrdemServico.data_abertura) == dia)
            .with_entities(func.coalesce(func.sum(OrdemServico.valor_total), 0))
            .scalar()
            or 0
        )
        valores_grafico.append(float(fat_dia))

    try:
        mecanicos = Mecanico.query.filter_by(ativo=True).order_by(Mecanico.nome).all()
    except Exception:
        mecanicos = []

    # ========== NOVAS INFORMAÇÕES DO DASHBOARD ==========

    # 1. Vendas Rápidas
    try:
        inicio_mes = hoje.replace(day=1)
        vendas_rapidas_mes = (
            VendaRapida.query
            .filter(func.date(VendaRapida.criado_em) >= inicio_mes)
            .with_entities(func.coalesce(func.sum(VendaRapida.valor_total), 0))
            .scalar() or 0
        )
        vendas_rapidas_hoje = (
            VendaRapida.query
            .filter(func.date(VendaRapida.criado_em) == hoje)
            .with_entities(func.coalesce(func.sum(VendaRapida.valor_total), 0))
            .scalar() or 0
        )
    except Exception:
        vendas_rapidas_mes = 0
        vendas_rapidas_hoje = 0

    # 2. Ticket médio
    try:
        qtd_os = query_os.count() or 1
        ticket_medio = float(faturamento or 0) / qtd_os
    except Exception:
        ticket_medio = 0

    # 3. OS abertas há mais de 7 dias
    try:
        limite = hoje - timedelta(days=7)
        os_antigas = (
            OrdemServico.query
            .filter(OrdemServico.status == "ABERTA")
            .filter(func.date(OrdemServico.data_abertura) <= limite)
            .count()
        )
    except Exception:
        os_antigas = 0

    # 4. Próximas revisões
    try:
        revisoes = []
        for v in Veiculo.query.order_by(Veiculo.proxima_revisao_data).all():
            data_rev = getattr(v, "proxima_revisao_data", None)
            km_rev = getattr(v, "proxima_revisao_km", None)
            km_atual = getattr(v, "km", None) or 0

            precisa = False
            if data_rev and data_rev <= hoje + timedelta(days=30):
                precisa = True
            if km_rev and km_atual and (km_rev - km_atual) <= 1000:
                precisa = True

            if precisa:
                cliente_nome = v.cliente.nome if getattr(v, "cliente", None) else "-"
                revisoes.append({
                    "placa": v.placa,
                    "cliente": cliente_nome,
                    "data": data_rev.strftime("%d/%m/%Y") if data_rev else "-",
                    "km": km_rev or "-"
                })
        revisoes = revisoes[:6]
    except Exception:
        revisoes = []

    return render_template(
        "dashboard.html",
        total_clientes=total_clientes,
        total_veiculos=total_veiculos,
        total_os=total_ordens,
        faturamento=faturamento,
        mecanicos=mecanicos,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        ordens_andamento=ordens_andamento,
        contas_receber=contas_receber,
        ultimas_ordens=ultimas_ordens,
        veiculos_atendimento=veiculos_atendimento,
        produtos_baixo=produtos_baixo,
        labels_grafico=labels_grafico,
        valores_grafico=valores_grafico,
                vendas_rapidas_mes=vendas_rapidas_mes,
        vendas_rapidas_hoje=vendas_rapidas_hoje,
        ticket_medio=ticket_medio,
        os_antigas=os_antigas,
        revisoes=revisoes,
    )


@app.route("/clientes")
@login_required
def clientes():
    lista_clientes = Cliente.query.order_by(Cliente.nome).all()
    return render_template("clientes.html", clientes=lista_clientes)


@app.route("/clientes/novo", methods=["GET", "POST"])
@login_required
def novo_cliente():
    if request.method == "POST":
        cpf = (request.form.get("cpf_cnpj") or "").strip()
        if cpf:
            existente = Cliente.query.filter(Cliente.cpf_cnpj == cpf).first()
            if existente:
                return redirect(f"/clientes/editar/{existente.id}?aviso=cpf_existente")

        data_nasc = request.form.get("data_nascimento")
        cliente = Cliente(
            empresa_id=session.get("empresa_id") or 1,
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
    cliente = Cliente.query.get_or_404(id)
    if request.method == "POST":
        data_nasc = request.form.get("data_nascimento")
        cliente.nome = request.form.get("nome")
        cliente.cpf_cnpj = request.form.get("cpf_cnpj")
        cliente.telefone = request.form.get("telefone")
        cliente.whatsapp = request.form.get("whatsapp")
        cliente.email = request.form.get("email")
        cliente.endereco = request.form.get("endereco")
        cliente.cidade = request.form.get("cidade")
        cliente.estado = request.form.get("estado")
        cliente.observacoes = request.form.get("observacoes")
        cliente.data_nascimento = datetime.strptime(data_nasc, "%Y-%m-%d").date() if data_nasc else None
        db.session.commit()
        return redirect("/clientes")
    return render_template("novo_cliente.html", cliente=cliente, aviso=request.args.get("aviso"))


@app.route("/clientes/excluir/<int:id>")
@login_required
def excluir_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    return redirect("/clientes")
@app.route("/veiculos")
@login_required
def veiculos():
    lista_veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    return render_template("veiculos.html", veiculos=lista_veiculos)


@app.route("/veiculos/novo", methods=["GET", "POST"])
@login_required
def novo_veiculo():
    if request.method == "POST":
        placa = request.form["placa"].upper().strip()

        existente = Veiculo.query.filter(Veiculo.placa == placa).first()
        if existente:
            return redirect(f"/veiculos/editar/{existente.id}?aviso=placa_existente")

        data_rev = request.form.get("proxima_revisao_data")
        km_rev = request.form.get("proxima_revisao_km")

        veiculo = Veiculo(
            empresa_id=session.get("empresa_id") or 1,
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
    clientes = Cliente.query.order_by(Cliente.nome).all()
    return render_template("novo_veiculo.html", clientes=clientes)


@app.route("/veiculos/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
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

    clientes = Cliente.query.order_by(Cliente.nome).all()
    return render_template(
        "novo_veiculo.html",
        veiculo=veiculo,
        clientes=clientes,
        aviso=aviso
    )


@app.route("/veiculos/excluir/<int:id>")
@login_required
def excluir_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    db.session.delete(veiculo)
    db.session.commit()
    return redirect("/veiculos")


# ============================================================
# ORDENS COM FILTRO DE DATA + STATUS
# ============================================================
@app.route("/ordens")
@login_required
def ordens():
    periodo = request.args.get("periodo")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    status = request.args.get("status")

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
                nomes.append(m.nome)
                total_servicos += val
                detalhes.append({
                    "mecanico": m,
                    "duracao": dur,
                    "valor": val,
                    "servico": serv,
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
            perc = float(m.percentual_comissao or 20)
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

                item = ItemOrdemServico(
                    ordem_servico_id=ordem.id,
                    produto_id=pid if pid > 0 else None,
                    origem=tipo if tipo in ("ESTOQUE", "PARCEIRO") else "ESTOQUE",
                    tipo_item="PRODUTO",
                    descricao=desc,
                    quantidade=qtd,
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

    clientes = Cliente.query.order_by(Cliente.nome).all()
    veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    try:
        lista_mecanicos = Mecanico.query.filter_by(ativo=True).order_by(Mecanico.nome).all()
    except Exception:
        lista_mecanicos = []
    try:
        lista_produtos = Produto.query.order_by(Produto.descricao).all()
    except Exception:
        lista_produtos = []
    try:
        lista_fornecedores = Fornecedor.query.order_by(Fornecedor.razao_social).all()
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
    ordem = OrdemServico.query.get_or_404(id)
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
                nomes.append(m.nome)
                total_servicos += val
                detalhes.append({
                    "mecanico": m,
                    "duracao": dur,
                    "valor": val,
                    "servico": serv,
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
            perc = float(m.percentual_comissao or 20)
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

                db.session.add(ItemOrdemServico(
                    ordem_servico_id=ordem.id,
                    produto_id=pid if pid > 0 else None,
                    origem=tipo if tipo in ("ESTOQUE", "PARCEIRO") else "ESTOQUE",
                    tipo_item="PRODUTO",
                    descricao=desc,
                    quantidade=qtd,
                    valor_unitario=vu,
                    valor_total=qtd * vu,
                ))
            except Exception as e:
                print("Erro item OS (edit):", e)

        db.session.commit()
        return redirect("/ordens")

    clientes = Cliente.query.order_by(Cliente.nome).all()
    veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    try:
        mecanicos = Mecanico.query.filter_by(ativo=True).order_by(Mecanico.nome).all()
    except Exception:
        mecanicos = []
    try:
        produtos = Produto.query.order_by(Produto.descricao).all()
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
    ordem = OrdemServico.query.get_or_404(id)
    ordem.status = "FINALIZADA"
    db.session.commit()
    return redirect("/ordens")


@app.route("/ordens/excluir/<int:id>")
@login_required
def excluir_ordem(id):
    ordem = OrdemServico.query.get_or_404(id)

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
    ordem = OrdemServico.query.get_or_404(id)
    pdf = gerar_pdf_ordem(ordem)
    return send_file(pdf, download_name=f"OS_{ordem.numero}.pdf", as_attachment=False, mimetype="application/pdf")


@app.route("/api/veiculos/<int:cliente_id>")
@login_required
def api_veiculos(cliente_id):
    lista = Veiculo.query.filter_by(cliente_id=cliente_id).order_by(Veiculo.placa).all()
    return jsonify([
        {"id": v.id, "placa": v.placa, "marca": getattr(v, "marca", None), "modelo": getattr(v, "modelo", None), "km": getattr(v, "km", None)}
        for v in lista
    ])


@app.route("/dashboard/dados")
@login_required
def dashboard_dados():
    total_clientes = Cliente.query.count()
    total_veiculos = Veiculo.query.count()
    total_ordens = OrdemServico.query.count()
    faturamento = db.session.query(db.func.sum(OrdemServico.valor_total)).scalar() or 0
    return jsonify({"clientes": total_clientes, "veiculos": total_veiculos, "ordens": total_ordens, "faturamento": faturamento})


@app.route("/estoque")
@login_required
def estoque():
    try:
        lista_produtos = Produto.query.order_by(Produto.descricao).all()
    except Exception:
        lista_produtos = []
    try:
        categorias = Categoria.query.order_by(Categoria.nome).all()
    except Exception:
        categorias = []
    try:
        fabricantes = Fabricante.query.order_by(Fabricante.nome).all()
    except Exception:
        fabricantes = []
    try:
        fornecedores = Fornecedor.query.order_by(Fornecedor.razao_social).all()
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
            produto.empresa_id = 1
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
                categorias = Categoria.query.order_by(Categoria.nome).all()
            except Exception:
                categorias = []
            try:
                fabricantes = Fabricante.query.order_by(Fabricante.nome).all()
            except Exception:
                fabricantes = []
            return render_template("novo_produto.html", categorias=categorias, fabricantes=fabricantes, erro=str(e))
    try:
        categorias = Categoria.query.order_by(Categoria.nome).all()
    except Exception:
        categorias = []
    try:
        fabricantes = Fabricante.query.order_by(Fabricante.nome).all()
    except Exception:
        fabricantes = []
    return render_template("novo_produto.html", categorias=categorias, fabricantes=fabricantes)


@app.route("/produtos/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_produto(id):
    produto = Produto.query.get_or_404(id)
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
        categorias = Categoria.query.order_by(Categoria.nome).all()
    except Exception:
        categorias = []
    try:
        fabricantes = Fabricante.query.order_by(Fabricante.nome).all()
    except Exception:
        fabricantes = []
    return render_template("editar_produto.html", produto=produto, categorias=categorias, fabricantes=fabricantes)


@app.route("/produtos/excluir/<int:id>")
@login_required
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)
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
    try:
        lista = Categoria.query.order_by(Categoria.nome).all()
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
    try:
        cat = Categoria.query.get_or_404(id)
        db.session.delete(cat)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro excluir categoria:", e)
    return redirect("/categorias")


@app.route("/fabricantes")
@login_required
def fabricantes():
    try:
        lista = Fabricante.query.order_by(Fabricante.nome).all()
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
        fab = Fabricante.query.get_or_404(id)
        db.session.delete(fab)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro excluir fabricante:", e)
    return redirect("/fabricantes")


@app.route("/fornecedores")
@login_required
def fornecedores():
    try:
        lista = Fornecedor.query.order_by(Fornecedor.razao_social).all()
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
                forn.empresa_id = 1
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
    try:
        forn = Fornecedor.query.get_or_404(id)
        db.session.delete(forn)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Erro excluir fornecedor:", e)
    return redirect("/fornecedores")


@app.route("/compras")
@login_required
def compras():
    try:
        lista = Compra.query.order_by(Compra.id.desc()).all()
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
        fornecedores = Fornecedor.query.order_by(Fornecedor.razao_social).all()
    except Exception:
        fornecedores = []
    try:
        produtos = Produto.query.order_by(Produto.descricao).all()
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
            compra.empresa_id = 1
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
    compra = Compra.query.get_or_404(id)
    try:
        itens = ItemCompra.query.filter_by(compra_id=id).all()
    except Exception:
        itens = []
    return render_template("ver_compra.html", compra=compra, itens=itens)


@app.route("/compras/excluir/<int:id>")
@login_required
def excluir_compra(id):
    try:
        compra = Compra.query.get_or_404(id)
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
    lista = Usuario.query.order_by(Usuario.nome).all()
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
    usuario = Usuario.query.get_or_404(id)
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
    usuario = Usuario.query.get_or_404(id)
    usuario.senha = generate_password_hash("123456")
    db.session.commit()
    return redirect("/usuarios")


@app.route("/usuarios/excluir/<int:id>")
@login_required
def excluir_usuario(id):
    if id == session.get("usuario_id"):
        return redirect("/usuarios")
    usuario = Usuario.query.get_or_404(id)
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
    try:
        lista = Mecanico.query.order_by(Mecanico.nome).all()
    except Exception:
        lista = []
    return render_template("mecanicos.html", mecanicos=lista)


@app.route("/mecanicos/novo", methods=["GET", "POST"])
@login_required
def novo_mecanico():
    if request.method == "POST":
        try:
            m = Mecanico(
                nome=request.form.get("nome"),
                telefone=request.form.get("telefone"),
                whatsapp=request.form.get("whatsapp"),
                ativo=True if request.form.get("ativo") == "on" else False,
                forma_pagamento=request.form.get("forma_pagamento") or "comissao",
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
    mecanico = Mecanico.query.get_or_404(id)
    if request.method == "POST":
        try:
            mecanico.nome = request.form.get("nome")
            mecanico.telefone = request.form.get("telefone")
            mecanico.whatsapp = request.form.get("whatsapp")
            mecanico.ativo = True if request.form.get("ativo") == "on" else False
            mecanico.forma_pagamento = request.form.get("forma_pagamento") or "comissao"
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
    m = Mecanico.query.get_or_404(id)
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
    ag = Agendamento.query.get_or_404(id)
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
    ag = Agendamento.query.get_or_404(id)
    db.session.delete(ag)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/offline.html")
def offline_page():
    return render_template("offline.html")


@app.route("/api/offline/clientes")
def api_offline_clientes():
    lista = Cliente.query.order_by(Cliente.nome).all()
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
    lista = Veiculo.query.order_by(Veiculo.placa).all()
    return jsonify([{
        "id": v.id, "cliente_id": v.cliente_id, "placa": v.placa,
        "marca": getattr(v, "marca", None), "modelo": getattr(v, "modelo", None),
        "cor": getattr(v, "cor", None), "km": getattr(v, "km", None),
    } for v in lista])


@app.route("/api/offline/produtos")
def api_offline_produtos():
    try:
        lista = Produto.query.order_by(Produto.descricao).all()
        return jsonify([{
            "id": p.id,
            "codigo": getattr(p, "codigo", None),
            "descricao": getattr(p, "descricao", None),
            "estoque_atual": float(getattr(p, "estoque_atual", 0) or 0),
            "preco_venda": float(getattr(p, "preco_venda", 0) or 0),
            "ativo": getattr(p, "ativo", True),
        } for p in lista])
    except Exception:
        return jsonify([])


@app.route("/api/offline/ordens")
def api_offline_ordens():
    lista = OrdemServico.query.order_by(OrdemServico.data_abertura.desc()).limit(200).all()
    return jsonify([{
        "id": o.id,
        "numero": o.numero,
        "cliente_id": o.cliente_id,
        "veiculo_id": o.veiculo_id,
        "status": o.status,
        "km": getattr(o, "km", None),
        "defeito_relatado": getattr(o, "defeito_relatado", None),
        "valor_total": float(getattr(o, "valor_total", 0) or 0),
        "data_abertura": o.data_abertura.isoformat() if o.data_abertura else None,
    } for o in lista])
# ============================================================
# API - BUSCA PRODUTO POR CÓDIGO DE BARRAS (BIPE)
# ============================================================
@app.route("/api/produto/codigo/<codigo>")
@login_required
def api_produto_por_codigo(codigo):
    codigo = (codigo or "").strip()
    if not codigo:
        return jsonify({"erro": "Código vazio"}), 400

    # Procura no campo codigo
    produto = Produto.query.filter(
        (Produto.codigo == codigo) | 
        (Produto.codigo == codigo.lstrip("0"))
    ).first()

    # Se não achou e existir o campo codigo_barras, procura nele também
    if not produto and hasattr(Produto, "codigo_barras"):
        produto = Produto.query.filter(
            (Produto.codigo_barras == codigo) | 
            (Produto.codigo_barras == codigo.lstrip("0"))
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
    termo = (request.args.get("q") or "").strip()
    if len(termo) < 2:
        return jsonify([])

    produtos = Produto.query.filter(
        (Produto.descricao.ilike(f"%{termo}%")) |
        (Produto.codigo.ilike(f"%{termo}%")) |
        (Produto.codigo_barras.ilike(f"%{termo}%"))
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

            produto = Produto.query.get_or_404(produto_id)
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

                    item = ItemVendaRapida(
                        venda_id=venda.id,
                        produto_id=pid if pid > 0 else None,
                        descricao=desc,
                        quantidade=qtd,
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

    clientes = Cliente.query.order_by(Cliente.nome).all()
    return render_template("venda_rapida.html", clientes=clientes)


@app.route("/vendas-rapidas")
@login_required
def listar_vendas_rapidas():
    vendas = VendaRapida.query.order_by(VendaRapida.id.desc()).limit(100).all()
    return render_template("vendas_rapidas.html", vendas=vendas)


@app.route("/ordens/pdf/<int:id>")
@login_required
def ordem_pdf(id):
    ordem = OrdemServico.query.get_or_404(id)
    try:
        from pdf_ordem import gerar_pdf_ordem
        pdf = gerar_pdf_ordem(ordem)
        return send_file(pdf, as_attachment=False, download_name=f"OS_{ordem.numero or ordem.id}.pdf")
    except Exception as e:
        print("Erro PDF ordem:", e)
        return f"<h1>OS #{ordem.numero or ordem.id}</h1><p>Cliente: {ordem.cliente.nome if ordem.cliente else '-'}</p><p>Total: R$ {ordem.valor_total or 0}</p>"


@app.route("/lembretes")
@login_required
def lembretes():
    hoje = date.today()
    ano = hoje.year

    aniversariantes = []
    try:
        for c in Cliente.query.all():
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
        for v in Veiculo.query.all():
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
        hoje = date.today()
        ano = hoje.year
        pendentes = 0

        # Aniversários não enviados
        for c in Cliente.query.all():
            dn = getattr(c, "data_nascimento", None)
            if dn and dn.month == hoje.month and dn.day == hoje.day:
                envio = LembreteEnvio.query.filter_by(
                    tipo="ANIVERSARIO", cliente_id=c.id, ano=ano
                ).first()
                if not envio:
                    pendentes += 1

        # Revisões não dispensadas
        for v in Veiculo.query.all():
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
if __name__ == "__main__":
    app.run(debug=True)