# Arquivo: pdf_generator.py

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

# ====================================================================
# ==== CONFIGURAÇÕES DE LAYOUT ====
# ====================================================================
MARGEM_ESQ = 5 * mm
MARGEM_DIR = 5 * mm
MARGEM_SUP = 10 * mm
MARGEM_INF = 10 * mm

LARGURA_UTIL = A4[0] - MARGEM_ESQ - MARGEM_DIR
ALTURA_PAGINA = A4[1]

_dados_caso_atual = None

# ====================================================================
# ==== CABEÇALHO CORPORATIVO ====
# ====================================================================
def _header_footer(canvas, doc):
    global _dados_caso_atual
    if not _dados_caso_atual: return

    canvas.saveState()
    
    top_y = ALTURA_PAGINA - MARGEM_SUP
    header_height = 12 * mm
    
    # Caixa do cabeçalho
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.5)
    canvas.rect(MARGEM_ESQ, top_y - header_height, LARGURA_UTIL, header_height)
    
    # Título Central
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawCentredString(A4[0]/2, top_y - 8*mm, "RELATÓRIO DE AUDITORIA")
    
    # Subtítulo (Direita)
    canvas.setFont("Helvetica", 9)
    info_text = f"{_dados_caso_atual.numero_relatorio_display}"
    canvas.drawRightString(MARGEM_ESQ + LARGURA_UTIL - 2*mm, top_y - 8*mm, info_text)

    # Rodapé
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - MARGEM_DIR, MARGEM_INF/2, f"Página {doc.page}")
    
    canvas.restoreState()

# ====================================================================
# ==== FUNÇÃO PRINCIPAL ====
# ====================================================================
def gerar_relatorio_pdf(dados_do_caso, lista_de_atividades):
    global _dados_caso_atual
    _dados_caso_atual = dados_do_caso

    buffer = BytesIO()
    
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                            leftMargin=MARGEM_ESQ, rightMargin=MARGEM_DIR,
                            topMargin=MARGEM_SUP + 15*mm, bottomMargin=MARGEM_INF)
    
    story = []
    styles = getSampleStyleSheet()
    
    # --- INTRODUÇÃO ---
    style_intro = ParagraphStyle(name='Intro', parent=styles['Normal'], fontSize=9, leading=11, spaceAfter=10)
    texto_intro = f"""
    <b>Unidade Auditada:</b> {dados_do_caso.filial.nome if dados_do_caso.filial else 'N/A'}<br/>
    <b>Tipo de Auditoria:</b> {dados_do_caso.categoria.nome if dados_do_caso.categoria else 'N/A'}<br/>
    <b>Período Geral:</b> {dados_do_caso.data_inicio} até {dados_do_caso.data_final or 'Presente'}<br/>
    """
    story.append(Paragraph(texto_intro, style_intro))

    story.append(Paragraph("RESUMO DOS TESTES REALIZADOS", ParagraphStyle(name='TitTab', fontSize=10, fontName='Helvetica-Bold', spaceAfter=5)))

    # -----------------------------------------------------------
    # DEFINIÇÃO DA TABELA
    # -----------------------------------------------------------
    col_widths = [8*mm, 35*mm, 40*mm, 22*mm, 22*mm, 23*mm, 8*mm, 42*mm]
    
    # Cabeçalhos com Paragraph para permitir quebra de linha se necessário
    style_header = ParagraphStyle(
        name='HeaderTable', 
        parent=styles['Normal'], 
        fontSize=7, 
        leading=8, 
        alignment=TA_CENTER, 
        textColor=colors.whitesmoke,
        fontName='Helvetica-Bold'
    )

    headers = [
        Paragraph('Nº', style_header),
        Paragraph('Atividade', style_header),
        Paragraph('Testes Realizados', style_header),
        Paragraph('Extensão dos Exames', style_header),
        Paragraph('Critério de Amostragem', style_header),
        Paragraph('Período / Situação em', style_header),
        Paragraph('Sit.', style_header),
        Paragraph('Observação / Resumo', style_header)
    ]
    
    data_table = [headers]

    # --- ESTILOS DE CÉLULA (AQUI ESTÁ A CONFIGURAÇÃO DE ALINHAMENTO) ---
    
    # 1. Estilo Esquerda (Para textos gerais)
    style_cell_left = ParagraphStyle(
        name='CellLeft', 
        parent=styles['Normal'], 
        fontSize=7, 
        leading=8, 
        alignment=TA_LEFT # Horizontal Esquerda
    )
    
    # 2. Estilo Centro (Para Nº, Datas e Símbolos)
    style_cell_center = ParagraphStyle(
        name='CellCenter', 
        parent=styles['Normal'], 
        fontSize=7, 
        leading=8, 
        alignment=TA_CENTER # Horizontal Centro
    )
    
    # 3. Estilo Símbolo (Check/X)
    style_symbol = ParagraphStyle(
        name='Symbol', 
        parent=styles['Normal'], 
        fontSize=12, 
        leading=12, 
        alignment=TA_CENTER, 
        fontName='ZapfDingbats'
    )

    for i, at in enumerate(lista_de_atividades, 1):
        
        # Lógica de Símbolos
        status = str(at.situacao).upper().strip() if at.situacao else ""
        
        if "SEM IRREGULARIDADES" in status:
            simbolo = "4" # Check (V)
            cor_simbolo = colors.green
        elif "RESSALVA" in status:
            simbolo = "4" # Check (V) - Laranja
            cor_simbolo = colors.orange
        elif "IRREGULARIDADE" in status or "FRAUDE" in status:
            simbolo = "7" # X - Vermelho
            cor_simbolo = colors.red
        else:
            simbolo = "" 
            cor_simbolo = colors.black

        para_simbolo = Paragraph(f'<font color="{cor_simbolo}">{simbolo}</font>', style_symbol)

        row = [
            # Agora usamos Paragraph também no número para garantir a centralização
            Paragraph(str(i), style_cell_center), 
            
            # Colunas de Texto -> Alinhadas à Esquerda
            Paragraph(at.atividade_desc, style_cell_left),
            Paragraph(at.testes_realizados or '-', style_cell_left),
            Paragraph(at.extensao_exames or '-', style_cell_left),
            Paragraph(at.criterio_amostragem or '-', style_cell_left),
            
            # Coluna de Período -> Centralizada
            Paragraph(f"{at.periodo_inicio or ''}<br/>a<br/>{at.periodo_fim or ''}", style_cell_center),
            
            # Coluna Símbolo -> Centralizada
            para_simbolo,
            
            # Coluna Observação -> Alinhada à Esquerda
            Paragraph(at.observacao_resumo or '-', style_cell_left)
        ]
        data_table.append(row)

    t = Table(data_table, colWidths=col_widths, repeatRows=1)

    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        
        # ALTERAÇÃO PRINCIPAL AQUI: MUDANÇA PARA 'MIDDLE'
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # Centraliza verticalmente TODO o conteúdo
        
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#212529')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        
        # O corpo da tabela continua a ter fundo branco
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        
        # Padding
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))

    story.append(t)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    _dados_caso_atual = None
    return buffer