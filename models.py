from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, Index, Numeric
from datetime import datetime

db = SQLAlchemy()


# ==========================================================
# EMPRESA
# ==========================================================

class Empresa(db.Model):
    __tablename__ = "empresas"

    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(20), unique=True, nullable=False)
    inscricao_estadual = db.Column(db.String(30))
    telefone = db.Column(db.String(30))
    whatsapp = db.Column(db.String(30))
    email = db.Column(db.String(150))
    site = db.Column(db.String(200))
    cep = db.Column(db.String(15))
    endereco = db.Column(db.String(200))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    logo = db.Column(db.String(255))
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ==========================================================
# USUÁRIOS
# ==========================================================

class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    nome = db.Column(db.String(150), nullable=False)
    login = db.Column(db.String(80), nullable=False)
    senha = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(150))
    perfil = db.Column(db.String(20), nullable=False, default="CONSULTOR")
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")

    __table_args__ = (
        UniqueConstraint("empresa_id", "login", name="uk_usuario_login_empresa"),
    )


# ==========================================================
# CLIENTES
# ==========================================================

class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    nome = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), default="FISICA")
    cpf_cnpj = db.Column(db.String(20))
    rg_ie = db.Column(db.String(30))
    telefone = db.Column(db.String(30))
    whatsapp = db.Column(db.String(30))
    email = db.Column(db.String(150))
    cep = db.Column(db.String(15))
    endereco = db.Column(db.String(200))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    observacoes = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")

    __table_args__ = (
        Index("idx_cliente_nome", "empresa_id", "nome"),
        Index("idx_cliente_cpf", "empresa_id", "cpf_cnpj"),
    )


# ==========================================================
# VEÍCULOS
# ==========================================================

class Veiculo(db.Model):
    __tablename__ = "veiculos"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)
    placa = db.Column(db.String(10), nullable=False)
    marca = db.Column(db.String(80))
    modelo = db.Column(db.String(120))
    versao = db.Column(db.String(120))
    ano_fabricacao = db.Column(db.Integer)
    ano_modelo = db.Column(db.Integer)
    cor = db.Column(db.String(40))
    combustivel = db.Column(db.String(30))
    cambio = db.Column(db.String(30))
    motor = db.Column(db.String(80))
    chassi = db.Column(db.String(40))
    renavam = db.Column(db.String(20))
    km_atual = db.Column(db.Integer, default=0)
    observacoes = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")
    cliente = db.relationship("Cliente", backref="veiculos")

    __table_args__ = (
        UniqueConstraint("empresa_id", "placa", name="uk_placa_empresa"),
        Index("idx_veiculo_modelo", "empresa_id", "modelo"),
    )


# ==========================================================
# CATEGORIAS
# ==========================================================

class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.String(255))
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")

    __table_args__ = (
        UniqueConstraint("empresa_id", "nome", name="uk_categoria_empresa"),
    )


# ==========================================================
# FABRICANTES
# ==========================================================

class Fabricante(db.Model):
    __tablename__ = "fabricantes"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    telefone = db.Column(db.String(30))
    whatsapp = db.Column(db.String(30))
    email = db.Column(db.String(150))
    site = db.Column(db.String(255))
    observacoes = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")

    __table_args__ = (
        UniqueConstraint("empresa_id", "nome", name="uk_fabricante_empresa"),
    )


# ==========================================================
# FORNECEDORES
# ==========================================================

class Fornecedor(db.Model):
    __tablename__ = "fornecedores"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200))
    cnpj = db.Column(db.String(20))
    inscricao_estadual = db.Column(db.String(30))
    telefone = db.Column(db.String(30))
    whatsapp = db.Column(db.String(30))
    email = db.Column(db.String(150))
    contato = db.Column(db.String(150))
    cep = db.Column(db.String(15))
    endereco = db.Column(db.String(200))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    observacoes = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")

    __table_args__ = (
        Index("idx_fornecedor_nome", "empresa_id", "razao_social"),
        Index("idx_fornecedor_cnpj", "empresa_id", "cnpj"),
    )


# ==========================================================
# PRODUTOS
# ==========================================================

