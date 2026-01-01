import os
from datetime import date, datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g, send_from_directory, make_response
from functools import wraps
import database as db
import config
import pprint
from werkzeug.utils import secure_filename
import pdf_generator # Importando o nosso motor de PDF

load_dotenv()
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = os.getenv('SECRET_KEY', 'um-segredo-muito-forte-para-desenvolvimento')

LISTA_SITUACAO_HARDCODED = [
    "SEM IRREGULARIDADES",
    "SEM IRREGULARIDADES COM RESSALVA",
    "IRREGULARIDADE LEVE",
    "IRREGULARIDADE GRAVE",
    "FRAUDE"
]    

# =======================================================
# ==== CARREGADOR GLOBAL DE UTILIZADOR (LÓGICA NOVA) ====
# =======================================================
@app.before_request
def carregar_usuario_logado():
    """
    Executa ANTES de cada requisição. Pega o user_id da sessão,
    busca o usuário ATUALIZADO no banco e o armazena em 'g.user',
    que fica disponível durante toda a requisição.
    """
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        with db.get_db() as sess:
            # buscar_usuario_por_id retorna o OBJETO completo
            g.user = db.buscar_usuario_por_id(sess, user_id)

# =============================================
# ==== INJETOR DE CONTEXTO (ATUALIZADO) ====
# =============================================
@app.context_processor
def inject_user():
    """
    Disponibiliza a variável 'usuario' para TODOS os templates.
    O seu valor é o objeto g.user que foi carregado no before_request.
    """
    return dict(usuario=getattr(g, 'user', None))

