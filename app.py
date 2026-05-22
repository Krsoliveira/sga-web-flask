import os
from datetime import date, datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g, send_from_directory, make_response
from functools import wraps
import database as db
from werkzeug.utils import secure_filename

# Tenta importar o módulo de PDF (caso esteja na mesma pasta)
try:
    import pdf_generator
except ImportError:
    print("AVISO: O módulo 'pdf_generator.py' não foi encontrado. A geração de PDF não funcionará.")
    pdf_generator = None

# Carrega variáveis de ambiente
load_dotenv()

# Inicializa o Flask
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# === CONFIGURAÇÃO DE SEGURANÇA ===
# Chave secreta para assinar os cookies de sessão.
app.secret_key = os.getenv('SECRET_KEY', 'SGA_CHAVE_MESTRA_FINAL_2026_V5')
app.config['SESSION_COOKIE_NAME'] = 'sga_session_v5_secure'

# Listas globais
LISTA_SITUACAO_HARDCODED = [
    "SEM IRREGULARIDADES", 
    "SEM IRREGULARIDADES COM RESSALVA",
    "IRREGULARIDADE LEVE", 
    "IRREGULARIDADE GRAVE", 
    "FRAUDE"
]    

LISTA_ATIVIDADES_SISTEMA = [
    "Contagem de Numerário (Caixa)",
    "Conferência de Estoque",
    "Auditoria de Processos",
    "Verificação de Despesas",
    "Análise de Contratos",
    "Checklist de Segurança",
    "Conferência de Ponto/RH",
    "Outros"
]
# Garante que a pasta de uploads existe
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# =======================================================
# ==== CARREGADOR GLOBAL DE USUÁRIO (Blindado) ====
# =======================================================
@app.before_request
def carregar_usuario_logado():
    """
    Verifica se existe um usuário na sessão antes de cada requisição.
    Evita erros de 'NoneType' se o banco cair ou a sessão expirar.
    """
    g.user = None
    user_id = session.get('user_id')
    
    if user_id:
        try:
            with db.get_db() as sess:
                usuario = db.buscar_usuario_por_id(sess, user_id)
                if usuario:
                    g.user = usuario
                else:
                    # Se o ID existe na sessão mas não no banco, limpa a sessão
                    session.clear()
        except Exception as e:
            print(f"Erro Crítico no Banco de Dados: {e}")
            g.user = None

@app.context_processor
def inject_user():
    """Disponibiliza a variável 'usuario' para todos os templates HTML"""
    return dict(usuario=getattr(g, 'user', None))