class Produto(db.Model):
    __tablename__ = "produtos"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"), nullable=False, index=True)
    codigo = db.Column(db.String(30), nullable=False)
    codigo_barras = db.Column(db.String(100))
    descricao = db.Column(db.String(250), nullable=False)
    descricao_reduzida = db.Column(db.String(120))
    referencia = db.Column(db.String(100))
    unidade = db.Column(db.String(10), nullable=False, default="UN")
    ncm = db.Column(db.String(20))
    cest = db.Column(db.String(20))
    peso = db.Column(Numeric(18, 3), default=0)
    localizacao = db.Column(db.String(80))
    controla_estoque = db.Column(db.Boolean, default=True, nullable=False)
    permite_venda = db.Column(db.Boolean, default=True, nullable=False)
    estoque_minimo = db.Column(Numeric(18, 3), default=0)
    estoque_maximo = db.Column(Numeric(18, 3), default=0)
    estoque_atual = db.Column(Numeric(18, 3), default=0)
    estoque_reservado = db.Column(Numeric(18, 3), default=0)
    preco_compra = db.Column(Numeric(18, 2), default=0)
    preco_venda = db.Column(Numeric(18, 2), default=0)
    margem_padrao = db.Column(Numeric(18, 2), default=0)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")
    categoria = db.relationship("Categoria")
    fornecedores = db.relationship(
        "ProdutoFornecedor",
        back_populates="produto",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uk_produto_codigo_empresa"),
        UniqueConstraint("empresa_id", "codigo_barras", name="uk_produto_barra_empresa"),
        Index("idx_produto_descricao", "empresa_id", "descricao"),
    )


# ==========================================================
# PRODUTO X FORNECEDOR
# ==========================================================

class ProdutoFornecedor(db.Model):
    __tablename__ = "produto_fornecedor"

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedores.id"), nullable=False)
    codigo_fornecedor = db.Column(db.String(60))
    ultimo_custo = db.Column(Numeric(18, 2), default=0)
    prazo_entrega = db.Column(db.Integer, default=0)
    fornecedor_principal = db.Column(db.Boolean, default=False)
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    produto = db.relationship("Produto", back_populates="fornecedores")
    fornecedor = db.relationship("Fornecedor")

    __table_args__ = (
        UniqueConstraint("produto_id", "fornecedor_id", name="uk_produto_fornecedor"),
    )


# ==========================================================
# COMPRAS
# ==========================================================

class Compra(db.Model):
    __tablename__ = "compras"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedores.id"), nullable=False, index=True)
    numero_nf = db.Column(db.String(30))
    serie_nf = db.Column(db.String(10))
    chave_nf = db.Column(db.String(60))
    data_emissao = db.Column(db.DateTime)
    data_entrada = db.Column(db.DateTime, default=datetime.utcnow)
    frete = db.Column(Numeric(18, 2), default=0)
    seguro = db.Column(Numeric(18, 2), default=0)
    desconto = db.Column(Numeric(18, 2), default=0)
    outras_despesas = db.Column(Numeric(18, 2), default=0)
    ipi = db.Column(Numeric(18, 2), default=0)
    icms = db.Column(Numeric(18, 2), default=0)
    pis = db.Column(Numeric(18, 2), default=0)
    cofins = db.Column(Numeric(18, 2), default=0)
    valor_total = db.Column(Numeric(18, 2), default=0)
    status = db.Column(db.String(20), default="ABERTA")
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")
    fornecedor = db.relationship("Fornecedor")
    itens = db.relationship("ItemCompra", back_populates="compra", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_compra_data", "empresa_id", "data_entrada"),
    )


# ==========================================================
# ITENS DA COMPRA
# ==========================================================

class ItemCompra(db.Model):
    __tablename__ = "itens_compra"

    id = db.Column(db.Integer, primary_key=True)
    compra_id = db.Column(db.Integer, db.ForeignKey("compras.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    quantidade = db.Column(Numeric(18, 3), default=0)
    valor_unitario = db.Column(Numeric(18, 2), default=0)
    desconto = db.Column(Numeric(18, 2), default=0)
    ipi = db.Column(Numeric(18, 2), default=0)
    icms = db.Column(Numeric(18, 2), default=0)
    frete_rateado = db.Column(Numeric(18, 2), default=0)
    custo_final = db.Column(Numeric(18, 2), default=0)
    valor_total = db.Column(Numeric(18, 2), default=0)

    compra = db.relationship("Compra", back_populates="itens")
    produto = db.relationship("Produto")


# ==========================================================
# MOVIMENTAÇÃO DE ESTOQUE
# ==========================================================

class MovimentacaoEstoque(db.Model):
    __tablename__ = "movimentacoes_estoque"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False, index=True)
    compra_id = db.Column(db.Integer, db.ForeignKey("compras.id"))
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey("ordens_servico.id"))
    tipo_movimento = db.Column(db.String(20), nullable=False)
    origem = db.Column(db.String(30), nullable=False)
    quantidade = db.Column(Numeric(18, 3), nullable=False)
    saldo_anterior = db.Column(Numeric(18, 3), default=0)
    saldo_atual = db.Column(Numeric(18, 3), default=0)
    custo_unitario = db.Column(Numeric(18, 2), default=0)
    valor_total = db.Column(Numeric(18, 2), default=0)
    observacoes = db.Column(db.Text)
    data_movimento = db.Column(db.DateTime, default=datetime.utcnow)

    empresa = db.relationship("Empresa")
    produto = db.relationship("Produto")
    compra = db.relationship("Compra")
    ordem_servico = db.relationship("OrdemServico")

    __table_args__ = (
        Index("idx_mov_produto", "empresa_id", "produto_id", "data_movimento"),
    )


