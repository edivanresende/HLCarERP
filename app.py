from flask import (
    Flask,
    render_template,
    request,
    redirect,
    send_file,
    jsonify
)

from datetime import datetime, date

from sqlalchemy import text

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
)

from pdf_ordem_old import gerar_pdf_ordem


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()


@app.route("/")
def dashboard():
    total_clientes = Cliente.query.count()
    total_veiculos = Veiculo.query.count()
    total_ordens = OrdemServico.query.count()
    faturamento = db.session.query(db.func.sum(OrdemServico.valor_total)).scalar() or 0
    try:
        mecanicos = Mecanico.query.filter_by(ativo=True).order_by(Mecanico.nome).all()
    except Exception:
        mecanicos = []
    return render_template(
        "dashboard.html",
        total_clientes=total_clientes,
        total_veiculos=total_veiculos,
        total_os=total_ordens,
        faturamento=faturamento,
        mecanicos=mecanicos
    )


@app.route("/clientes")
def clientes():
    lista_clientes = Cliente.query.order_by(Cliente.nome).all()
    return render_template("clientes.html", clientes=lista_clientes)


@app.route("/clientes/novo", methods=["GET", "POST"])
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
    return render_template("novo_cliente.html")


@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
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
    return render_template("novo_cliente.html", cliente=cliente)


@app.route("/clientes/excluir/<int:id>")
def excluir_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    return redirect("/clientes")


@app.route("/veiculos")
def veiculos():
    lista_veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    return render_template("veiculos.html", veiculos=lista_veiculos)


@app.route("/veiculos/novo", methods=["GET", "POST"])
def novo_veiculo():
    if request.method == "POST":
        veiculo = Veiculo(
            cliente_id=int(request.form["cliente_id"]),
            placa=request.form["placa"].upper(),
            marca=request.form.get("marca"),
            modelo=request.form.get("modelo"),
            cor=request.form.get("cor"),
            km=int(request.form["km"]) if request.form.get("km") else None,
            chassi=request.form.get("chassi"),
            renavam=request.form.get("renavam", ""),
            motor=request.form.get("motor"),
            combustivel=request.form.get("combustivel"),
            observacoes=request.form.get("observacoes", "")
        )
        db.session.add(veiculo)
        db.session.commit()
        return redirect("/veiculos")
    clientes = Cliente.query.order_by(Cliente.nome).all()
    return render_template("novo_veiculo.html", clientes=clientes)


@app.route("/veiculos/editar/<int:id>", methods=["GET", "POST"])
def editar_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    if request.method == "POST":
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
        db.session.commit()
        return redirect("/veiculos")
    clientes = Cliente.query.order_by(Cliente.nome).all()
    return render_template("novo_veiculo.html", veiculo=veiculo, clientes=clientes)


@app.route("/veiculos/excluir/<int:id>")
def excluir_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    db.session.delete(veiculo)
    db.session.commit()
    return redirect("/veiculos")


@app.route("/ordens")
def ordens():
    lista_ordens = OrdemServico.query.order_by(OrdemServico.id.desc()).all()
    return render_template("ordens.html", ordens=lista_ordens)


