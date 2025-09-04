import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import database as db
import config

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# --- DECORADORES ---
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
            if session['dados_usuario'].get('role') not in roles:
                flash('Você não tem permissão para aceder a esta página.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
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


# --- ROTAS PRINCIPAIS DO SISTEMA ---
@app.route('/dashboard')
@login_required
def dashboard():
    lista_de_casos = db.buscar_casos()
    return render_template('dashboard.html', casos=lista_de_casos)

@app.route('/relatorio/novo', methods=['POST'])
@login_required
def novo_relatorio():
    hoje = db.date.today().strftime("%Y-%m-%d")
    novo_id = db.adicionar_novo_caso("Novo Relatório (preencher)", "Auditoria", hoje, "PLANEJADO")
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
    lista_atividades = db.buscar_atividades_completas_por_caso_id(id_caso)
    if not dados_caso:
        flash(f'Relatório com ID {id_caso} não encontrado.', 'danger')
        return redirect(url_for('dashboard'))
    atividade_para_editar = None
    id_atividade_edicao = request.args.get('editar', type=int)
    if id_atividade_edicao:
        atividade_para_editar = db.buscar_atividade_por_id(id_atividade_edicao)
    return render_template('relatorio.html', caso=dados_caso, atividades=lista_atividades, atividade_edicao=atividade_para_editar, opcoes_atividade=config.LISTA_ATIVIDADES, opcoes_situacao=config.LISTA_SITUACAO)

@app.route('/relatorio/deletar/<int:id_caso>', methods=['POST'])
@login_required
def deletar_relatorio_rota(id_caso):
    codigo_usuario = session['dados_usuario']['codigo']
    nome_usuario = session['dados_usuario']['nome']
    if db.deletar_relatorio_e_registrar_log(id_caso, codigo_usuario, nome_usuario):
        flash(f'Relatório ID {id_caso} deletado com sucesso.', 'success')
    else:
        flash(f'Erro ao deletar o relatório ID {id_caso}.', 'danger')
    return redirect(url_for('dashboard'))


# --- ROTAS PARA GERENCIAR ATIVIDADES ---
@app.route('/relatorio/<int:id_caso>/atividade/salvar', methods=['POST'])
@login_required
def salvar_atividade_rota(id_caso):
    id_atividade = request.form.get('id_atividade')
    dados = {
        "atividade_desc": request.form.get('atividade_desc'),
        "testes_realizados": request.form.get('testes_realizados'),
        "extensao_exames": request.form.get('extensao_exames'),
        "criterio_amostragem": request.form.get('criterio_amostragem'),
        "periodo_inicio": request.form.get('periodo_inicio'),
        "periodo_fim": request.form.get('periodo_fim'),
        "situacao": request.form.get('situacao'),
        "observacao_resumo": request.form.get('observacao_resumo')
    }
    erros = []
    if not dados.get('atividade_desc'):
        erros.append("O campo 'Atividade' é obrigatório.")
    if not dados.get('situacao'):
        erros.append("O campo 'Situação da Atividade' é obrigatório.")
    inicio = dados.get('periodo_inicio')
    fim = dados.get('periodo_fim')
    if inicio and fim and inicio > fim:
        erros.append("A data 'De' do período não pode ser posterior à data 'Até'.")
    if erros:
        for erro in erros:
            flash(erro, 'danger')
        return redirect(url_for('ver_relatorio', id_caso=id_caso))
    sucesso = False
    if id_atividade:
        sucesso = db.atualizar_atividade(id_atividade, dados)
        if sucesso:
            flash('Atividade atualizada com sucesso!', 'success')
    else:
        dados.update({
            "caso_id": id_caso,
            "realizado_por_id": session['dados_usuario']['id'],
            "data_registro": db.date.today().strftime("%Y-%m-%d"),
            "nao_conformidade": "", "reincidente": 0, "recomendacao": "", "data_p_solucao": ""
        })
        sucesso = db.salvar_atividade(dados)
        if sucesso:
            flash('Nova atividade adicionada com sucesso!', 'success')
    if not sucesso:
        flash('Erro ao salvar a atividade.', 'danger')
    return redirect(url_for('ver_relatorio', id_caso=id_caso))

@app.route('/relatorio/atividade/deletar/<int:id_atividade>', methods=['POST'])
@login_required
def deletar_atividade_rota(id_atividade):
    id_caso = request.form.get('id_caso')
    if db.deletar_atividade_por_id(id_atividade):
        flash(f'Atividade ID {id_atividade} deletada com sucesso.', 'success')
    else:
        flash(f'Erro ao deletar a atividade ID {id_atividade}.', 'danger')
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
        codigo = request.form.get('codigo', '').strip().upper()
        nome = request.form.get('nome_completo', '').strip().upper()
        senha = request.form.get('senha')
        role = request.form.get('role')
        username = ""
        if nome:
            partes_nome = nome.lower().split()
            primeiro_nome = partes_nome[0]
            username = f"{primeiro_nome}.{partes_nome[-1]}" if len(partes_nome) > 1 else primeiro_nome
        if not all([codigo, nome, senha, role]):
            flash('Todos os campos são obrigatórios.', 'danger')
            return redirect(url_for('criar_usuario'))
        sucesso = db.adicionar_usuario(codigo, nome, username, senha, role)
        if sucesso:
            flash(f'Usuário "{username}" criado com sucesso!', 'success')
            return redirect(url_for('gestao_usuarios'))
        else:
            flash(f'Erro: O código "{codigo}" ou o username gerado "{username}" já existe.', 'danger')
            return redirect(url_for('criar_usuario'))
    return render_template('criar_usuario.html', roles=config.LISTA_ROLES)

@app.route('/admin/usuario/editar/<int:user_id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(user_id):
    usuario_logado = session['dados_usuario']
    if usuario_logado['role'] != 'Admin' and usuario_logado['id'] != user_id:
        flash('Você só tem permissão para editar o seu próprio perfil.', 'danger')
        return redirect(url_for('dashboard'))

    usuario_para_editar = db.buscar_usuario_por_id(user_id)
    if not usuario_para_editar:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('gestao_usuarios'))
    
    if request.method == 'POST':
        dados_atualizados = {
            'codigo': request.form.get('codigo', '').strip().upper(),
            'nome_completo': request.form.get('nome_completo', '').strip().upper(),
            'username': request.form.get('username', '').strip(),
            'role': request.form.get('role'),
            'nova_senha': request.form.get('nova_senha'),
            'confirmar_senha': request.form.get('confirmar_senha')
        }
        if dados_atualizados['nova_senha'] != dados_atualizados['confirmar_senha']:
            flash('As novas senhas não coincidem. Tente novamente.', 'danger')
            return redirect(url_for('editar_usuario', user_id=user_id))
        
        # Regra de negócio: Apenas Admins podem mudar o role de outros
        if usuario_logado['role'] != 'Admin':
            dados_atualizados['role'] = usuario_para_editar['role']

        sucesso = db.atualizar_usuario(user_id, dados_atualizados)
        if sucesso:
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('gestao_usuarios'))
        else:
            flash('Erro ao atualizar. O código ou username pode já estar em uso por outro usuário.', 'danger')
            return redirect(url_for('editar_usuario', user_id=user_id))

    return render_template('editar_usuario.html', 
                           usuario=usuario_para_editar, 
                           roles=config.LISTA_ROLES)


if __name__ == '__main__':
    app.run(debug=True)