from io import BytesIO
import os
from datetime import timedelta

import qrcode

from flask import current_app

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
)


LARANJA = colors.HexColor("#FF6B00")
CINZA_ESCURO = colors.HexColor("#1F2937")
CINZA_CLARO = colors.HexColor("#F3F4F6")
CINZA_BORDA = colors.HexColor("#D1D5DB")


def _money(v):
    try:
        return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def gerar_pdf_ordem(ordem):
    buffer = BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=(21 * cm, 29.7 * cm),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.2 * cm,
    )

    estilos = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle(
        "TituloOS",
        parent=estilos["Heading1"],
        fontSize=16,
        textColor=CINZA_ESCURO,
        alignment=TA_CENTER,
        spaceAfter=2,
        fontName="Helvetica-Bold",
    )

    estilo_subtitulo = ParagraphStyle(
        "SubOS",
        parent=estilos["Normal"],
        fontSize=11,
        textColor=LARANJA,
        alignment=TA_CENTER,
        spaceAfter=8,
        fontName="Helvetica-Bold",
    )

    estilo_secao = ParagraphStyle(
        "SecaoOS",
        parent=estilos["Normal"],
        fontSize=10,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
    )

    estilo_normal = ParagraphStyle(
        "NormalOS",
        parent=estilos["Normal"],
        fontSize=9,
        textColor=CINZA_ESCURO,
        leading=12,
    )

    estilo_label = ParagraphStyle(
        "LabelOS",
        parent=estilos["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#6B7280"),
        fontName="Helvetica-Bold",
    )

    estilo_valor = ParagraphStyle(
        "ValorOS",
        parent=estilos["Normal"],
        fontSize=9,
        textColor=CINZA_ESCURO,
    )

    elementos = []

    # ==========================================================
    # CABEÇALHO
    # ==========================================================
    logo_path = None
    caminhos_logo = [
        os.path.join(current_app.root_path, "static", "icons", "icon-512.png"),
        os.path.join(current_app.root_path, "static", "icons", "icon-192.png"),
        os.path.join(current_app.root_path, "static", "img", "logo_hlcar.png"),
        os.path.join(current_app.root_path, "static", "logo_hlcar.png"),
        os.path.join(current_app.root_path, "static", "icon-512.png"),
    ]
    for caminho in caminhos_logo:
        if os.path.exists(caminho):
            logo_path = caminho
            break

    logo_img = Image(logo_path, width=2.2 * cm, height=2.2 * cm) if logo_path else Paragraph("", estilo_normal)

    cab_direita = [
        [Paragraph("<b>HL CAR AUTO CENTER</b>", ParagraphStyle("Emp", fontSize=12, textColor=CINZA_ESCURO, fontName="Helvetica-Bold"))],
        [Paragraph("CNPJ: 61.782.333/0001-04", estilo_valor)],
        [Paragraph("Tel: (94) 99663-3585  |  Parauapebas - PA", estilo_valor)],
        [Paragraph("edivan.resende1@gmail.com", estilo_valor)],
    ]

    tabela_cab = Table(
        [[logo_img, cab_direita]],
        colWidths=[3 * cm, 15.5 * cm],
    )
    tabela_cab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (1, 0), (1, 0), 10),
    ]))
    elementos.append(tabela_cab)

    elementos.append(Spacer(1, 0.25 * cm))
    elementos.append(HRFlowable(width="100%", thickness=2, color=LARANJA, spaceBefore=2, spaceAfter=6))

    elementos.append(Paragraph("ORDEM DE SERVIÇO", estilo_titulo))
    elementos.append(Paragraph(f"Nº {ordem.numero or ordem.id}  —  {ordem.status or ''}", estilo_subtitulo))

    # ==========================================================
    # DADOS OS / CLIENTE / VEÍCULO
    # ==========================================================
    if ordem.data_abertura:
        data_local = ordem.data_abertura - timedelta(hours=3)
        data_str = data_local.strftime("%d/%m/%Y %H:%M")
    else:
        data_str = "-"

    cliente_nome = ordem.cliente.nome if ordem.cliente else "-"
    cliente_tel = getattr(ordem.cliente, "telefone", None) or getattr(ordem.cliente, "whatsapp", None) or "-"
    placa = ordem.veiculo.placa if ordem.veiculo else "-"
    veiculo_txt = ""
    if ordem.veiculo:
        veiculo_txt = f"{ordem.veiculo.marca or ''} {ordem.veiculo.modelo or ''}".strip() or "-"

    info_data = [
        [
            Paragraph("<b>Data</b>", estilo_label),
            Paragraph(data_str, estilo_valor),
            Paragraph("<b>KM</b>", estilo_label),
            Paragraph(str(ordem.km or "-"), estilo_valor),
        ],
        [
            Paragraph("<b>Cliente</b>", estilo_label),
            Paragraph(cliente_nome, estilo_valor),
            Paragraph("<b>Telefone</b>", estilo_label),
            Paragraph(str(cliente_tel), estilo_valor),
        ],
        [
            Paragraph("<b>Veículo</b>", estilo_label),
            Paragraph(veiculo_txt, estilo_valor),
            Paragraph("<b>Placa</b>", estilo_label),
            Paragraph(placa, estilo_valor),
        ],
        [
            Paragraph("<b>Mecânico</b>", estilo_label),
            Paragraph(ordem.mecanico or "-", estilo_valor),
            Paragraph("", estilo_label),
            Paragraph("", estilo_valor),
        ],
    ]

    tabela_info = Table(info_data, colWidths=[2.5 * cm, 7 * cm, 2.5 * cm, 6 * cm])
    tabela_info.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, CINZA_BORDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, CINZA_BORDA),
        ("BACKGROUND", (0, 0), (0, -1), CINZA_CLARO),
        ("BACKGROUND", (2, 0), (2, -1), CINZA_CLARO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabela_info)
    elementos.append(Spacer(1, 0.45 * cm))

    # ==========================================================
    # DEFEITO / DIAGNÓSTICO / EXECUTADOS
    # ==========================================================
    def bloco_texto(titulo, texto):
        cab = Table(
            [[Paragraph(titulo, estilo_secao)]],
            colWidths=[18 * cm],
        )
        cab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LARANJA),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        corpo = Table(
            [[Paragraph(texto or "-", estilo_normal)]],
            colWidths=[18 * cm],
        )
        corpo.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, CINZA_BORDA),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return [cab, corpo, Spacer(1, 0.35 * cm)]

    elementos.extend(bloco_texto("DEFEITO RELATADO", ordem.defeito_relatado))
    elementos.extend(bloco_texto("DIAGNÓSTICO", ordem.diagnostico))
    elementos.extend(bloco_texto("SERVIÇOS EXECUTADOS", ordem.servico_executado))

    # ==========================================================
    # SERVIÇOS
    # ==========================================================
    servicos_linhas = [[
        Paragraph("<b>Nº</b>", estilo_label),
        Paragraph("<b>Descrição do Serviço</b>", estilo_label),
        Paragraph("<b>Mecânico</b>", estilo_label),
        Paragraph("<b>Valor</b>", estilo_label),
    ]]

    total_servicos = 0.0
    try:
        itens_mec = list(getattr(ordem, "mecanicos_os", []) or [])
    except Exception:
        itens_mec = []

    if itens_mec:
        for i, item in enumerate(itens_mec, 1):
            nome_mec = ""
            try:
                nome_mec = item.mecanico.nome if item.mecanico else ""
            except Exception:
                nome_mec = ""
            desc = (getattr(item, "descricao_servico", None) or "").strip() or "Serviço"
            valor = float(getattr(item, "valor_negociado", 0) or 0)
            total_servicos += valor
            servicos_linhas.append([
                str(i),
                Paragraph(desc, estilo_normal),
                Paragraph(nome_mec or "-", estilo_normal),
                _money(valor),
            ])
    else:
        total_servicos = float(ordem.valor_servicos or 0)
        servicos_linhas.append([
            "1",
            Paragraph(ordem.servico_executado or "Serviços gerais", estilo_normal),
            Paragraph(ordem.mecanico or "-", estilo_normal),
            _money(total_servicos),
        ])

    cab_serv = Table(
        [[Paragraph("SERVIÇOS", estilo_secao)]],
        colWidths=[18 * cm],
    )
    cab_serv.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LARANJA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.append(cab_serv)

    tabela_serv = Table(servicos_linhas, colWidths=[1.2 * cm, 8.5 * cm, 4.8 * cm, 3.5 * cm])
    tabela_serv.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, CINZA_BORDA),
        ("BACKGROUND", (0, 0), (-1, 0), CINZA_CLARO),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabela_serv)
    elementos.append(Spacer(1, 0.4 * cm))

    # ==========================================================
    # PEÇAS (detalhadas)
    # ==========================================================
    cab_pec = Table(
        [[Paragraph("PEÇAS / PRODUTOS", estilo_secao)]],
        colWidths=[18 * cm],
    )
    cab_pec.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LARANJA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.append(cab_pec)

    pecas_linhas = [[
        Paragraph("<b>Nº</b>", estilo_label),
        Paragraph("<b>Descrição</b>", estilo_label),
        Paragraph("<b>Qtd</b>", estilo_label),
        Paragraph("<b>Valor</b>", estilo_label),
    ]]

    valor_pecas = 0.0
    try:
        itens_peca = list(getattr(ordem, "itens", []) or [])
    except Exception:
        itens_peca = []

    if itens_peca:
        for i, it in enumerate(itens_peca, 1):
            desc = (getattr(it, "descricao", None) or "Peça").strip()
            qtd = float(getattr(it, "quantidade", 0) or 0)
            vt = float(getattr(it, "valor_total", 0) or 0)
            if vt == 0:
                vu = float(getattr(it, "valor_unitario", 0) or 0)
                vt = qtd * vu
            valor_pecas += vt
            pecas_linhas.append([
                str(i),
                Paragraph(desc, estilo_normal),
                f"{qtd:g}",
                _money(vt),
            ])
    else:
        valor_pecas = float(ordem.valor_produtos or 0)
        if valor_pecas > 0:
            pecas_linhas.append([
                "1",
                Paragraph("Peças e produtos utilizados", estilo_normal),
                "—",
                _money(valor_pecas),
            ])
        else:
            pecas_linhas.append([
                "—",
                Paragraph("Nenhuma peça registrada", estilo_normal),
                "—",
                _money(0),
            ])

    # Nº | Descrição | Qtd | Valor  — Qtd mais estreita e centralizada
    tabela_pec = Table(pecas_linhas, colWidths=[1.2 * cm, 11.8 * cm, 1.8 * cm, 3.2 * cm])
    tabela_pec.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, CINZA_BORDA),
        ("BACKGROUND", (0, 0), (-1, 0), CINZA_CLARO),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabela_pec)
    elementos.append(Spacer(1, 0.45 * cm))

    # ==========================================================
    # TOTAIS
    # ==========================================================
    desconto = float(ordem.desconto or 0)
    total = float(ordem.valor_total or 0)

    totais = [
        ["Subtotal Serviços", _money(total_servicos or ordem.valor_servicos)],
        ["Subtotal Peças", _money(valor_pecas)],
        ["Desconto", _money(desconto)],
        ["TOTAL", _money(total)],
    ]

    tabela_tot = Table(totais, colWidths=[12 * cm, 6 * cm])
    tabela_tot.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, CINZA_BORDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, CINZA_BORDA),
        ("BACKGROUND", (0, 3), (-1, 3), LARANJA),
        ("TEXTCOLOR", (0, 3), (-1, 3), colors.white),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (0, 2), "Helvetica"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.append(tabela_tot)
    elementos.append(Spacer(1, 0.7 * cm))

    # ==========================================================
    # QR + ASSINATURAS
    # ==========================================================
    qr = qrcode.make(f"HLCar OS {ordem.numero or ordem.id}")
    qr_path = os.path.join(current_app.root_path, "static", "qr_temp.png")
    qr.save(qr_path)

    qr_img = Image(qr_path, width=2.4 * cm, height=2.4 * cm) if os.path.exists(qr_path) else Spacer(1, 2.4 * cm)

    ass = Table(
        [
            [qr_img, "_______________________________", "_______________________________"],
            ["", "Cliente", "HL Car Auto Center"],
        ],
        colWidths=[3.5 * cm, 7.2 * cm, 7.2 * cm],
    )
    ass.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
        ("FONTSIZE", (1, 1), (-1, 1), 8),
        ("TEXTCOLOR", (1, 1), (-1, 1), colors.HexColor("#6B7280")),
        ("TOPPADDING", (1, 0), (-1, 0), 28),
    ]))
    elementos.append(ass)

    elementos.append(Spacer(1, 0.5 * cm))
    elementos.append(HRFlowable(width="100%", thickness=1, color=CINZA_BORDA, spaceBefore=4, spaceAfter=4))
    elementos.append(Paragraph(
        "Documento gerado pelo sistema HLCarERP — HL Car Auto Center",
        ParagraphStyle("Rodape", fontSize=7, textColor=colors.HexColor("#9CA3AF"), alignment=TA_CENTER),
    ))

    pdf.build(elementos)
    buffer.seek(0)
    return buffer