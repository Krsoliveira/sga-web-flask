# Arquivo: pdf_generator.py

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
# IMPORTANTE: Importar o alinhamento TA_LEFT
from reportlab.lib.enums import TA_LEFT 
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
import datetime

# ====================================================================
# ==== CABEÇALHO E RODAPÉ (Sem alterações) ====
# ====================================================================
_dados_caso_atual = None

def _header_footer(canvas, doc):
    global _dados_caso_atual 
    if not _dados_caso_atual: return

    canvas.saveState()
    styles = getSampleStyleSheet()
    style_header = ParagraphStyle(name='HeaderStyle', alignment=1, fontSize=9)
    header_text = f"Relatório: {_dados_caso_atual.numero_relatorio_display}"
    header = Paragraph(header_text, style_header)
    w, h = header.wrap(doc.width, doc.topMargin)
    header.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - h - 0.5*cm) 
    canvas.line(doc.leftMargin, doc.height + doc.topMargin - h - 0.6*cm, doc.leftMargin + doc.width, doc.height + doc.topMargin - h - 0.6*cm)

    style_footer = ParagraphStyle(name='FooterStyle', alignment=2, fontSize=8)
    footer = Paragraph(f"Página {doc.page}", style_footer)
    w, h = footer.wrap(doc.width, doc.bottomMargin)
    footer.drawOn(canvas, doc.leftMargin, 0.5*cm)

    canvas.restoreState()

# ====================================================================
# ==== FUNÇÃO PRINCIPAL (COM ESTILOS REFINADOS) ====
# ====================================================================
def gerar_relatorio_pdf(dados_do_caso, lista_de_atividades):
    global _dados_caso_atual
    _dados_caso_atual = dados_do_caso

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                            rightMargin=1.5*cm, leftMargin=1.5*cm, 
                            topMargin=3*cm, bottomMargin=1.5*cm)
    
    story = []
    styles = getSampleStyleSheet()
    
    # --- PÁGINA DE ROSTO (Sem alterações) ---
    style_titulo_rosto = ParagraphStyle(name='TituloRosto', fontSize=24, leading=28, alignment=1, spaceAfter=1*cm)
    story.append(Paragraph(dados_do_caso.titulo, style_titulo_rosto))
    style_sumario_rosto = ParagraphStyle(name='SumarioRosto', fontSize=12, leading=16, spaceAfter=0.5*cm, alignment=1)
    story.append(Paragraph(f"<b>Filial:</b> {dados_do_caso.filial.nome if dados_do_caso.filial else 'N/A'}", style_sumario_rosto))
    story.append(Paragraph(f"<b>Categoria:</b> {dados_do_caso.categoria.nome if dados_do_caso.categoria else 'N/A'}", style_sumario_rosto))
    story.append(Paragraph(f"<b>Período da Auditoria:</b> {dados_do_caso.data_inicio} a {dados_do_caso.data_final or 'Presente'}", style_sumario_rosto))
    story.append(Paragraph(f"<b>Status:</b> {dados_do_caso.status}", style_sumario_rosto))
    story.append(PageBreak())

    # --- TABELA DETALHADA DE ATIVIDADES ---
    story.append(Paragraph("Detalhamento das Atividades", styles['h2']))
    story.append(Spacer(1, 0.5*cm))

    cabecalhos = ['Atividade', 'Período Análise', 'Observação/Resumo', 'Não Conformidade', 'Recomendação', 'Situação']
    larguras_colunas = [4*cm, 2.5*cm, 5*cm, 3*cm, 3*cm, 1.5*cm] 

    dados_tabela = [cabecalhos]
    
    # ================================================================
    # ==== ALTERAÇÃO 1: NOVO ESTILO PARA O CORPO DA TABELA ====
    # ================================================================
    style_corpo_tabela = ParagraphStyle(
        name='CorpoTabela',
        parent=styles['Normal'],   # Herda de Normal
        fontSize=9,
        leading=12,               # Aumenta um pouco o espaçamento entre linhas
        alignment=TA_LEFT,        # Alinha o texto à esquerda
    )
    # ================================================================

    for at in lista_de_atividades:
        # Usa o novo estilo 'style_corpo_tabela' para todas as células de texto
        desc = Paragraph(at.atividade_desc, style_corpo_tabela)
        periodo = Paragraph(f"{at.periodo_inicio or '-'} a {at.periodo_fim or '-'}", style_corpo_tabela)
        obs = Paragraph(at.observacao_resumo or '', style_corpo_tabela)
        nc = Paragraph(at.nao_conformidade or '', style_corpo_tabela)
        rec = Paragraph(at.recomendacao or '', style_corpo_tabela)
        sit = Paragraph(at.situacao or '', style_corpo_tabela) # Pode querer centralizar este depois
        
        dados_tabela.append([desc, periodo, obs, nc, rec, sit])
        
    tabela = Table(dados_tabela, colWidths=larguras_colunas)
    
    # ================================================================
    # ==== ALTERAÇÃO 2: ESTILO DA TABELA REFINADO ====
    # ================================================================
    estilo_tabela = TableStyle([
        # --- Estilos do Cabeçalho ---
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#212529')), 
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),          
        ('ALIGN', (0,0), (-1,0), 'CENTER'), # Cabeçalho centralizado                     
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),             
        ('BOTTOMPADDING', (0,0), (-1,0), 10),                     
        
        # --- Estilos do Corpo ---
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#FFFFFF')), 
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#343a40')), # Cor do texto do corpo
        # ('ALIGN', (0,1), (-1,-1), 'LEFT'), # Agora controlado pelo ParagraphStyle
        ('VALIGN', (0,0), (-1,-1), 'TOP'),  # Alinha TUDO no topo da célula (importante!)
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'), # Fonte normal para o corpo
        ('GRID', (0,0), (-1,-1), 1, colors.darkgrey), 
        
        # --- Padding aumentado para todas as células ---
        ('LEFTPADDING', (0,0), (-1,-1), 6), 
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ])
    # ================================================================
    tabela.setStyle(estilo_tabela)
    
    story.append(tabela)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    
    _dados_caso_atual = None
    buffer.seek(0)
    return buffer