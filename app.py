from flask import (
    Flask,
    render_template,
    request,
    redirect,
    send_file,
    jsonify
)

from datetime import datetime

from config import Config

from models import (
    db,
    Cliente,
    Veiculo,
    OrdemServico
)

from pdf_ordem_old import gerar_pdf_ordem


# =====================================================
# APP
# =====================================================

app = Flask(__name__)

app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()


# =====================================================
# DASHBOARD
# =====================================================

@app.route("/")
def dashboard():

    total_clientes = Cliente.query.count()

    total_veiculos = Veiculo.query.count()

    total_ordens = OrdemServico.query.count()

    faturamento = (
        db.session.query(
            db.func.sum(
                OrdemServico.valor_total
            )
        ).scalar()
        or 0
    )

    return render_template(
        "dashboard.html",
        total_clientes=total_clientes,
        total_veiculos=total_veiculos,
        total_os=total_ordens,
        faturamento=faturamento
    )


# =====================================================
# CLIENTES
# =====================================================

@app.route("/clientes")
def clientes():

    lista_clientes = (
        Cliente.query
        .order_by(Cliente.nome)
        .all()
    )

    return render_template(
        "clientes.html",
        clientes=lista_clientes
    )


@app.route(
    "/clientes/novo",
    methods=["GET", "POST"]
)
def novo_cliente():

    if request.method == "POST":

        cliente = Cliente(

            nome=request.form.get("nome"),

            cpf_cnpj=request.form.get("cpf_cnpj"),

            telefone=request.form.get("telefone"),

            whatsapp=request.form.get("whatsapp"),

            email=request.form.get("email"),

            endereco=request.form.get("endereco"),

            cidade=request.form.get("cidade"),

            estado=request.form.get("estado"),

            observacoes=request.form.get("observacoes")

        )

        db.session.add(cliente)

        db.session.commit()

        return redirect("/clientes")

    return render_template(
        "novo_cliente.html"
    )