# =============================================
# ==== DECORADORES (ATUALIZADOS) ====
# =============================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # ALTERADO: Verifica 'g.user' em vez da sessão diretamente
        if g.user is None:
            flash('Por favor, faça o login para acessar esta página.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # ALTERADO: A verificação usa g.user, que é sempre 'ao vivo'
            if g.user is None or g.user.role not in roles:
                flash('Você não tem permissão para aceder a esta página.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# =============================================
# ==== ROTAS ====
# =============================================

# --- ROTAS DE AUTENTICAÇÃO E PRINCIPAIS ---
@app.route('/')
def home():
    # ALTERADO: Verifica g.user
    if g.user:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # ALTERADO: Verifica g.user
    if g.user:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        codigo = request.form['codigo']
        senha = request.form['senha']
        with db.get_db() as sess:
            dados_usuario_dict = db.verificar_login(sess, codigo, senha)
        
        if dados_usuario_dict:
            session.clear()
            # ALTERADO: Guardamos apenas o ID na sessão
            session['user_id'] = dados_usuario_dict['id']
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Código ou Senha inválidos.', 'danger')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # ALTERADO: Limpa a sessão para remover o user_id
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    with db.get_db() as sess:
        lista_de_casos = db.buscar_casos(sess)
        todas_categorias = db.buscar_todas_categorias(sess)
        todas_filiais = db.buscar_todas_filiais(sess)
        
    return render_template('dashboard.html', 
                           casos=lista_de_casos, 
                           categorias=todas_categorias, 
                           filiais=todas_filiais)

# --- ROTAS DE RELATÓRIO E WORKFLOW ---

@app.route('/relatorio/novo/categoria/<int:categoria_id>', methods=['POST'])
@login_required
def novo_relatorio_por_categoria(categoria_id):
    try:
        # Apanha o filial_id que vem do formulário na modal
        filial_id = request.form.get('filial_id')
        if not filial_id:
            flash('Por favor, selecione uma filial.', 'warning')
            return redirect(url_for('dashboard'))

        with db.get_db() as sess:
            novo_id = db.criar_caso_com_atividades_padrao(
                sess, 
                categoria_id=categoria_id, 
                filial_id=filial_id, 
                realizado_por_id=g.user.id
            )
        
        if novo_id:
            flash(f'Novo relatório criado com sucesso!', 'success')
            return redirect(url_for('ver_relatorio', id_caso=novo_id))
        else:
            raise Exception("A criação do novo caso retornou um ID inválido.")
            
    except Exception as e:
        print(f"ERRO na rota novo_relatorio_por_categoria: {e}")
        flash('Erro ao criar novo relatório.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/relatorio/<int:id_caso>', methods=['GET'])
@login_required
def ver_relatorio(id_caso):
    with db.get_db() as sess:
        dados_caso = db.buscar_caso_por_id(sess, id_caso)
    
    if not dados_caso:
        flash(f'Relatório com ID {id_caso} não encontrado.', 'danger')
        return redirect(url_for('dashboard'))
    
    lista_atividades = dados_caso.atividades

    return render_template('relatorio.html', 
                           caso=dados_caso, 
                           atividades=lista_atividades, 
                           opcoes_atividade=config.LISTA_ATIVIDADES,                           
                           opcoes_situacao=LISTA_SITUACAO_HARDCODED)

@app.route('/relatorio/<int:id_caso>/pdf')
@login_required
def gerar_pdf_relatorio(id_caso):
    """
    Gera e envia o relatório completo em formato PDF para download.
    """
    try:
        # 1. Busca todos os dados necessários do banco.
        # A nossa função buscar_caso_por_id já é perfeita para isto, pois carrega tudo!
        with db.get_db() as sess:
            caso = db.buscar_caso_por_id(sess, id_caso)
        
        if not caso:
            flash('Relatório não encontrado.', 'danger')
            return redirect(url_for('dashboard'))

        # 2. Chama o nosso "Motor de PDF", passando os dados.
        # Ele nos devolve o PDF pronto, guardado na memória.
        pdf_buffer = pdf_generator.gerar_relatorio_pdf(caso, caso.atividades)
        
        # 3. Constrói a resposta HTTP que será enviada para o navegador.
        response = make_response(pdf_buffer.getvalue())
        
        # 4. Define os "cabeçalhos" da resposta para que o navegador entenda o que fazer.
        #    'Content-Type' diz: "Isto é um ficheiro PDF".
        response.headers['Content-Type'] = 'application/pdf'
        #    'Content-Disposition' diz: "Trate isto como um anexo para download e sugira este nome de ficheiro".
        # Ajuste para garantir que o nome do arquivo seja seguro
        safe_filename = secure_filename(f'relatorio_{caso.numero_relatorio_display}.pdf')
        response.headers['Content-Disposition'] = f'attachment; filename={safe_filename}'
        
        return response

    except Exception as e:
        print(f"ERRO ao gerar PDF: {e}")
        flash('Ocorreu um erro ao gerar o relatório PDF.', 'danger')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/adicionar_atividade', methods=['POST'])
@login_required
def adicionar_atividade(id_caso):
    dados_formulario = {
        'atividade_desc': request.form.get('atividade_desc'),
        'testes_realizados': request.form.get('testes_realizados'),
        'observacao_resumo': request.form.get('observacao_resumo'),
        'nao_conformidade': request.form.get('nao_conformidade'),
        'recomendacao': request.form.get('recomendacao'),
        'situacao': request.form.get('situacao'),
        'realizado_por_id': g.user.id, # ALTERADO: Usa g.user.id
        'data_registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'caso_id': id_caso,
        'periodo_inicio': request.form.get('periodo_inicio'), 
        'periodo_fim': request.form.get('periodo_fim'),        
        'extensao_exames': request.form.get('extensao_exames'),
        'criterio_amostragem': request.form.get('criterio_amostragem')
    }
    with db.get_db() as sess:
        sucesso = db.salvar_atividade(sess, dados_formulario)

    if sucesso:
        flash('Atividade registrada com sucesso!', 'success')
    else:
        flash('Ocorreu um erro ao salvar a atividade.', 'danger')

    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/anexar', methods=['POST'])
@login_required
def anexar_ficheiro(id_caso):
    # 1. Verifica se a requisição tem um ficheiro
    if 'anexo' not in request.files:
        flash('Nenhum ficheiro selecionado.', 'warning')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))

    file = request.files['anexo']

    # 2. Verifica se o utilizador realmente selecionou um ficheiro
    if file.filename == '':
        flash('Nenhum ficheiro selecionado.', 'warning')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))

    if file:
        # 3. Segurança: Limpa o nome do ficheiro para remover caracteres inválidos
        original_filename = secure_filename(file.filename)
        
        # 4. Cria um nome único para evitar ficheiros com o mesmo nome
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        secure_name = f"{timestamp}_{original_filename}"
        
        # 5. Define o caminho completo onde o ficheiro será salvo
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_name)
        
        try:
            # 6. Salva o ficheiro no "armazém físico"
            file.save(save_path)
            
            # 7. Salva a "ficha de registo" no banco de dados
            with db.get_db() as sess:
                db.adicionar_anexo(sess, id_caso, original_filename, secure_name, save_path)
            
            flash('Anexo enviado com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao salvar anexo: {e}")
            flash('Ocorreu um erro ao enviar o anexo.', 'danger')

    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/submeter', methods=['POST'])
@login_required
def submeter_relatorio(id_caso):
    with db.get_db() as sess:
        sucesso = db.atualizar_relatorio(sess, id_caso, {'status': 'Pendente de Revisão'})
    if sucesso:
        flash('Relatório submetido para revisão com sucesso!', 'success')
    else:
        flash('Erro ao submeter o relatório.', 'danger')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/aprovar', methods=['POST'])
@login_required
@role_required('Manager', 'Admin')
def aprovar_relatorio(id_caso):
    notas = request.form.get('notas_aprovacao', '')
    with db.get_db() as sess:
        sucesso = db.atualizar_relatorio(sess, id_caso, {'status': 'Aprovado', 'notas_revisao': notas})
    if sucesso:
        flash('Relatório aprovado com sucesso!', 'success')
    else:
        flash('Ocorreu um erro ao aprovar o relatório.', 'danger')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/rejeitar', methods=['POST'])
@login_required
@role_required('Manager', 'Admin')
def rejeitar_relatorio(id_caso):
    notas = request.form.get('notas_revisao')
    if not notas:
        flash('Para rejeitar, é obrigatório deixar uma nota de correção.', 'danger')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))
    with db.get_db() as sess:
        sucesso = db.atualizar_relatorio(sess, id_caso, {'status': 'Em Elaboração', 'notas_revisao': notas})
    if sucesso:
        flash('Relatório devolvido para correção.', 'info')
    else:
        flash('Ocorreu um erro ao rejeitar o relatório.', 'danger')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/concluir', methods=['POST'])
