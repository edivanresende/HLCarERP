from io import BytesIO
import os

import qrcode

from flask import current_app

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image
)


def gerar_pdf_ordem(ordem):

    buffer = BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=(21 * cm, 29.7 * cm),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm
    )

    estilos = getSampleStyleSheet()

    titulo = estilos["Heading1"]
    titulo.alignment = TA_CENTER

    subtitulo = estilos["Heading2"]
    subtitulo.alignment = TA_CENTER

    normal = estilos["BodyText"]

    elementos = []

    # ==========================================================
    # LOGO
    # ==========================================================

    logo = os.path.join(
        current_app.root_path,
        "static",
        "logo_hlcar.png"
    )

    if os.path.exists(logo):
        elementos.append(
            Image(
                logo,
                width=5.5 * cm,
                height=5.5 * cm
            )
        )

    elementos.append(
        Paragraph(
            "<b>HL CAR AUTO CENTER</b>",
            titulo
        )
    )

    elementos.append(
        Paragraph(
            "ORDEM DE SERVIÇO",
            subtitulo
        )
    )

    elementos.append(
        Spacer(1, 0.4 * cm)
    )

    # ==========================================================
    # DADOS DA EMPRESA
    # ==========================================================

    empresa = [

        ["CNPJ", "61.782.333/0001-04"],

        ["Telefone", "(94) 99663-3585"],

        ["Cidade", "Parauapebas - PA"],

        ["E-mail", "edivan.resende1@gmail.com"]

    ]

    tabela_empresa = Table(
        empresa,
        colWidths=[3 * cm, 14 * cm]
    )

    tabela_empresa.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
        ])
    )

    elementos.append(tabela_empresa)

    elementos.append(
        Spacer(1, 0.6 * cm)
    )

    # ==========================================================
    # DADOS DA ORDEM DE SERVIÇO
    # ==========================================================

    dados_os = [

        ["Número", str(ordem.numero or ordem.id)],

        ["Status", ordem.status or ""],

        [
            "Data",
            ordem.data_abertura.strftime("%d/%m/%Y %H:%M")
            if ordem.data_abertura else ""
        ],

        [
            "Cliente",
            ordem.cliente.nome if ordem.cliente else ""
        ],

        [
            "Veículo",
            f"{ordem.veiculo.marca} {ordem.veiculo.modelo}"
            if ordem.veiculo else ""
        ],

        [
            "Placa",
            ordem.veiculo.placa if ordem.veiculo else ""
        ],

        [
            "KM",
            str(ordem.km or "")
        ],

        [
            "Mecânico",
            ordem.mecanico or ""
        ]

    ]

    tabela_os = Table(
        dados_os,
        colWidths=[4 * cm, 13 * cm]
    )

    tabela_os.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EFEFEF")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
        ])
    )

    elementos.append(tabela_os)
    elementos.append(
        Spacer(1, 0.6 * cm)
    )

    # ==========================================================
    # DEFEITO RELATADO
    # ==========================================================

    elementos.append(
        Paragraph(
            "<b>DEFEITO RELATADO</b>",
            normal
        )
    )

    elementos.append(
        Paragraph(
            ordem.defeito_relatado or "-",
            normal
        )
    )

    elementos.append(
        Spacer(1, 0.4 * cm)
    )

    # ==========================================================
    # DIAGNÓSTICO
    # ==========================================================

    elementos.append(
        Paragraph(
            "<b>DIAGNÓSTICO</b>",
            normal
        )
    )

    elementos.append(
        Paragraph(
            ordem.diagnostico or "-",
            normal
        )
    )

    elementos.append(
        Spacer(1, 0.4 * cm)
    )

    # ==========================================================
    # SERVIÇOS EXECUTADOS
    # ==========================================================

    elementos.append(
        Paragraph(
            "<b>SERVIÇOS EXECUTADOS</b>",
            normal
        )
    )

    elementos.append(
        Paragraph(
            ordem.servico_executado or "-",
            normal
        )
    )

    elementos.append(
        Spacer(1, 0.7 * cm)
    )

    # ==========================================================
    # VALORES
    # ==========================================================

    valores = [

        [
            "Serviços",
            f"R$ {ordem.valor_servicos:.2f}"
        ],

        [
            "Peças",
            f"R$ {ordem.valor_pecas:.2f}"
        ],

        [
            "Desconto",
            f"R$ {ordem.desconto:.2f}"
        ],

        [
            "TOTAL",
            f"R$ {ordem.valor_total:.2f}"
        ]

    ]

    tabela_valores = Table(
        valores,
        colWidths=[8 * cm, 5 * cm]
    )

    tabela_valores.setStyle(
        TableStyle([

            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),

            ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#FF8C00")),

            ("TEXTCOLOR", (0, 3), (-1, 3), colors.white),

            ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),

            ("ALIGN", (1, 0), (1, -1), "RIGHT"),

            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)

        ])
    )

    elementos.append(tabela_valores)

    elementos.append(
        Spacer(1, 1.5 * cm)
    )
        # ==========================================================
    # QR CODE
    # ==========================================================

    qr = qrcode.make(
        f"OS {ordem.numero or ordem.id}"
    )

    qr_path = os.path.join(
        current_app.root_path,
        "static",
        "qr_temp.png"
    )

    qr.save(qr_path)

    if os.path.exists(qr_path):
        elementos.append(
            Image(
                qr_path,
                width=3 * cm,
                height=3 * cm
            )
        )

    elementos.append(
        Spacer(1, 0.8 * cm)
    )

    # ==========================================================
    # ASSINATURAS
    # ==========================================================

    assinatura = Table(
        [
            [
                "______________________________",
                "______________________________"
            ],
            [
                "Cliente",
                "HL Car Auto Center"
            ]
        ],
        colWidths=[8 * cm, 8 * cm]
    )

    assinatura.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 8)
        ])
    )

    elementos.append(assinatura)

    # ==========================================================
    # GERAÇÃO DO PDF
    # ==========================================================

    pdf.build(elementos)

    buffer.seek(0)

    return buffer