@app.route("/ordens/nova", methods=["GET", "POST"])
def nova_ordem():
    if request.method == "POST":
        valor_pecas = float(request.form.get("valor_pecas") or 0)
        desconto = float(request.form.get("desconto") or 0)
        mecanicos_ids = request.form.getlist("mecanicos")
        nomes = []
        total_servicos = 0.0
        detalhes = []

        for mid in mecanicos_ids:
            try:
                m = Mecanico.query.get(int(mid))
                if not m:
                    continue
                nomes.append(m.nome)
                dur = int(request.form.get(f"duracao_{mid}") or 40)
                val = float(request.form.get(f"valor_{mid}") or 0)
                serv = (request.form.get(f"servico_{mid}") or "").strip()
                total_servicos += val
                detalhes.append({"mecanico": m, "duracao": dur, "valor": val, "servico": serv or m.nome})
            except Exception:
                pass

        total = total_servicos + valor_pecas - desconto
        ultimo_numero = db.session.query(db.func.max(OrdemServico.numero)).scalar()
        numero = 1 if ultimo_numero is None else ultimo_numero + 1

        ordem = OrdemServico(
            numero=numero,
            cliente_id=int(request.form["cliente_id"]),
            veiculo_id=int(request.form["veiculo_id"]),
            km=int(request.form["km"]) if request.form.get("km") else None,
            defeito_relatado=request.form.get("defeito_relatado"),
            diagnostico=request.form.get("diagnostico"),
            servico_executado=request.form.get("servico_executado"),
            mecanico=", ".join(nomes) if nomes else None,
            valor_servicos=total_servicos,
            valor_produtos=valor_pecas,
            desconto=desconto,
            valor_total=total,
            status="ABERTA",
        )
        try:
            ordem.empresa_id = 1
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
            ))
            if agendar:
                entrada = int(m.hora_entrada or 9)
                almoco_i = int(m.almoco_inicio or 12)
                almoco_f = int(m.almoco_fim or 14)
                ocupados = Agendamento.query.filter_by(mecanico_id=m.id, data=hoje).order_by(Agendamento.hora_inicio).all()
                cursor = entrada * 60
                for ag in ocupados:
                    try:
                        h, mi = map(int, ag.hora_inicio.split(":"))
                        ini = h * 60 + mi
                        dur = ag.duracao_real_min or ag.duracao_estimada_min or 40
                        fim = ini + dur
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
def editar_ordem(id):
    ordem = OrdemServico.query.get_or_404(id)
    if request.method == "POST":
        ordem.cliente_id = int(request.form["cliente_id"])
        ordem.veiculo_id = int(request.form["veiculo_id"])
        ordem.km = int(request.form["km"]) if request.form.get("km") else None
        ordem.defeito_relatado = request.form.get("defeito_relatado")
        ordem.diagnostico = request.form.get("diagnostico")
        ordem.servico_executado = request.form.get("servico_executado")
        ordem.mecanico = request.form.get("mecanico")
        ordem.valor_servicos = float(request.form.get("valor_servicos") or 0)
        ordem.valor_produtos = float(request.form.get("valor_pecas") or 0)
        ordem.desconto = float(request.form.get("desconto") or 0)
        ordem.valor_total = ordem.valor_servicos + ordem.valor_produtos - ordem.desconto
        ordem.status = request.form.get("status", "ABERTA")
        db.session.commit()
        return redirect("/ordens")
    clientes = Cliente.query.order_by(Cliente.nome).all()
    veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    try:
        lista_mecanicos = Mecanico.query.filter_by(ativo=True).order_by(Mecanico.nome).all()
    except Exception:
        lista_mecanicos = []
    return render_template("editar_ordem.html", ordem=ordem, clientes=clientes, veiculos=veiculos, mecanicos=lista_mecanicos)


@app.route("/ordens/finalizar/<int:id>")
def finalizar_ordem(id):
    ordem = OrdemServico.query.get_or_404(id)
    ordem.status = "FINALIZADA"
    db.session.commit()
    return redirect("/ordens")


@app.route("/ordens/excluir/<int:id>")
def excluir_ordem(id):
    ordem = OrdemServico.query.get_or_404(id)
    db.session.delete(ordem)
    db.session.commit()
    return redirect("/ordens")


@app.route("/ordens/pdf/<int:id>")
def pdf_ordem(id):
    ordem = OrdemServico.query.get_or_404(id)
    pdf = gerar_pdf_ordem(ordem)
    return send_file(pdf, download_name=f"OS_{ordem.numero}.pdf", as_attachment=False, mimetype="application/pdf")


@app.route("/api/veiculos/<int:cliente_id>")
def api_veiculos(cliente_id):
    lista = Veiculo.query.filter_by(cliente_id=cliente_id).order_by(Veiculo.placa).all()
    return jsonify([
        {"id": v.id, "placa": v.placa, "marca": getattr(v, "marca", None), "modelo": getattr(v, "modelo", None), "km": getattr(v, "km", None)}
        for v in lista
    ])


@app.route("/dashboard/dados")
def dashboard_dados():
    total_clientes = Cliente.query.count()
    total_veiculos = Veiculo.query.count()
    total_ordens = OrdemServico.query.count()
    faturamento = db.session.query(db.func.sum(OrdemServico.valor_total)).scalar() or 0
    return jsonify({"clientes": total_clientes, "veiculos": total_veiculos, "ordens": total_ordens, "faturamento": faturamento})


@app.route("/estoque")
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
def produtos():
    return redirect("/estoque")