@login_required
def concluir_relatorio(id_caso):
    texto_apresentacao = request.form.get('contexto_apresentacao')
    
    if not texto_apresentacao:
        flash('É obrigatório descrever o contexto da apresentação para concluir.', 'warning')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))

    with db.get_db() as sess:
        caso = db.buscar_caso_por_id(sess, id_caso)
        
        if not caso:
            flash('Relatório não encontrado.', 'danger')
            return redirect(url_for('dashboard'))

        # === REGRA DE NEGÓCIO ===
        permite_concluir = False
        
        # Regra 1: Se já está APROVADO, qualquer usuário logado pode concluir
        if caso.status == 'Aprovado':
            permite_concluir = True
            
        # Regra 2: Se NÃO está aprovado, apenas Admin ou Manager pode forçar a conclusão
        elif g.user.role in ['Admin', 'Manager']:
            permite_concluir = True
        
        else:
            permite_concluir = False

        if permite_concluir:
            # Atualiza o status e salva o texto
            caso.status = 'Concluído'
            caso.contexto_apresentacao = texto_apresentacao
            # Opcional: Salvar data de conclusão se tivermos coluna para isso
            sess.commit()
            flash('Relatório marcado como CONCLUÍDO com sucesso!', 'success')
        else:
            flash('Você não tem permissão para concluir este relatório no status atual.', 'danger')

    return redirect(url_for('ver_relatorio', id_caso=id_caso))


