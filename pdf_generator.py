# Arquivo: pdf_generator.py

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

# ====================================================================
# ==== FUNÇÃO AUXILIAR PARA CABEÇALHO E RODAPÉ ====
# ====================================================================
def _header_footer(canvas, doc):
    """
    Desenha o cabeçalho e o rodapé em cada página do PDF.
    """
    # Salva o estado do canvas
    canvas.saveState()
    styles = getSampleStyleSheet()
    
    # --- Cabeçalho ---
    header = Paragraph("SGA - Relatório de Auditoria", styles['Normal'])
    w, h = header.wrap(doc.width, doc.topMargin)
    header.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - h)

    # --- Rodapé ---
    footer = Paragraph(f"Página {doc.page}", styles['Normal'])
    w, h = footer.wrap(doc.width, doc.bottomMargin)
    footer.drawOn(canvas, doc.leftMargin, h)

    # Restaura o estado do canvas
    canvas.restoreState()


# ====================================================================
# ==== FUNÇÃO PRINCIPAL DE GERAÇÃO DO PDF ====
# ====================================================================
def gerar_relatorio_pdf(dados_do_caso, lista_de_atividades):
    """
    Gera um relatório de auditoria completo usando Platypus.
    """
    buffer = BytesIO()
    
    # 1. CRIA O DOCUMENTO (SimpleDocTemplate lida com margens e quebras de página)
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    
    # 2. CRIA A "HISTÓRIA" (story) - uma lista de elementos para desenhar
    story = []
    styles = getSampleStyleSheet()
    
    # --- TÍTULO ---
    style_titulo = ParagraphStyle(name='Titulo', fontSize=18, leading=22, alignment=1, spaceAfter=20)
    story.append(Paragraph(dados_do_caso.titulo, style_titulo))
    
    # --- SUMÁRIO DO RELATÓRIO ---
    style_sumario = ParagraphStyle(name='Sumario', fontSize=10, leading=14, spaceAfter=5)
    story.append(Paragraph(f"<b>Nº Relatório:</b> {dados_do_caso.numero_relatorio}", style_sumario))
    story.append(Paragraph(f"<b>Filial:</b> {dados_do_caso.filial.nome if dados_do_caso.filial else 'N/A'}", style_sumario))
    story.append(Paragraph(f"<b>Tipo/Categoria:</b> {dados_do_caso.categoria.nome if dados_do_caso.categoria else 'N/A'}", style_sumario))
    story.append(Paragraph(f"<b>Data de Início:</b> {dados_do_caso.data_inicio}", style_sumario))
    story.append(Paragraph(f"<b>Status:</b> {dados_do_caso.status}", style_sumario))
    
    # Adiciona um espaço antes da tabela
    story.append(Spacer(1, 0.5*cm))

    # --- TABELA DE ATIVIDADES ---
    # 3. Prepara os dados para a tabela (lista de listas)
    dados_tabela = [
        ['Descrição da Atividade', 'Observação / Resumo', 'Situação']
    ]
    
    for at in lista_de_atividades:
        # Usamos Paragraphs dentro das células para que o texto longo quebre a linha automaticamente
        desc = Paragraph(at.atividade_desc, styles['Normal'])
        obs = Paragraph(at.observacao_resumo or '', styles['Normal'])
        
        dados_tabela.append([desc, obs, at.situacao])
        
    # 4. Cria o objeto Tabela, definindo a largura das colunas
    tabela = Table(dados_tabela, colWidths=[6*cm, 8*cm, 3*cm])
    
    # 5. Adiciona o Estilo da Tabela (cores, linhas, etc.)
    estilo_tabela = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#212529')), # Cor de fundo do cabeçalho
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),          # Cor do texto do cabeçalho
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),                      # Alinhamento central
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),                     # Alinhamento vertical
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),             # Fonte do cabeçalho em negrito
        ('BOTTOMPADDING', (0,0), (-1,0), 12),                     # Espaçamento do cabeçalho
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),            # Cor de fundo do corpo
        ('GRID', (0,0), (-1,-1), 1, colors.black)                 # Desenha as linhas da grelha
    ])
    tabela.setStyle(estilo_tabela)
    
    story.append(tabela)

    # 6. CONSTRÓI O PDF
    # O 'onFirstPage' e 'onLaterPages' chamam a nossa função para desenhar cabeçalho/rodapé
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    
    buffer.seek(0)
    return buffer