# =============================================
# ==== DECORADORES DE PROTEÇÃO DE ROTA ====
# =============================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """Protege rotas baseadas no cargo (Role) do usuário"""
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user is None or g.user.role not in roles:
                flash('Você não tem permissão para acessar esta área.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# =============================================
# ==== ROTAS PRINCIPAIS ====
# =============================================

@app.route('/')
def home():
    if g.user:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # NOTA: Removemos o redirecionamento automático 'if g.user' 
    # para evitar o loop de tela branca caso o navegador cacheie a sessão errada.
    
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        senha = request.form.get('senha')
        
        try:
            with db.get_db() as sess:
                dados_usuario = db.verificar_login(sess, codigo, senha)
            
            if dados_usuario:
                # Login Sucesso: Renova a sessão
                session.clear()
                session['user_id'] = dados_usuario['id']
                return redirect(url_for('dashboard'))
            else:
                flash('Código ou Senha incorretos.', 'danger')
        except Exception as e:
            flash(f'Erro de conexão: {str(e)}', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema com segurança.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Tela principal que lista os casos e métricas"""
    try:
        with db.get_db() as sess:
            lista_de_casos = db.buscar_casos(sess) or []
            todas_categorias = db.buscar_todas_categorias(sess) or []
            todas_filiais = db.buscar_todas_filiais(sess) or []
            
        return render_template('dashboard.html', 
                               casos=lista_de_casos, 
                               categorias=todas_categorias, 
                               filiais=todas_filiais)
    except Exception as e:
        print(f"Erro ao carregar Dashboard: {e}")
        return "Erro interno no servidor. Verifique o log."
    
# =============================================
# ==== RELATÓRIOS E WORKFLOW ====
# =============================================

@app.route('/relatorio/novo/categoria/<int:categoria_id>', methods=['POST'])
@login_required
def novo_relatorio_por_categoria(categoria_id):
    try:
        filial_id = request.form.get('filial_id')
        if not filial_id:
            flash('Por favor, selecione uma filial antes de criar.', 'warning')
            return redirect(url_for('dashboard'))

        with db.get_db() as sess:
            # Cria o caso e copia automaticamente os POPs daquela categoria
            novo_id = db.criar_caso_com_atividades_padrao(
                sess, 
                categoria_id=categoria_id, 
                filial_id=filial_id, 
                realizado_por_id=g.user.id
            )
        
        if novo_id:
            flash('Relatório iniciado com sucesso!', 'success')
            return redirect(url_for('ver_relatorio', id_caso=novo_id))
        else:
            flash('Erro ao criar registro no banco.', 'danger')
            return redirect(url_for('dashboard'))
            
    except Exception as e:
        print(f"ERRO CRÍTICO: {e}")
        flash('Erro interno ao criar relatório.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/relatorio/<int:id_caso>', methods=['GET'])
@login_required
def ver_relatorio(id_caso):
    with db.get_db() as sess:
        dados_caso = db.buscar_caso_por_id(sess, id_caso)
    
    if not dados_caso:
        flash('Relatório não encontrado ou excluído.', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('relatorio.html', 
                           caso=dados_caso, 
                           atividades=dados_caso.atividades, 
                           opcoes_situacao=LISTA_SITUACAO_HARDCODED,
                           opcoes_atividade=LISTA_ATIVIDADES_SISTEMA)

@app.route('/relatorio/<int:id_caso>/pdf')
@login_required
def gerar_pdf_relatorio(id_caso):
    if not pdf_generator:
        flash('O módulo de PDF não está instalado no servidor.', 'danger')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))

    try:
        with db.get_db() as sess:
            caso = db.buscar_caso_por_id(sess, id_caso)
        
        if not caso:
            return redirect(url_for('dashboard'))

        # Gera o PDF em memória
        pdf_buffer = pdf_generator.gerar_relatorio_pdf(caso, caso.atividades)
        
        # Prepara o download
        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        safe_filename = secure_filename(f'Relatorio_{caso.numero_relatorio_display}.pdf')
        response.headers['Content-Disposition'] = f'attachment; filename={safe_filename}'
        return response

    except Exception as e:
        print(f"ERRO PDF: {e}")
        flash('Erro ao gerar o arquivo PDF.', 'danger')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/anexar', methods=['POST'])
@login_required
def anexar_ficheiro(id_caso):
    file = request.files.get('anexo')
    if not file or file.filename == '':
        flash('Nenhum arquivo selecionado.', 'warning')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))

    if file:
        try:
            filename = secure_filename(file.filename)
            # Adiciona timestamp para evitar arquivos com mesmo nome
            secure_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], secure_name)
            
            file.save(path)
            
            with db.get_db() as sess:
                db.adicionar_anexo(sess, id_caso, filename, secure_name, path)
            flash('Anexo enviado com sucesso.', 'success')
        except Exception as e:
            flash(f'Erro ao salvar arquivo: {e}', 'danger')
            
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/uploads/<string:nome_seguro>')
@login_required
def download_anexo(nome_seguro):
    return send_from_directory(app.config['UPLOAD_FOLDER'], nome_seguro, as_attachment=True)

# === ROTAS DE FLUXO DE APROVAÇÃO ===

@app.route('/relatorio/<int:id_caso>/submeter', methods=['POST'])
@login_required
def submeter_relatorio(id_caso):
    with db.get_db() as sess:
        db.atualizar_relatorio(sess, id_caso, {'status': 'Pendente de Revisão'})
    flash('Relatório enviado para revisão do gerente.', 'success')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/aprovar', methods=['POST'])
@login_required
@role_required('Manager', 'Admin')
def aprovar_relatorio(id_caso):
    notas = request.form.get('notas_aprovacao', '')
    with db.get_db() as sess:
        db.atualizar_relatorio(sess, id_caso, {'status': 'Aprovado', 'notas_revisao': notas})
    flash('Relatório APROVADO com sucesso!', 'success')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/rejeitar', methods=['POST'])
@login_required
@role_required('Manager', 'Admin')
def rejeitar_relatorio(id_caso):
    notas = request.form.get('notas_revisao')
    if not notas:
        flash('É obrigatório justificar a rejeição.', 'danger')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))
    with db.get_db() as sess:
        db.atualizar_relatorio(sess, id_caso, {'status': 'Em Elaboração', 'notas_revisao': notas})
    flash('Relatório devolvido ao auditor para correções.', 'warning')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

# =============================================
# ==== ATIVIDADES E EDIÇÃO ====
# =============================================

@app.route('/relatorio/<int:id_caso>/adicionar_atividade', methods=['POST'])
@login_required
def adicionar_atividade(id_caso):
    dados = {
        'atividade_desc': request.form.get('atividade_desc'),
        'testes_realizados': request.form.get('testes_realizados'),
        'observacao_resumo': request.form.get('observacao_resumo'),
        'nao_conformidade': request.form.get('nao_conformidade'),
        'recomendacao': request.form.get('recomendacao'),
        'situacao': request.form.get('situacao'),
        'realizado_por_id': g.user.id,
        'data_registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'caso_id': id_caso,
        'periodo_inicio': request.form.get('periodo_inicio'), 
        'periodo_fim': request.form.get('periodo_fim'),        
        'extensao_exames': request.form.get('extensao_exames'),
        'criterio_amostragem': request.form.get('criterio_amostragem')
    }
    with db.get_db() as sess:
        db.salvar_atividade(sess, dados)
    flash('Atividade adicionada.', 'success')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/atividade/<int:id_atividade>/editar', methods=['GET', 'POST'])
@login_required
def editar_atividade(id_atividade):
    with db.get_db() as sess:
        atividade = db.buscar_atividade_por_id(sess, id_atividade)

        if not atividade:
            flash('Atividade não encontrada.', 'danger')
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            dados = {
                'atividade_desc': request.form.get('atividade_desc'),
                'testes_realizados': request.form.get('testes_realizados'),
                'observacao_resumo': request.form.get('observacao_resumo'),
                'nao_conformidade': request.form.get('nao_conformidade'),
                'situacao': request.form.get('situacao'),
                'recomendacao': request.form.get('recomendacao'),
                'periodo_inicio': request.form.get('periodo_inicio'),
                'periodo_fim': request.form.get('periodo_fim'),
                'extensao_exames': request.form.get('extensao_exames'),
                'criterio_amostragem': request.form.get('criterio_amostragem')
            }
            dados = {k: v for k, v in dados.items() if v is not None}
            db.atualizar_atividade(sess, id_atividade, dados)
            flash('Atividade atualizada com sucesso!', 'success')
            return redirect(url_for('ver_relatorio', id_caso=atividade.caso_id))

        caso = db.buscar_caso_por_id(sess, atividade.caso_id)

    return render_template('editar_atividade.html',
                           atividade=atividade,
                           caso=caso,
                           opcoes_situacao=LISTA_SITUACAO_HARDCODED,
                           opcoes_atividade=LISTA_ATIVIDADES_SISTEMA)

@app.route('/relatorio/<int:id_caso>/concluir', methods=['POST'])
@login_required
def concluir_relatorio(id_caso):
    texto_apresentacao = request.form.get('contexto_apresentacao')
    with db.get_db() as sess:
        caso = db.buscar_caso_por_id(sess, id_caso)
        
        permite = False
        if caso.status == 'Aprovado': permite = True
        if g.user.role in ['Admin', 'Manager']: permite = True
        
        if permite:
            caso.status = 'Concluído'
            caso.contexto_apresentacao = texto_apresentacao
            sess.commit()
            flash('Relatório Finalizado e Concluído!', 'success')
        else:
            flash('Você não tem permissão para concluir este relatório.', 'danger')
            
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/editar', methods=['GET', 'POST'])
@login_required
def editar_relatorio(id_caso):
    with db.get_db() as sess:
        caso = db.buscar_caso_por_id(sess, id_caso)
    if not caso: return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        dados = {
            'status': request.form.get('status'),
            'data_inicio': request.form.get('data_inicio'),
            'data_final': request.form.get('data_final')
        }
        dados = {k: v for k, v in dados.items() if v is not None}
        with db.get_db() as sess:
            db.atualizar_relatorio(sess, id_caso, dados)
        flash('Dados do relatório atualizados.', 'success')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))
    
    return render_template('editar_relatorio.html', caso=caso, opcoes_situacao=LISTA_SITUACAO_HARDCODED)

@app.route('/relatorio/<int:id_caso>/deletar', methods=['POST'])
@login_required
@role_required('Admin', 'Manager')
def deletar_relatorio(id_caso):
    with db.get_db() as sess:
        db.deletar_caso(sess, id_caso)
    flash('Relatório excluído permanentemente.', 'success')
    return redirect(url_for('dashboard'))

# =============================================
# ==== ADMINISTRAÇÃO GERAL ====
# =============================================

@app.route('/admin/usuarios')
@login_required
@role_required('Admin', 'Manager')
def listar_usuarios():
    with db.get_db() as sess:
        lista = db.buscar_todos_usuarios(sess)
    return render_template('admin_usuarios.html', usuarios=lista)

@app.route('/admin/usuario/novo', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Manager')
def criar_usuario():
    if request.method == 'POST':
        dados = {
            'codigo': request.form.get('codigo', '').strip().upper(),
            'nome_completo': request.form.get('nome_completo', '').strip().upper(),
            'senha': request.form.get('senha'),
            'role': request.form.get('role'),
            'gerente_id': request.form.get('gerente_id')
        }
        with db.get_db() as sess:
            if db.adicionar_usuario(sess, dados):
                flash('Usuário criado com sucesso.', 'success')
                return redirect(url_for('listar_usuarios'))
            else:
                flash('Erro: Já existe um usuário com este Código.', 'danger')
    
    with db.get_db() as sess:
        gerentes = db.buscar_todos_usuarios(sess)
    return render_template('admin_usuario_form.html', roles=['Admin', 'Manager', 'Auditor'], gerentes=gerentes)

@app.route('/admin/usuario/editar/<int:user_id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(user_id):
    # Permite edição se for Admin/Manager OU se for o próprio usuário
    if g.user.role not in ['Admin', 'Manager'] and g.user.id != user_id:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        dados = {
            'codigo': request.form.get('codigo'),
            'nome_completo': request.form.get('nome_completo'),
            'role': request.form.get('role'),
            'gerente_id': request.form.get('gerente_id')
        }
        if request.form.get('nova_senha'):
            dados['senha'] = request.form.get('nova_senha')
            
        with db.get_db() as sess:
            db.atualizar_usuario(sess, user_id, dados)
        flash('Perfil atualizado.', 'success')
        return redirect(url_for('listar_usuarios'))

    with db.get_db() as sess:
        u = db.buscar_usuario_por_id(sess, user_id)
        gs = db.buscar_todos_usuarios(sess)
    return render_template('admin_usuario_form.html', usuario_para_editar=u, gerentes=gs, roles=['Admin', 'Manager', 'Auditor'])

@app.route('/admin/categorias')
@login_required
@role_required('Admin', 'Manager')
def listar_categorias():
    with db.get_db() as sess:
        cats = db.buscar_todas_categorias(sess)
    return render_template('admin_categorias.html', categorias=cats)

@app.route('/admin/categoria/novo', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Manager')
def nova_categoria():
    if request.method == 'POST':
        with db.get_db() as sess:
            db.adicionar_categoria(sess, request.form.get('nome'))
        return redirect(url_for('listar_categorias'))
    return render_template('admin_categoria_form.html')

@app.route('/admin/categoria/deletar/<int:id>', methods=['POST'])
@login_required
@role_required('Admin', 'Manager')
def deletar_categoria(id):
    with db.get_db() as sess:
        db.deletar_categoria(sess, id)
    return redirect(url_for('listar_categorias'))

@app.route('/admin/filiais')
@login_required
@role_required('Admin', 'Manager')
def listar_filiais():
    with db.get_db() as sess:
        fils = db.buscar_todas_filiais(sess)
    return render_template('admin_filiais.html', filiais=fils)

@app.route('/admin/filial/novo', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Manager')
def nova_filial():
    if request.method == 'POST':
        with db.get_db() as sess:
            db.adicionar_filial(sess, request.form.get('nome'), request.form.get('cidade'))
        return redirect(url_for('listar_filiais'))
    return render_template('admin_filial_form.html')

@app.route('/admin/filial/deletar/<int:id>', methods=['POST'])
@login_required
@role_required('Admin', 'Manager')
def deletar_filial(id):
    with db.get_db() as sess:
        db.deletar_filial(sess, id)
    return redirect(url_for('listar_filiais'))

# =======================================================
# ==== GESTÃO DE POP (Procedimentos Operacionais) ====
# =======================================================

@app.route('/admin/pops')
@login_required
def listar_pops():
    """Lista todos os POPs agrupados por categoria (Acesso livre para todos)"""
    with db.get_db() as sess:
        categorias = sess.query(db.Categoria).options(
            db.joinedload(db.Categoria.atividades_padrao).joinedload(db.AtividadePadrao.autor)
        ).all()
        return render_template('admin_pops_lista.html', categorias=categorias)

@app.route('/admin/pop/novo', methods=['POST'])
@login_required
def novo_pop():
    """Cria um novo POP em rascunho"""
    titulo = request.form.get('titulo')
    categoria_id = request.form.get('categoria_id')
    with db.get_db() as sess:
        novo = db.AtividadePadrao(
            titulo=titulo,
            categoria_id=categoria_id,
            status='Rascunho',
            autor_id=g.user.id
        )
        sess.add(novo)
        sess.commit()
        return redirect(url_for('editar_pop', pop_id=novo.id))

@app.route('/admin/pop/<int:pop_id>/editor')
@login_required
def editar_pop(pop_id):
    """Abre a tela de edição de blocos do POP"""
    with db.get_db() as sess:
        pop = sess.query(db.AtividadePadrao).options(
            db.joinedload(db.AtividadePadrao.passos),
            db.joinedload(db.AtividadePadrao.categoria)
        ).filter_by(id=pop_id).first()
        
        if not pop:
            flash('POP não encontrado.', 'danger')
            return redirect(url_for('listar_pops'))
            
        return render_template('admin_pop_editor.html', pop=pop)

@app.route('/admin/pop/deletar/<int:pop_id>', methods=['POST'])
@login_required
@role_required('Admin', 'Manager')
def deletar_pop(pop_id):
    """Exclui um POP inteiro (Apenas Admin/Manager)"""
    try:
        with db.get_db() as sess:
            pop = sess.query(db.AtividadePadrao).filter_by(id=pop_id).first()
            if pop:
                sess.delete(pop)
                sess.commit()
                flash('Procedimento excluído com sucesso.', 'success')
            else:
                flash('POP não encontrado.', 'danger')
    except Exception as e:
        print(f"Erro ao deletar POP: {e}")
        flash('Erro ao excluir. Verifique se existem relatórios já criados usando este POP.', 'danger')
        
    return redirect(url_for('listar_pops'))

# =============================================
# ==== APIs DO SISTEMA (Para AJAX/JavaScript) ====
# =============================================

@app.route('/api/atividade/<int:id_atividade>')
@login_required
def get_atividade_details(id_atividade):
    """Retorna dados de uma atividade (usado no modal de edição)"""
    with db.get_db() as sess:
        atividade = db.buscar_atividade_por_id(sess, id_atividade)
    if atividade:
        atividade_dict = db.object_as_dict(atividade) 
        if atividade.realizado_por:
            atividade_dict['realizado_por_nome'] = atividade.realizado_por.nome_completo
        else:
            atividade_dict['realizado_por_nome'] = 'Não atribuído'
        return jsonify(atividade_dict)
    else:
        return jsonify({'error': 'Atividade não encontrada'}), 404

# --- APIs do Editor de Blocos (POP) ---

@app.route('/api/pop/<int:pop_id>/adicionar_passo', methods=['POST'])
@login_required
def api_adicionar_passo(pop_id):
    dados = request.json
    with db.get_db() as sess:
        novo_passo = db.PassoPOP(
            atividade_padrao_id=pop_id,
            tipo=dados.get('tipo'),
            conteudo=dados.get('conteudo'),
            ordem=dados.get('ordem')
        )
        sess.add(novo_passo)
        sess.commit()
        return jsonify({'success': True, 'id': novo_passo.id})

@app.route('/api/pop/atualizar_passo/<int:passo_id>', methods=['POST'])
@login_required
def api_atualizar_passo(passo_id):
    dados = request.json
    try:
        with db.get_db() as sess:
            passo = sess.query(db.PassoPOP).filter_by(id=passo_id).first()
            if passo:
                if 'conteudo' in dados: passo.conteudo = dados['conteudo']
                if 'tipo' in dados: passo.tipo = dados['tipo']
                if 'ordem' in dados: passo.ordem = dados['ordem']
                sess.commit()
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Passo não encontrado'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/pop/remover_passo/<int:passo_id>', methods=['POST'])
@login_required
def api_remover_passo(passo_id):
    with db.get_db() as sess:
        passo = sess.query(db.PassoPOP).filter_by(id=passo_id).first()
        if passo:
            sess.delete(passo)
            sess.commit()
            return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/pop/<int:pop_id>/publicar', methods=['POST'])
@login_required
def api_publicar_pop(pop_id):
    """
    Publica ou Solicita Revisão do POP.
    - Se Admin/Manager: Publica direto.
    - Se Auditor: Muda status para 'Pendente de Revisão'.
    """
    with db.get_db() as sess:
        pop = sess.query(db.AtividadePadrao).filter_by(id=pop_id).first()
        if pop:
            if g.user.role in ['Admin', 'Manager']:
                pop.status = 'Publicado'
                msg = 'Procedimento publicado com sucesso!'
            else:
                pop.status = 'Pendente de Revisão'
                msg = 'Solicitação de revisão enviada ao gerente!'
            
            sess.commit()
            flash(msg, 'success')
            return jsonify({'success': True})
            
    return jsonify({'success': False})

@app.route('/api/get-user-name/<string:codigo>')
@login_required
def get_user_name(codigo):
    with db.get_db() as sess:
        usuario = db.buscar_usuario_por_codigo(sess, codigo)
    if usuario:
        return jsonify({'nome_completo': usuario['nome_completo']})
    else:
        return jsonify({'error': 'Usuário não encontrado'}), 404

# Inicialização
if __name__ == '__main__':
    app.run(debug=True) 