# ==========================================================
# INVENTÁRIOS
# ==========================================================

class Inventario(db.Model):
    __tablename__ = "inventarios"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    data_inventario = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="ABERTO")
    observacoes = db.Column(db.Text)

    empresa = db.relationship("Empresa")
    itens = db.relationship("ItemInventario", back_populates="inventario", cascade="all, delete-orphan")


# ==========================================================
# ITENS DO INVENTÁRIO
# ==========================================================

class ItemInventario(db.Model):
    __tablename__ = "itens_inventario"

    id = db.Column(db.Integer, primary_key=True)
    inventario_id = db.Column(db.Integer, db.ForeignKey("inventarios.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    estoque_sistema = db.Column(Numeric(18, 3), default=0)
    estoque_contado = db.Column(Numeric(18, 3), default=0)
    diferenca = db.Column(Numeric(18, 3), default=0)
    observacoes = db.Column(db.Text)

    inventario = db.relationship("Inventario", back_populates="itens")
    produto = db.relationship("Produto")


# ==========================================================
# ORDEM DE SERVIÇO
# ==========================================================

class OrdemServico(db.Model):
    __tablename__ = "ordens_servico"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    numero = db.Column(db.Integer, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculos.id"))
    status = db.Column(db.String(20), default="ABERTA")
    prioridade = db.Column(db.String(20), default="NORMAL")
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    data_inicio = db.Column(db.DateTime)
    data_finalizacao = db.Column(db.DateTime)
    km = db.Column(db.Integer)
    consultor = db.Column(db.String(120))
    mecanico = db.Column(db.String(120))
    defeito_relatado = db.Column(db.Text)
    diagnostico = db.Column(db.Text)
    servico_executado = db.Column(db.Text)
    observacoes = db.Column(db.Text)
    valor_servicos = db.Column(Numeric(18, 2), default=0)
    valor_produtos = db.Column(Numeric(18, 2), default=0)
    desconto = db.Column(Numeric(18, 2), default=0)
    acrescimo = db.Column(Numeric(18, 2), default=0)
    valor_total = db.Column(Numeric(18, 2), default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")
    cliente = db.relationship("Cliente")
    veiculo = db.relationship("Veiculo")
    itens = db.relationship("ItemOrdemServico", back_populates="ordem_servico", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uk_os_empresa"),
    )


# ==========================================================
# ITENS DA ORDEM DE SERVIÇO
# ==========================================================

class ItemOrdemServico(db.Model):
    __tablename__ = "itens_ordem_servico"

    id = db.Column(db.Integer, primary_key=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey("ordens_servico.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"))
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedores.id"))
    origem = db.Column(db.String(20), nullable=False)
    tipo_item = db.Column(db.String(20), default="PRODUTO")
    descricao = db.Column(db.String(250), nullable=False)
    quantidade = db.Column(Numeric(18, 3), default=1)
    custo_unitario = db.Column(Numeric(18, 2), default=0)
    valor_parceiro = db.Column(Numeric(18, 2), default=0)
    margem = db.Column(Numeric(18, 2), default=0)
    lucro = db.Column(Numeric(18, 2), default=0)
    valor_unitario = db.Column(Numeric(18, 2), default=0)
    desconto = db.Column(Numeric(18, 2), default=0)
    valor_total = db.Column(Numeric(18, 2), default=0)
    observacoes = db.Column(db.Text)

    ordem_servico = db.relationship("OrdemServico", back_populates="itens")
    produto = db.relationship("Produto")
    fornecedor = db.relationship("Fornecedor")


# ==========================================================
# CONTAS A RECEBER
# ==========================================================

class ContaReceber(db.Model):
    __tablename__ = "contas_receber"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey("ordens_servico.id"))
    descricao = db.Column(db.String(250), nullable=False)
    data_emissao = db.Column(db.DateTime, default=datetime.utcnow)
    data_vencimento = db.Column(db.DateTime, nullable=False)
    data_pagamento = db.Column(db.DateTime)
    valor = db.Column(Numeric(18, 2), default=0)
    juros = db.Column(Numeric(18, 2), default=0)
    multa = db.Column(Numeric(18, 2), default=0)
    desconto = db.Column(Numeric(18, 2), default=0)
    valor_recebido = db.Column(Numeric(18, 2), default=0)
    forma_pagamento = db.Column(db.String(30))
    status = db.Column(db.String(20), default="PENDENTE")
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")
    cliente = db.relationship("Cliente")
    ordem_servico = db.relationship("OrdemServico")


# ==========================================================
# CONTAS A PAGAR
# ==========================================================

class ContaPagar(db.Model):
    __tablename__ = "contas_pagar"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedores.id"), nullable=False)
    compra_id = db.Column(db.Integer, db.ForeignKey("compras.id"))
    descricao = db.Column(db.String(250), nullable=False)
    data_emissao = db.Column(db.DateTime, default=datetime.utcnow)
    data_vencimento = db.Column(db.DateTime, nullable=False)
    data_pagamento = db.Column(db.DateTime)
    valor = db.Column(Numeric(18, 2), default=0)
    juros = db.Column(Numeric(18, 2), default=0)
    multa = db.Column(Numeric(18, 2), default=0)
    desconto = db.Column(Numeric(18, 2), default=0)
    valor_pago = db.Column(Numeric(18, 2), default=0)
    forma_pagamento = db.Column(db.String(30))
    status = db.Column(db.String(20), default="PENDENTE")
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship("Empresa")
    fornecedor = db.relationship("Fornecedor")
    compra = db.relationship("Compra")


# ==========================================================
# MOVIMENTAÇÃO DE CAIXA
# ==========================================================

class Caixa(db.Model):
    __tablename__ = "caixa"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    data_movimento = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(10), nullable=False)
    origem = db.Column(db.String(30), nullable=False)
    documento = db.Column(db.String(50))
    descricao = db.Column(db.String(250), nullable=False)
    valor = db.Column(Numeric(18, 2), nullable=False)
    saldo = db.Column(Numeric(18, 2), default=0)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    observacoes = db.Column(db.Text)

    empresa = db.relationship("Empresa")
    usuario = db.relationship("Usuario")

    __table_args__ = (
        Index("idx_caixa_data", "empresa_id", "data_movimento"),
    )


# ==========================================================
# MECÂNICOS
# ==========================================================

class Mecanico(db.Model):
    __tablename__ = "mecanicos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20))
    whatsapp = db.Column(db.String(20))
    ativo = db.Column(db.Boolean, default=True)

    # salario | comissao | salario_comissao
    forma_pagamento = db.Column(db.String(30), default="comissao")

    salario = db.Column(db.Float, default=0)
    percentual_comissao = db.Column(db.Float, default=20)

    hora_entrada = db.Column(db.Integer, default=9)
    hora_saida = db.Column(db.Integer, default=18)

    almoco_inicio = db.Column(db.Integer, default=12)
    almoco_fim = db.Column(db.Integer, default=14)

    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


# ==========================================================
# VÍNCULO OS x MECÂNICO (tempo + comissão por mecânico)
# ==========================================================

class OrdemServicoMecanico(db.Model):
    __tablename__ = "ordem_servico_mecanicos"

    id = db.Column(db.Integer, primary_key=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey("ordens_servico.id"), nullable=False)
    mecanico_id = db.Column(db.Integer, db.ForeignKey("mecanicos.id"), nullable=False)

    # Tempo estimado na abertura da OS (pode mudar depois na agenda)
    duracao_estimada_min = db.Column(db.Integer, default=40)

    # Valores para comissão
    valor_mercado = db.Column(db.Float, default=0)
    valor_negociado = db.Column(db.Float, default=0)
    percentual_comissao = db.Column(db.Float, default=20)
    base_comissao = db.Column(db.Float, default=0)
    valor_comissao = db.Column(db.Float, default=0)

    ordem_servico = db.relationship("OrdemServico", backref="mecanicos_os")
    mecanico = db.relationship("Mecanico", backref="ordens_mecanico")


# ==========================================================
# AGENDAMENTO (agenda real — editável)
# ==========================================================

class Agendamento(db.Model):
    __tablename__ = "agendamentos"

    id = db.Column(db.Integer, primary_key=True)
    mecanico_id = db.Column(db.Integer, db.ForeignKey("mecanicos.id"), nullable=False)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey("ordens_servico.id"))

    data = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.String(5), nullable=False)   # "09:00"

    # Estimado na criação / Real quando você ajusta na agenda
    duracao_estimada_min = db.Column(db.Integer, default=40)
    duracao_real_min = db.Column(db.Integer)                 # se None, usa a estimada
    hora_fim = db.Column(db.String(5))                       # recalculada ao alterar duração

    descricao = db.Column(db.String(250))
    status = db.Column(db.String(20), default="AGENDADO")
    # AGENDADO | EM_EXECUCAO | CONCLUIDO | CANCELADO

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    alterado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mecanico = db.relationship("Mecanico", backref="agendamentos")
    ordem_servico = db.relationship("OrdemServico", backref="agendamentos")