@app.route(
    "/clientes/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_cliente(id):

    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":

        cliente.nome = request.form.get("nome")

        cliente.cpf_cnpj = request.form.get("cpf_cnpj")

        cliente.telefone = request.form.get("telefone")

        cliente.whatsapp = request.form.get("whatsapp")

        cliente.email = request.form.get("email")

        cliente.endereco = request.form.get("endereco")

        cliente.cidade = request.form.get("cidade")

        cliente.estado = request.form.get("estado")

        cliente.observacoes = request.form.get("observacoes")

        db.session.commit()

        return redirect("/clientes")

    return render_template(
        "novo_cliente.html",
        cliente=cliente
    )


@app.route("/clientes/excluir/<int:id>")
def excluir_cliente(id):

    cliente = Cliente.query.get_or_404(id)

    db.session.delete(cliente)

    db.session.commit()

    return redirect("/clientes")


# =====================================================
# VEÍCULOS
# =====================================================

@app.route("/veiculos")
def veiculos():

    lista_veiculos = (
        Veiculo.query
        .order_by(Veiculo.placa)
        .all()
    )

    return render_template(
        "veiculos.html",
        veiculos=lista_veiculos
    )


@app.route(
    "/veiculos/novo",
    methods=["GET", "POST"]
)
def novo_veiculo():

    if request.method == "POST":

        veiculo = Veiculo(

            cliente_id=int(
                request.form["cliente_id"]
            ),

            placa=request.form["placa"].upper(),

            marca=request.form.get("marca"),

            modelo=request.form.get("modelo"),

            ano=int(
                request.form["ano"]
            ) if request.form.get("ano") else None,

            cor=request.form.get("cor"),

            km=int(
                request.form["km"]
            ) if request.form.get("km") else None,

            chassi=request.form.get("chassi"),

            renavam=request.form.get(
                "renavam",
                ""
            ),

            motor=request.form.get("motor"),

            combustivel=request.form.get("combustivel"),

            observacoes=request.form.get(
                "observacoes",
                ""
            )

        )

        db.session.add(veiculo)

        db.session.commit()

        return redirect("/veiculos")

    clientes = (
        Cliente.query
        .order_by(Cliente.nome)
        .all()
    )

    return render_template(
        "novo_veiculo.html",
        clientes=clientes
    )


@app.route(
    "/veiculos/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_veiculo(id):

    veiculo = Veiculo.query.get_or_404(id)

    if request.method == "POST":

        veiculo.cliente_id = int(
            request.form["cliente_id"]
        )

        veiculo.placa = request.form["placa"].upper()

        veiculo.marca = request.form.get("marca")

        veiculo.modelo = request.form.get("modelo")

        veiculo.ano = (
            int(request.form["ano"])
            if request.form.get("ano")
            else None
        )

        veiculo.cor = request.form.get("cor")

        veiculo.km = (
            int(request.form["km"])
            if request.form.get("km")
            else None
        )

        veiculo.chassi = request.form.get("chassi")

        veiculo.renavam = request.form.get(
            "renavam",
            ""
        )

        veiculo.motor = request.form.get("motor")

        veiculo.combustivel = request.form.get("combustivel")

        veiculo.observacoes = request.form.get(
            "observacoes",
            ""
        )

        db.session.commit()

        return redirect("/veiculos")

    clientes = (
        Cliente.query
        .order_by(Cliente.nome)
        .all()
    )

    return render_template(
        "novo_veiculo.html",
        veiculo=veiculo,
        clientes=clientes
    )


@app.route("/veiculos/excluir/<int:id>")
def excluir_veiculo(id):

    veiculo = Veiculo.query.get_or_404(id)

    db.session.delete(veiculo)

    db.session.commit()

    return redirect("/veiculos")


# =====================================================
# ORDENS DE SERVIÇO
# =====================================================
@app.route("/ordens")
def ordens():

    lista_ordens = (
        OrdemServico.query
        .order_by(OrdemServico.id.desc())
        .all()
    )

    return render_template(
        "ordens.html",
        ordens=lista_ordens
    )


@app.route(
    "/ordens/nova",
    methods=["GET", "POST"]
)
def nova_ordem():

    if request.method == "POST":

        valor_servicos = float(
            request.form.get("valor_servicos") or 0
        )

        valor_pecas = float(
            request.form.get("valor_pecas") or 0
        )

        desconto = float(
            request.form.get("desconto") or 0
        )

        total = (
            valor_servicos +
            valor_pecas -
            desconto
        )

        ultimo_numero = (
            db.session.query(
                db.func.max(
                    OrdemServico.numero
                )
            ).scalar()
        )

        numero = (
            1
            if ultimo_numero is None
            else ultimo_numero + 1
        )

        ordem = OrdemServico(

            numero=numero,

            cliente_id=int(
                request.form["cliente_id"]
            ),

            veiculo_id=int(
                request.form["veiculo_id"]
            ),

            km=(
                int(request.form["km"])
                if request.form.get("km")
                else None
            ),

            defeito_relatado=request.form.get(
                "defeito_relatado"
            ),

            diagnostico=request.form.get(
                "diagnostico"
            ),

            servico_executado=request.form.get(
                "servico_executado"
            ),

            mecanico=request.form.get(
                "mecanico"
            ),

            valor_servicos=valor_servicos,

            valor_pecas=valor_pecas,

            desconto=desconto,

            valor_total=total,

            status="ABERTA"

        )

        db.session.add(ordem)

        db.session.commit()

        return redirect("/ordens")

    clientes = (
        Cliente.query
        .order_by(Cliente.nome)
        .all()
    )

    veiculos = (
        Veiculo.query
        .order_by(Veiculo.placa)
        .all()
    )

    return render_template(
        "nova_ordem.html",
        clientes=clientes,
        veiculos=veiculos
    )


@app.route(
    "/ordens/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_ordem(id):

    ordem = OrdemServico.query.get_or_404(id)

    if request.method == "POST":

        ordem.cliente_id = int(
            request.form["cliente_id"]
        )

        ordem.veiculo_id = int(
            request.form["veiculo_id"]
        )

        ordem.km = (
            int(request.form["km"])
            if request.form.get("km")
            else None
        )

        ordem.defeito_relatado = request.form.get(
            "defeito_relatado"
        )

        ordem.diagnostico = request.form.get(
            "diagnostico"
        )

        ordem.servico_executado = request.form.get(
            "servico_executado"
        )

        ordem.mecanico = request.form.get(
            "mecanico"
        )

        ordem.valor_servicos = float(
            request.form.get("valor_servicos") or 0
        )

        ordem.valor_pecas = float(
            request.form.get("valor_pecas") or 0
        )

        ordem.desconto = float(
            request.form.get("desconto") or 0
        )

        ordem.valor_total = (
            ordem.valor_servicos +
            ordem.valor_pecas -
            ordem.desconto
        )

        ordem.status = request.form.get(
            "status",
            "ABERTA"
        )

        db.session.commit()

        return redirect("/ordens")

    clientes = (
        Cliente.query
        .order_by(Cliente.nome)
        .all()
    )

    veiculos = (
        Veiculo.query
        .order_by(Veiculo.placa)
        .all()
    )

    return render_template(
        "editar_ordem.html",
        ordem=ordem,
        clientes=clientes,
        veiculos=veiculos
    )
# =====================================================
# FINALIZAR ORDEM
# =====================================================

@app.route("/ordens/finalizar/<int:id>")
def finalizar_ordem(id):

    ordem = OrdemServico.query.get_or_404(id)

    ordem.status = "FINALIZADA"

    db.session.commit()

    return redirect("/ordens")


# =====================================================
# EXCLUIR ORDEM
# =====================================================

@app.route("/ordens/excluir/<int:id>")
def excluir_ordem(id):

    ordem = OrdemServico.query.get_or_404(id)

    db.session.delete(ordem)

    db.session.commit()

    return redirect("/ordens")


# =====================================================
# PDF DA ORDEM
# =====================================================

@app.route("/ordens/pdf/<int:id>")
def pdf_ordem(id):

    ordem = OrdemServico.query.get_or_404(id)

    pdf = gerar_pdf_ordem(ordem)

    return send_file(
        pdf,
        download_name=f"OS_{ordem.numero}.pdf",
        as_attachment=False,
        mimetype="application/pdf"
    )


# =====================================================
# API VEÍCULOS DO CLIENTE
# =====================================================

@app.route("/api/veiculos/<int:cliente_id>")
def api_veiculos(cliente_id):

    lista = (
        Veiculo.query
        .filter_by(cliente_id=cliente_id)
        .order_by(Veiculo.placa)
        .all()
    )

    return jsonify([
        {
            "id": v.id,
            "placa": v.placa,
            "marca": v.marca,
            "modelo": v.modelo,
            "km": v.km
        }
        for v in lista
    ])


# =====================================================
# DADOS DO DASHBOARD
# =====================================================

@app.route("/dashboard/dados")
def dashboard_dados():

    total_clientes = Cliente.query.count()

    total_veiculos = Veiculo.query.count()

    total_ordens = OrdemServico.query.count()

    faturamento = (
        db.session.query(
            db.func.sum(
                OrdemServico.valor_total
            )
        ).scalar()
        or 0
    )

    return jsonify({

        "clientes": total_clientes,

        "veiculos": total_veiculos,

        "ordens": total_ordens,

        "faturamento": faturamento

    })


# =====================================================
# ESTOQUE
# =====================================================

@app.route("/estoque")
def estoque():

    return render_template("estoque.html")


# =====================================================
# FINANCEIRO
# =====================================================

@app.route("/financeiro")
def financeiro():

    return render_template("financeiro.html")


# =====================================================
# USUÁRIOS
# =====================================================

@app.route("/usuarios")
def usuarios():

    return render_template("usuarios.html")


# =====================================================
# CONFIGURAÇÕES
# =====================================================

@app.route("/configuracoes")
def configuracoes():

    return render_template("configuracoes.html")


# =====================================================
# INICIAR SERVIDOR
# =====================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )