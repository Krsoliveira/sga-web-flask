import os
from datetime import date, datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import database as db
import config
import pprint

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# =============================================
# ==== INJETOR DE CONTEXTO GLOBAL (ESSENCIAL) ====
# =============================================
@app.context_processor
def inject_user():
    """
    Injeta a variável 'usuario' no contexto de todos os templates.
    O valor será o dicionário do usuário se ele estiver logado, ou None caso contrário.
    """
    return dict(usuario=session.get('dados_usuario'))

# =============================================
# ==== DECORADORES ====
# =============================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'dados_usuario' not in session:
            flash('Por favor, faça o login para acessar esta página.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('dados_usuario', {}).get('role') not in roles:
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
    if 'dados_usuario' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'dados_usuario' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        codigo = request.form['codigo']
        senha = request.form['senha']
        dados_usuario = db.verificar_login(codigo, senha)
        if dados_usuario:
            session['dados_usuario'] = dados_usuario
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Código ou Senha inválidos.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('dados_usuario', None)
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    lista_de_casos = db.buscar_casos()
    return render_template('dashboard.html', casos=lista_de_casos)

# --- ROTAS DE RELATÓRIO E WORKFLOW ---
@app.route('/relatorio/novo', methods=['POST'])
@login_required
def novo_relatorio():
    hoje = date.today().strftime("%Y-%m-%d")
    novo_id = db.adicionar_novo_caso("Novo Relatório (preencher)", "Auditoria", hoje, "Em Elaboração")
    if novo_id:
        flash('Novo relatório criado com sucesso!', 'success')
        return redirect(url_for('ver_relatorio', id_caso=novo_id))
    else:
        flash('Erro ao criar novo relatório.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/relatorio/<int:id_caso>', methods=['GET'])
@login_required
def ver_relatorio(id_caso):
    dados_caso = db.buscar_caso_por_id(id_caso)
    if not dados_caso:
        flash(f'Relatório com ID {id_caso} não encontrado.', 'danger')
        return redirect(url_for('dashboard'))
    
    lista_atividades = db.buscar_atividades_completas_por_caso_id(id_caso)
    return render_template('relatorio.html', caso=dados_caso, atividades=lista_atividades, opcoes_atividade=config.LISTA_ATIVIDADES, opcoes_situacao=config.LISTA_SITUACAO)

@app.route('/relatorio/<int:id_caso>/adicionar_atividade', methods=['POST'])
@login_required
def adicionar_atividade(id_caso):
    dados_formulario = {
        'caso_id': id_caso,
        'atividade_desc': request.form.get('atividade_desc'),
        'testes_realizados': request.form.get('testes_realizados'),
        'extensao_exames': request.form.get('extensao_exames'),
        'criterio_amostragem': request.form.get('criterio_amostragem'),
        'periodo_inicio': request.form.get('periodo_inicio'),
        'periodo_fim': request.form.get('periodo_fim'),
        'observacao_resumo': request.form.get('observacao_resumo'),
        'realizado_por_id': session['dados_usuario']['id'],
        'nao_conformidade': request.form.get('nao_conformidade'),
        'reincidente': request.form.get('reincidente'),
        'recomendacao': request.form.get('recomendacao'),
        'data_p_solucao': request.form.get('data_p_solucao'),
        'data_registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'situacao': request.form.get('situacao')
    }
    try:
        db.salvar_atividade(dados_formulario)
        flash('Atividade registrada com sucesso!', 'success')
    except Exception as e:
        flash(f'Ocorreu um erro ao salvar a atividade: {e}', 'danger')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/<int:id_caso>/submeter', methods=['POST'])
@login_required
def submeter_relatorio(id_caso):
    sucesso = db.atualizar_status_relatorio(id_caso, 'Pendente de Revisão')
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
    sucesso = db.aprovar_relatorio_com_nota(id_caso, notas)
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
    sucesso = db.rejeitar_relatorio_com_nota(id_caso, notas)
    if sucesso:
        flash('Relatório devolvido para correção.', 'info')
    else:
        flash('Ocorreu um erro ao rejeitar o relatório.', 'danger')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

# --- ROTAS DE ADMINISTRAÇÃO ---
@app.route('/admin/usuarios')
@login_required
@role_required('Admin')
def gestao_usuarios():
    lista_de_usuarios = db.buscar_todos_usuarios()
    return render_template('gestao_usuarios.html', usuarios=lista_de_usuarios)

@app.route('/admin/usuario/novo', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def criar_usuario():
    if request.method == 'POST':
        gerente_id = request.form.get('gerente_id')
        codigo = request.form.get('codigo', '').strip().upper()
        nome = request.form.get('nome_completo', '').strip().upper()
        senha = request.form.get('senha')
        role = request.form.get('role')
        gerente_id_final = int(gerente_id) if gerente_id else None
        username = ""
        if nome:
            partes_nome = nome.lower().split()
            primeiro_nome = partes_nome[0]
            username = f"{primeiro_nome}.{partes_nome[-1]}" if len(partes_nome) > 1 else primeiro_nome
        if not all([codigo, nome, senha, role]):
            flash('Todos os campos, exceto o gerente, são obrigatórios.', 'danger')
            return redirect(url_for('criar_usuario'))
        sucesso = db.adicionar_usuario(codigo, nome, username, senha, role, gerente_id_final)
        if sucesso:
            flash(f'Usuário "{username}" criado com sucesso!', 'success')
            return redirect(url_for('gestao_usuarios'))
        else:
            flash(f'Erro: O código ou username gerado já existe.', 'danger')
            return redirect(url_for('criar_usuario'))
    lista_gerentes = db.buscar_todos_usuarios()
    return render_template('criar_usuario.html', roles=config.LISTA_ROLES, gerentes=lista_gerentes)

@app.route('/admin/usuario/editar/<int:user_id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(user_id):
    usuario_logado = session.get('dados_usuario', {})
    if usuario_logado.get('role') != 'Admin' and usuario_logado.get('id') != user_id:
        flash('Você só tem permissão para editar o seu próprio perfil.', 'danger')
        return redirect(url_for('dashboard'))
    usuario_para_editar = db.buscar_usuario_por_id(user_id)
    if not usuario_para_editar:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('gestao_usuarios'))
    if request.method == 'POST':
        gerente_id = request.form.get('gerente_id')
        dados_atualizados = {
            'codigo': request.form.get('codigo', '').strip().upper(),
            'nome_completo': request.form.get('nome_completo', '').strip().upper(),
            'username': request.form.get('username', '').strip(),
            'role': request.form.get('role'),
            'nova_senha': request.form.get('nova_senha'),
            'confirmar_senha': request.form.get('confirmar_senha'),
            'gerente_id': int(gerente_id) if gerente_id else None
        }
        if dados_atualizados['nova_senha'] != dados_atualizados['confirmar_senha']:
            flash('As novas senhas não coincidem. Tente novamente.', 'danger')
            return redirect(url_for('editar_usuario', user_id=user_id))
        if usuario_logado.get('role') != 'Admin':
            dados_atualizados['role'] = usuario_para_editar['role']
        sucesso = db.atualizar_usuario(user_id, dados_atualizados)
        if sucesso:
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('gestao_usuarios'))
        else:
            flash('Erro ao atualizar. O código ou username pode já estar em uso por outro usuário.', 'danger')
            return redirect(url_for('editar_usuario', user_id=user_id))
    lista_gerentes = db.buscar_todos_usuarios()
    return render_template('editar_usuario.html', usuario=usuario_para_editar, roles=config.LISTA_ROLES, gerentes=lista_gerentes)

@app.route('/atividade/<int:id_atividade>/editar', methods=['GET', 'POST'])
@login_required
def editar_atividade(id_atividade):
    atividade_atual = db.buscar_atividade_por_id(id_atividade)
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
            'recomendacao': request.form.get('recomendacao')
        }
        campos_para_atualizar = {}
        for campo, valor_novo in dados_do_formulario.items():
            valor_antigo = atividade_atual.get(campo)
            if str(valor_novo or '') != str(valor_antigo or ''):
                campos_para_atualizar[campo] = valor_novo
        if campos_para_atualizar:
            sucesso = db.atualizar_atividade(id_atividade, campos_para_atualizar)
            if sucesso:
                flash(f'{len(campos_para_atualizar)} campo(s) atualizado(s) com sucesso!', 'success')
            else:
                flash('Ocorreu um erro ao atualizar a atividade.', 'danger')
        else:
            flash('Nenhuma alteração foi detectada.', 'info')
        return redirect(url_for('ver_relatorio', id_caso=atividade_atual['caso_id']))
    caso = db.buscar_caso_por_id(atividade_atual['caso_id'])
    return render_template('editar_atividade.html', 
                           atividade=atividade_atual, 
                           caso=caso,
                           opcoes_atividade=config.LISTA_ATIVIDADES,
                           opcoes_situacao=config.LISTA_SITUACAO)

# --- ROTAS DE API ---
@app.route('/api/get-user-name/<string:codigo>')
def get_user_name(codigo):
    usuario = db.buscar_usuario_por_codigo(codigo)
    if usuario:
        return jsonify({'nome_completo': usuario['nome_completo']})
    else:
        return jsonify({'error': 'Usuário não encontrado'}), 404

@app.route('/api/atividade/<int:id_atividade>')
@login_required
def get_atividade_details(id_atividade):
    atividade = db.buscar_atividade_por_id(id_atividade)
    if atividade:
        return jsonify(atividade)
    else:
        return jsonify({'error': 'Atividade não encontrada'}), 404

if __name__ == '__main__':
    app.run(debug=True)