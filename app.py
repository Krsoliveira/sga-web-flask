import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import database as db
import config

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
# Configuração da chave secreta para sessões
app.secret_key = os.getenv('SECRET_KEY')


# --- DECORADOR PARA VERIFICAÇÃO DE LOGIN ---
def login_required(f):
    """
    Decorador que verifica se o usuário está logado na sessão.
    Se não estiver, redireciona para a página de login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'dados_usuario' not in session:
            flash('Por favor, faça o login para acessar esta página.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


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

# --- ROTAS PRINCIPAIS ---
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
    
    # Renderiza a página de relatório, passando os dados do caso e as atividades
    return render_template(
        'relatorio.html', 
        caso=dados_caso, 
        atividades=lista_atividades, 
        atividade_edicao=atividade_para_editar,
        opcoes_atividade=config.LISTA_ATIVIDADES,  
        opcoes_situacao=config.LISTA_SITUACAO      
    )

@app.route('/relatorio/deletar/<int:id_caso>', methods=['POST'])
@login_required
def deletar_relatorio_rota(id_caso):
    codigo_usuario = session['dados_usuario'][0]
    nome_usuario = session['dados_usuario'][1]

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
        "periodo_situacao": request.form.get('periodo_situacao'),
        "situacao": request.form.get('situacao'),
        "observacao_resumo": request.form.get('observacao_resumo')
    }

    # --- INÍCIO DO BLOCO DE VALIDAÇÃO ---
    erros = []
    if not dados.get('atividade_desc'):
        erros.append("O campo 'Atividade' é obrigatório.")
    if not dados.get('situacao'):
        erros.append("O campo 'Situação da Atividade' é obrigatório.")
    

    if erros:
        for erro in erros:
            flash(erro, 'danger')
       
        return redirect(url_for('ver_relatorio', id_caso=id_caso))
    # --- FIM DO BLOCO DE VALIDAÇÃO ---

    # Se a validação passar, o código continua a execução normal.
    sucesso = False
    if id_atividade:
        sucesso = db.atualizar_atividade(id_atividade, dados)
        if sucesso:
            flash('Atividade atualizada com sucesso!', 'success')
    else:
        dados.update({
            "caso_id": id_caso,
            "realizado_por": session['dados_usuario'][1],
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


if __name__ == '__main__':
    app.run(debug=True)