@app.route('/uploads/<string:nome_seguro>')
@login_required
def download_anexo(nome_seguro):
    """
    Rota segura para servir os ficheiros da pasta de uploads.
    """
    try:
        # A função send_from_directory é a forma segura do Flask de enviar ficheiros.
        # Ela impede que os utilizadores tentem aceder a outros diretórios do sistema.
        # 'as_attachment=True' força o download do ficheiro em vez de tentar exibi-lo no navegador.
        return send_from_directory(
            app.config['UPLOAD_FOLDER'], 
            nome_seguro, 
            as_attachment=True
        )
    except FileNotFoundError:
        flash('Arquivo não encontrado.', 'danger')
        # Redireciona de volta para a última página visitada ou para o dashboard
        return redirect(request.referrer or url_for('dashboard'))
    
@app.route('/relatorio/<int:id_caso>/editar', methods=['GET', 'POST'])
@login_required
def editar_relatorio(id_caso):
    with db.get_db() as sess:
        # Busca o caso que será editado
        caso = db.buscar_caso_por_id(sess, id_caso)

    if not caso:
        flash('Relatório não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

    # Se o formulário foi submetido (método POST)
    if request.method == 'POST':
        # CORREÇÃO: Removemos 'titulo' e 'tipo' que não existem mais no banco
        # Adicionamos 'data_inicio' e 'data_final' que são úteis
        dados_formulario = {
            'status': request.form.get('status'),
            'data_inicio': request.form.get('data_inicio'),
            'data_final': request.form.get('data_final')
        }
        
        # Removemos chaves com valores vazios para não apagar dados existentes sem querer
        dados_limpos = {k: v for k, v in dados_formulario.items() if v is not None}

        with db.get_db() as sess:
            sucesso = db.atualizar_relatorio(sess, id_caso, dados_limpos)
        
        if sucesso:
            flash('Relatório atualizado com sucesso!', 'success')
            return redirect(url_for('ver_relatorio', id_caso=id_caso))
        else:
            flash('Ocorreu um erro ao atualizar o relatório.', 'danger')

    # Se for a primeira vez a aceder à página (método GET), mostra o formulário
    return render_template('editar_relatorio.html', 
                           caso=caso, 
                           opcoes_situacao=config.LISTA_SITUACAO)

# --- ROTAS DE ADMINISTRAÇÃO ---
@app.route('/admin/usuarios')
@login_required
@role_required('Admin', 'Manager')
def gestao_usuarios():
    with db.get_db() as sess:
        lista_de_usuarios = db.buscar_todos_usuarios(sess)
    return render_template('gestao_usuarios.html', usuarios=lista_de_usuarios)

@app.route('/admin/usuario/novo', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Manager')
def criar_usuario():
    if request.method == 'POST':
        dados_formulario = {
            'codigo': request.form.get('codigo', '').strip().upper(),
            'nome_completo': request.form.get('nome_completo', '').strip().upper(),
            'senha': request.form.get('senha'),
            'role': request.form.get('role'),
            'gerente_id': request.form.get('gerente_id')
        }
        with db.get_db() as sess:
            sucesso = db.adicionar_usuario(sess, dados_formulario)
        if sucesso:
            flash(f'Usuário criado com sucesso!', 'success')
            return redirect(url_for('gestao_usuarios'))
        else:
            flash(f'Erro: O código ou username gerado já existe.', 'danger')
            return redirect(url_for('criar_usuario'))
    
    with db.get_db() as sess:
        lista_gerentes = db.buscar_todos_usuarios(sess)
    return render_template('criar_usuario.html', roles=config.LISTA_ROLES, gerentes=lista_gerentes)

@app.route('/admin/usuario/editar/<int:user_id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(user_id):
    
    # A verificação de permissão usa g.user
    if g.user.role not in ['Admin', 'Manager'] and g.user.id != user_id:
        flash('Você não tem permissão para editar este perfil.', 'danger')
        return redirect(url_for('dashboard'))

    with db.get_db() as sess:
        usuario_para_editar = db.buscar_usuario_por_id(sess, user_id)

    if not usuario_para_editar:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('gestao_usuarios'))
    
    if request.method == 'POST':
        dados_formulario = {
            'codigo': request.form.get('codigo', '').strip().upper(),
            'nome_completo': request.form.get('nome_completo', '').strip().upper(),
            'username': request.form.get('username', '').strip(),
            'role': request.form.get('role'),
            'gerente_id': request.form.get('gerente_id') if request.form.get('gerente_id') else None
        }
        
        nova_senha = request.form.get('nova_senha')
        if nova_senha:
            dados_formulario['senha'] = nova_senha

        with db.get_db() as sess:
            sucesso = db.atualizar_usuario(sess, user_id, dados_formulario)
        
        if sucesso:
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('gestao_usuarios'))
        else:
            flash('Erro ao atualizar. O código ou username pode já estar em uso.', 'danger')
            return redirect(url_for('editar_usuario', user_id=user_id))

    with db.get_db() as sess:
        lista_gerentes = db.buscar_todos_usuarios(sess)      
   
    return render_template('editar_usuario.html', usuario_para_editar=usuario_para_editar, roles=config.LISTA_ROLES, gerentes=lista_gerentes)

# Rota para LISTAR todas as categorias
@app.route('/admin/categorias')
@login_required
@role_required('Admin', 'Manager')
def gestao_categorias():
    with db.get_db() as sess:
        categorias = db.buscar_todas_categorias(sess)
    return render_template('gestao_categorias.html', categorias=categorias)

# Rota para ADICIONAR uma nova categoria (mostra o formulário e processa)
@app.route('/admin/categoria/nova', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Manager')
def adicionar_categoria_route():
    if request.method == 'POST':
        nome = request.form.get('nome')
        if nome:
            with db.get_db() as sess:
                sucesso = db.adicionar_categoria(sess, nome)
            if sucesso:
                flash('Categoria criada com sucesso!', 'success')
                return redirect(url_for('gestao_categorias'))
            else:
                flash('Erro ao criar categoria. O nome já pode existir.', 'danger')
    return render_template('form_categoria.html')

# Rota para EDITAR uma categoria existente (mostra o formulário e processa)
@app.route('/admin/categoria/editar/<int:categoria_id>', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Manager')
def editar_categoria_route(categoria_id):
    with db.get_db() as sess:
        categoria = db.buscar_categoria_por_id(sess, categoria_id)
    if not categoria:
        flash('Categoria não encontrada.', 'danger')
        return redirect(url_for('gestao_categorias'))
        
    if request.method == 'POST':
        nome = request.form.get('nome')
        if nome:
            with db.get_db() as sess:
                sucesso = db.atualizar_categoria(sess, categoria_id, nome)
            if sucesso:
                flash('Categoria atualizada com sucesso!', 'success')
                return redirect(url_for('gestao_categorias'))
            else:
                flash('Erro ao atualizar categoria.', 'danger')

    return render_template('form_categoria.html', categoria=categoria)

# Rota para DELETAR uma categoria
@app.route('/admin/categoria/deletar/<int:categoria_id>', methods=['POST'])
@login_required
@role_required('Admin', 'Manager')
def deletar_categoria_route(categoria_id):
    with db.get_db() as sess:
        sucesso = db.deletar_categoria(sess, categoria_id)
    if sucesso:
        flash('Categoria deletada com sucesso!', 'success')
    else:
        flash('Erro ao deletar categoria.', 'danger')
    return redirect(url_for('gestao_categorias'))

# Rota para LISTAR todas as filiais
@app.route('/admin/filiais')
@login_required
@role_required('Admin', 'Manager')
def gestao_filiais():
    with db.get_db() as sess:
        filiais = db.buscar_todas_filiais(sess)
    return render_template('gestao_filiais.html', filiais=filiais)

# Rota para ADICIONAR uma nova filial
@app.route('/admin/filial/nova', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Manager')
def adicionar_filial_route():
    if request.method == 'POST':
        nome = request.form.get('nome')
        cidade = request.form.get('cidade')
        if nome:
            with db.get_db() as sess:
                sucesso = db.adicionar_filial(sess, nome, cidade)
            if sucesso:
                flash('Filial criada com sucesso!', 'success')
                return redirect(url_for('gestao_filiais'))
            else:
                flash('Erro ao criar filial. O nome já pode existir.', 'danger')
    return render_template('form_filial.html')

# Rota para EDITAR uma filial
@app.route('/admin/filial/editar/<int:filial_id>', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Manager')
def editar_filial_route(filial_id):
    with db.get_db() as sess:
        filial = db.buscar_filial_por_id(sess, filial_id)
    if not filial:
        flash('Filial não encontrada.', 'danger')
        return redirect(url_for('gestao_filiais'))
        
    if request.method == 'POST':
        nome = request.form.get('nome')
        cidade = request.form.get('cidade')
        if nome:
            with db.get_db() as sess:
                sucesso = db.atualizar_filial(sess, filial_id, nome, cidade)
            if sucesso:
                flash('Filial atualizada com sucesso!', 'success')
                return redirect(url_for('gestao_filiais'))
            else:
                flash('Erro ao atualizar filial.', 'danger')

    return render_template('form_filial.html', filial=filial)

# Rota para DELETAR uma filial
@app.route('/admin/filial/deletar/<int:filial_id>', methods=['POST'])
@login_required
@role_required('Admin', 'Manager')
def deletar_filial_route(filial_id):
    with db.get_db() as sess:
        sucesso = db.deletar_filial(sess, filial_id)
    if sucesso:
        flash('Filial deletada com sucesso!', 'success')
    else:
        flash('Erro ao deletar filial. Verifique se não existem relatórios associados a ela.', 'danger')
    return redirect(url_for('gestao_filiais'))

@app.route('/atividade/<int:id_atividade>/editar', methods=['GET', 'POST'])
@login_required 
def editar_atividade(id_atividade):
    with db.get_db() as sess:
        atividade_atual = db.buscar_atividade_por_id(sess, id_atividade)
    if not atividade_atual:
        flash('Atividade não encontrada.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        dados_do_formulario = {
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
        campos_para_atualizar = {k: v for k, v in dados_do_formulario.items() if str(v or '') != str(getattr(atividade_atual, k) or '')}

        if campos_para_atualizar:
            with db.get_db() as sess:
                # Precisamos de uma função para atualizar atividades
                sucesso = db.atualizar_atividade(sess, id_atividade, campos_para_atualizar)
            if sucesso:
                flash(f'{len(campos_para_atualizar)} campo(s) atualizado(s) com sucesso!', 'success')
            else:
                flash('Ocorreu um erro ao atualizar a atividade.', 'danger')
        else:
            flash('Nenhuma alteração foi detectada.', 'info')
        return redirect(url_for('ver_relatorio', id_caso=atividade_atual.caso_id))
    
    with db.get_db() as sess:
        caso = db.buscar_caso_por_id(sess, atividade_atual.caso_id)
    return render_template('editar_atividade.html', atividade=atividade_atual, caso=caso, opcoes_atividade=config.LISTA_ATIVIDADES, opcoes_situacao=LISTA_SITUACAO_HARDCODED)

# --- ROTAS DE API ---
@app.route('/api/get-user-name/<string:codigo>')
def get_user_name(codigo):
    with db.get_db() as sess:
        usuario = db.buscar_usuario_por_codigo(sess, codigo)
    
    if usuario:
        return jsonify({'nome_completo': usuario['nome_completo']})
    else:
        return jsonify({'error': 'Usuário não encontrado'}), 404

@app.route('/api/atividade/<int:id_atividade>')
@login_required
def get_atividade_details(id_atividade):
    with db.get_db() as sess:
        # A nossa função buscar_atividade_por_id já faz o eager load do realizado_por
        atividade = db.buscar_atividade_por_id(sess, id_atividade)
    if atividade:
        # object_as_dict incluirá periodo_inicio e periodo_fim automaticamente!
        atividade_dict = db.object_as_dict(atividade) 
        
        # Adicionamos o nome do responsável
        if atividade.realizado_por:
            atividade_dict['realizado_por_nome'] = atividade.realizado_por.nome_completo
        else:
            atividade_dict['realizado_por_nome'] = 'Não atribuído'
            
        return jsonify(atividade_dict)
    else:
        return jsonify({'error': 'Atividade não encontrada'}), 404
    

@app.route('/api/atividade/<int:id_atividade_atual>/historico/filial')
@login_required
def get_historico_atividade_filial(id_atividade_atual):
    """
    API para buscar o histórico de uma atividade específica na mesma filial.
    """
    try:
        with db.get_db() as sess:
            # 1. Primeiro, buscamos o objeto da atividade ATUAL para ter as "coordenadas"
            atividade_atual = db.buscar_atividade_por_id(sess, id_atividade_atual)
            if not atividade_atual:
                return jsonify({'error': 'Atividade atual não encontrada'}), 404

            # 2. Usamos a nossa nova função de consulta inteligente
            atividades_historicas = db.buscar_historico_atividade_na_filial(sess, atividade_atual)
            
            # 3. Formatamos os resultados para enviá-los como JSON
            historico_formatado = []
            for at_hist in atividades_historicas:
                historico_formatado.append({
                    'relatorio_numero': at_hist.caso.numero_relatorio_display, # Usando a propriedade formatada
                    'data_registro': at_hist.data_registro,
                    'realizado_por': at_hist.realizado_por.nome_completo if at_hist.realizado_por else 'N/A',
                    'observacao_resumo': at_hist.observacao_resumo,
                    'nao_conformidade': at_hist.nao_conformidade,
                    'recomendacao': at_hist.recomendacao,
                    'situacao': at_hist.situacao
                })
        
        # 4. Retornamos a lista de históricos formatada
        return jsonify(historico_formatado)

    except Exception as e:
        print(f"ERRO na API de histórico: {e}")
        return jsonify({'error': 'Ocorreu um erro interno ao buscar o histórico.'}), 500 

@app.route('/api/atividade/<int:id_atividade_atual>/historico/global')
@login_required
def get_historico_atividade_global(id_atividade_atual):
    """
    API para buscar o histórico de uma atividade específica em TODAS as filiais.
    """
    try:
        with db.get_db() as sess:
            # 1. Buscamos a atividade atual para saber o que procurar
            atividade_atual = db.buscar_atividade_por_id(sess, id_atividade_atual)
            if not atividade_atual:
                return jsonify({'error': 'Atividade atual não encontrada'}), 404

            # 2. Chamamos a nossa nova função de consulta global
            atividades_historicas = db.buscar_historico_atividade_global(sess, atividade_atual)
            
            # 3. Formatamos os resultados para JSON, incluindo o nome da filial
            historico_formatado = []
            for at_hist in atividades_historicas:
                historico_formatado.append({
                    'relatorio_numero': at_hist.caso.numero_relatorio_display, # Usando a propriedade formatada
                    'filial_nome': at_hist.caso.filial.nome if at_hist.caso.filial else 'N/A', # A informação extra que precisamos!
                    'data_registro': at_hist.data_registro,
                    'realizado_por': at_hist.realizado_por.nome_completo if at_hist.realizado_por else 'N/A',
                    'observacao_resumo': at_hist.observacao_resumo,
                    'nao_conformidade': at_hist.nao_conformidade,
                    'recomendacao': at_hist.recomendacao,
                    'situacao': at_hist.situacao
                })
        
        return jsonify(historico_formatado)

    except Exception as e:
        print(f"ERRO na API de histórico global: {e}")
        return jsonify({'error': 'Ocorreu um erro interno ao buscar o histórico global.'}), 500

@app.route('/relatorio/<int:id_caso>/deletar', methods=['POST'])
@login_required
@role_required('Admin', 'Manager') # Apenas chefia pode deletar
def deletar_relatorio(id_caso):
    with db.get_db() as sess:
        sucesso = db.deletar_caso(sess, id_caso)
    
    if sucesso:
        flash('Relatório e todos os seus dados excluídos com sucesso.', 'success')
    else:
        flash('Erro ao excluir o relatório.', 'danger')
        
    return redirect(url_for('dashboard'))       

if __name__ == '__main__':
    app.run(debug=True)