@app.route("/produtos/novo", methods=["GET", "POST"])
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
def categorias():
    try:
        lista = Categoria.query.order_by(Categoria.nome).all()
    except Exception:
        lista = []
    return render_template("categorias.html", categorias=lista)


@app.route("/categorias/novo", methods=["GET", "POST"])
@app.route("/categorias/salvar", methods=["POST"])
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
def fabricantes():
    try:
        lista = Fabricante.query.order_by(Fabricante.nome).all()
    except Exception:
        lista = []
    return render_template("fabricantes.html", fabricantes=lista)


@app.route("/fabricantes/novo", methods=["GET", "POST"])
@app.route("/fabricantes/salvar", methods=["POST"])
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
def fornecedores():
    try:
        lista = Fornecedor.query.order_by(Fornecedor.razao_social).all()
    except Exception:
        lista = []
    return render_template("fornecedores.html", fornecedores=lista)


@app.route("/fornecedores/novo", methods=["GET", "POST"])
@app.route("/fornecedores/salvar", methods=["POST"])
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
def salvar_compra():
    try:
        print("=== POST /compras/salvar ===")
        print("form:", dict(request.form))

        fornecedor_id = int(request.form.get("fornecedor_id") or 0)
        if not fornecedor_id:
            print("Sem fornecedor")
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
        print("itens:", itens, "total:", valor_total)

        if not itens:
            print("Nenhum item válido")
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

                    # SQL direto — preenche a coluna obrigatória "tipo"
                    try:
                        db.session.execute(
                            text(
                                "INSERT INTO movimentacoes_estoque "
                                "(empresa_id, produto_id, tipo, quantidade, origem, observacoes, data_movimento) "
                                "VALUES (:empresa_id, :produto_id, :tipo, :quantidade, :origem, :obs, :data_mov)"
                            ),
                            {
                                "empresa_id": 1,
                                "produto_id": prod.id,
                                "tipo": "ENTRADA",
                                "quantidade": it["qtd"],
                                "origem": "COMPRA",
                                "obs": "Compra NF {}".format(numero_nf or compra.id),
                                "data_mov": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            },
                        )
                    except Exception as e_mov:
                        print("Aviso movimentacao (compra continua salva):", e_mov)

        db.session.commit()
        print("Compra salva id=", compra.id, "total=", valor_total)
    except Exception as e:
        db.session.rollback()
        print("Erro compra:", type(e).__name__, e)

    return redirect("/compras")


@app.route("/compras/ver/<int:id>")
def ver_compra(id):
    compra = Compra.query.get_or_404(id)
    try:
        itens = ItemCompra.query.filter_by(compra_id=id).all()
    except Exception:
        itens = []
    return render_template("ver_compra.html", compra=compra, itens=itens)


@app.route("/compras/excluir/<int:id>")
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
def inventario():
    try:
        lista = Inventario.query.order_by(Inventario.id.desc()).all()
    except Exception:
        lista = []
    return render_template("inventario.html", inventarios=lista, total_inventarios=len(lista))


@app.route("/movimentacoes")
def movimentacoes():
    try:
        lista = MovimentacaoEstoque.query.order_by(MovimentacaoEstoque.id.desc()).all()
    except Exception:
        lista = []
    return render_template("movimentacoes.html", movimentacoes=lista, total_movimentacoes=len(lista))


@app.route("/financeiro")
def financeiro():
    try:
        total_ordens = OrdemServico.query.count()
        faturamento = db.session.query(db.func.sum(OrdemServico.valor_total)).scalar() or 0
        abertas = OrdemServico.query.filter_by(status="ABERTA").count()
        finalizadas = OrdemServico.query.filter_by(status="FINALIZADA").count()
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
        finalizadas=finalizadas
    )


@app.route("/usuarios")
def usuarios():
    return render_template("usuarios.html")


@app.route("/configuracoes")
def configuracoes():
    return render_template("configuracoes.html")


@app.route("/mecanicos")
def mecanicos():
    try:
        lista = Mecanico.query.order_by(Mecanico.nome).all()
    except Exception:
        lista = []
    return render_template("mecanicos.html", mecanicos=lista)


@app.route("/mecanicos/novo", methods=["GET", "POST"])
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
def excluir_mecanico(id):
    m = Mecanico.query.get_or_404(id)
    db.session.delete(m)
    db.session.commit()
    return redirect("/mecanicos")


@app.route("/api/agenda")
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


if __name__ == "__main__":
    app.run(debug=True)