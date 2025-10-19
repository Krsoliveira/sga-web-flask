import os
import hashlib
import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, event, Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, scoped_session, joinedload
from sqlalchemy.inspection import inspect
from contextlib import contextmanager

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi definida.")

# --- Configuração do SQLAlchemy ---
engine = create_engine(DATABASE_URL)
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
ScopedSession = scoped_session(session_factory)

Base = declarative_base()

# --- FUNÇÃO HELPER PARA CONVERSÃO ---
def object_as_dict(obj):
    """Converte um objeto SQLAlchemy para um dicionário."""
    return {c.key: getattr(obj, c.key)
            for c in inspect(obj).mapper.column_attrs}

# --- Modelos de Tabela ---
class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True)
    codigo = Column(String(50), unique=True, nullable=False)
    nome_completo = Column(String(255), nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default='Auditor')
    gerente_id = Column(Integer, ForeignKey('usuarios.id'))
    
    atividades_realizadas = relationship("Atividade", back_populates="realizado_por")

class Caso(Base):
    __tablename__ = 'casos'
    id = Column(Integer, primary_key=True)
    titulo = Column(String(255), nullable=False)
    numero_relatorio = Column(String(50), unique=True)
    tipo = Column(String(100), nullable=False)
    data_inicio = Column(String(20), nullable=False)
    data_final = Column(String(20))
    status = Column(String(50), nullable=False)
    notas_revisao = Column(Text)
    categoria_id = Column(Integer, ForeignKey('categorias.id'))
    filial_id = Column(Integer, ForeignKey('filiais.id'))

    atividades = relationship("Atividade", back_populates="caso", cascade="all, delete-orphan")
    anexos = relationship("Anexo", back_populates="caso", cascade="all, delete-orphan")
    categoria = relationship("Categoria", back_populates="casos")
    filial = relationship("Filial", back_populates="casos")

class Filial(Base):
    __tablename__ = 'filiais'
    id = Column(Integer, primary_key=True)
    nome = Column(String(150), unique=True, nullable=False)
    cidade = Column(String(100))
    
    # Relacionamento para aceder a todos os casos (relatórios) desta filial
    casos = relationship("Caso", back_populates="filial")    

class Atividade(Base):
    __tablename__ = 'atividades'
    id = Column(Integer, primary_key=True)
    caso_id = Column(Integer, ForeignKey('casos.id'), nullable=False)
    atividade_desc = Column(Text)
    testes_realizados = Column(Text)
    observacao_resumo = Column(Text)
    nao_conformidade = Column(Text)
    recomendacao = Column(Text)
    data_registro = Column(String(20), nullable=False)
    situacao = Column(String(50))
    realizado_por_id = Column(Integer, ForeignKey('usuarios.id'))
    
    caso = relationship("Caso", back_populates="atividades")
    realizado_por = relationship("Usuario", back_populates="atividades_realizadas")

# --- Funções de Acesso ao Banco de Dados ---
@contextmanager
def get_db():
    session = ScopedSession()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        ScopedSession.remove()

def inicializar_banco():
    print(f"Tentando conectar ao banco de dados com a URL: {DATABASE_URL.split('@')[-1]}")
    print("Inicializando o banco de dados e criando tabelas...")
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso (se não existiam).")

def verificar_login(sess, codigo_usuario, senha):
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    # CORREÇÃO FINAL: Usando 'codigo', que é o nome correto do campo no modelo.
    usuario = sess.query(Usuario).filter_by(codigo=codigo_usuario, password_hash=senha_hash).first()
    return object_as_dict(usuario) if usuario else None

def buscar_usuario_por_codigo(sess, codigo_usuario):
    # CORREÇÃO FINAL: Usando 'codigo', que é o nome correto do campo no modelo.
    usuario_obj = sess.query(Usuario).filter_by(codigo=codigo_usuario).first()
    return object_as_dict(usuario_obj) if usuario_obj else None

def adicionar_usuario(sess, dados):
    try:
        nome = dados['nome_completo'].lower().split()
        username = f"{nome[0]}.{nome[-1]}" if len(nome) > 1 else nome[0]
        novo_usuario = Usuario(
            codigo=dados['codigo'],
            nome_completo=dados['nome_completo'],
            username=username,
            password_hash=hashlib.sha256(dados['senha'].encode()).hexdigest(),
            role=dados['role'],
            gerente_id=dados.get('gerente_id')
        )
        sess.add(novo_usuario)
        return True
    except Exception:
        sess.rollback()
        return False

def buscar_casos(sess):
    return sess.query(Caso).order_by(Caso.id.desc()).all()

def adicionar_novo_caso(sess, titulo, tipo, data_inicio, status):
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        numero_temporario = f"REL-{timestamp}"
        novo_caso = Caso(
            titulo=titulo,
            numero_relatorio=numero_temporario,
            tipo=tipo,
            data_inicio=str(data_inicio),
            status=status
        )
        sess.add(novo_caso)
        sess.flush()
        return novo_caso.id
    except Exception as e:
        print(f"ERRO em adicionar_novo_caso: {e}")
        return None

def buscar_caso_por_id(sess, caso_id):
    """
    Busca um único caso pelo seu ID, carregando TODOS os relacionamentos
    necessários para a aplicação (atividades, anexos, filial e categoria).
    """
    return sess.query(Caso).options(
        # Carrega as atividades e os seus usuários
        joinedload(Caso.atividades).joinedload(Atividade.realizado_por),
        # Carrega os anexos
        joinedload(Caso.anexos),
        # ADICIONADO: Carrega a filial associada ao caso
        joinedload(Caso.filial),
        # ADICIONADO: Carrega a categoria associada ao caso
        joinedload(Caso.categoria)
    ).filter_by(id=caso_id).first()

def salvar_atividade(sess, dados_da_atividade):
    try:
        nova_atividade = Atividade(**dados_da_atividade)
        sess.add(nova_atividade)
        return True
    except Exception as e:
        print(f"ERRO ao salvar atividade: {e}")
        return False

def buscar_atividade_por_id(sess, atividade_id):
    return sess.query(Atividade).options(
        joinedload(Atividade.realizado_por)
    ).filter_by(id=atividade_id).first()

# Adicione estas duas novas classes ao seu database.py

class Categoria(Base):
    __tablename__ = 'categorias'
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)

    # Relacionamentos
    atividades_padrao = relationship("AtividadePadrao", back_populates="categoria", cascade="all, delete-orphan")
    casos = relationship("Caso", back_populates="categoria")

class AtividadePadrao(Base):
    __tablename__ = 'atividades_padrao'
    id = Column(Integer, primary_key=True)
    descricao = Column(Text, nullable=False)
    
    # Chave estrangeira para ligar à categoria
    categoria_id = Column(Integer, ForeignKey('categorias.id'), nullable=False)
    
    # Relacionamento
    categoria = relationship("Categoria", back_populates="atividades_padrao")

def buscar_todos_usuarios(sess):
    return sess.query(Usuario).order_by(Usuario.nome_completo).all()

def buscar_usuario_por_id(sess, user_id):
    return sess.get(Usuario, user_id)

def atualizar_usuario(sess, user_id, novos_dados):
    try:
        usuario = sess.get(Usuario, user_id)
        if not usuario:
            return False
        for campo, valor in novos_dados.items():
            if campo == 'senha' and valor:
                valor_hash = hashlib.sha256(valor.encode()).hexdigest()
                setattr(usuario, 'password_hash', valor_hash)
            elif campo != 'senha':
                setattr(usuario, campo, valor)
        return True
    except Exception as e:
        print(f"ERRO ao atualizar usuário: {e}")
        return False
    
def atualizar_relatorio(sess, caso_id, novos_dados):
    """
    Atualiza os dados de um relatório (caso) existente no banco de dados.
    """
    try:
        # Busca o caso que queremos atualizar.
        caso = sess.get(Caso, caso_id)
        if not caso:
            return False # Retorna falha se o caso não for encontrado.

        # Itera sobre o dicionário de novos dados e atualiza o objeto.
        for campo, valor in novos_dados.items():
            setattr(caso, campo, valor)
        
        return True
    except Exception as e:
        print(f"ERRO ao atualizar relatório: {e}")
        return False
    
# Adiona anexos relacionados a casos

class Anexo(Base):
    __tablename__ = 'anexos'
    id = Column(Integer, primary_key=True)
    nome_original = Column(String(255), nullable=False)
    nome_seguro = Column(String(255), unique=True, nullable=False)
    caminho = Column(String(512), nullable=False)
    data_upload = Column(String(20), nullable=False, default=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # Chave estrangeira para ligar o anexo a um caso
    caso_id = Column(Integer, ForeignKey('casos.id'), nullable=False)
    
    # Relacionamento que permite aceder ao objeto 'Caso' a partir de um 'Anexo'
    caso = relationship("Caso", back_populates="anexos")


def adicionar_anexo(sess, caso_id, nome_original, nome_seguro, caminho):
    """Cria o registo de um novo anexo no banco de dados."""
    try:
        novo_anexo = Anexo(
            caso_id=caso_id,
            nome_original=nome_original,
            nome_seguro=nome_seguro,
            caminho=caminho
        )
        sess.add(novo_anexo)
        return True
    except Exception as e:
        print(f"ERRO ao adicionar anexo: {e}")
        return False

# Adicione este novo conjunto de funções ao seu database.py

def buscar_todas_categorias(sess):
    """Busca todas as categorias, ordenadas por nome."""
    return sess.query(Categoria).order_by(Categoria.nome).all()

def buscar_categoria_por_id(sess, categoria_id):
    """Busca uma única categoria pelo seu ID."""
    return sess.get(Categoria, categoria_id)

def adicionar_categoria(sess, nome):
    """Adiciona uma nova categoria."""
    try:
        nova_categoria = Categoria(nome=nome)
        sess.add(nova_categoria)
        return True
    except Exception as e:
        print(f"ERRO ao adicionar categoria: {e}")
        return False

def atualizar_categoria(sess, categoria_id, nome):
    """Atualiza o nome de uma categoria existente."""
    try:
        categoria = sess.get(Categoria, categoria_id)
        if categoria:
            categoria.nome = nome
            return True
        return False
    except Exception as e:
        print(f"ERRO ao atualizar categoria: {e}")
        return False

def deletar_categoria(sess, categoria_id):
    """Deleta uma categoria e todas as atividades padrão associadas a ela."""
    try:
        categoria = sess.get(Categoria, categoria_id)
        if categoria:
            sess.delete(categoria)
            return True
        return False
    except Exception as e:
        print(f"ERRO ao deletar categoria: {e}")
        return False

def buscar_todas_filiais(sess):
    """Busca todas as filiais, ordenadas por nome."""
    return sess.query(Filial).order_by(Filial.nome).all()

def buscar_filial_por_id(sess, filial_id):
    """Busca uma única filial pelo seu ID."""
    return sess.get(Filial, filial_id)

def adicionar_filial(sess, nome, cidade):
    """Adiciona uma nova filial."""
    try:
        nova_filial = Filial(nome=nome, cidade=cidade)
        sess.add(nova_filial)
        return True
    except Exception as e:
        print(f"ERRO ao adicionar filial: {e}")
        return False

def atualizar_filial(sess, filial_id, nome, cidade):
    """Atualiza os dados de uma filial existente."""
    try:
        filial = sess.get(Filial, filial_id)
        if filial:
            filial.nome = nome
            filial.cidade = cidade
            return True
        return False
    except Exception as e:
        print(f"ERRO ao atualizar filial: {e}")
        return False

def deletar_filial(sess, filial_id):
    """Deleta uma filial. ATENÇÃO: Pode falhar se houver relatórios associados."""
    try:
        filial = sess.get(Filial, filial_id)
        if filial:
            sess.delete(filial)
            return True
        return False
    except Exception as e:
        print(f"ERRO ao deletar filial: {e}")
        return False    
    
# Adicione ou substitua esta função no seu database.py

def criar_caso_com_atividades_padrao(sess, categoria_id, filial_id, realizado_por_id):
    """
    Cria um novo Caso numa Filial específica e o popula com as Atividades Padrão
    da Categoria selecionada. Retorna o ID do novo Caso.
    """
    try:
        # 1. Busca os dados necessários
        categoria = sess.query(Categoria).options(joinedload(Categoria.atividades_padrao)).filter_by(id=categoria_id).one()
        filial = sess.get(Filial, filial_id)

        # 2. Cria o novo Caso (Relatório)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        novo_caso = Caso(
            titulo=f"Novo Relatório - {categoria.nome} ({filial.nome})",
            numero_relatorio=f"REL-{timestamp}",
            tipo=categoria.nome,
            data_inicio=str(datetime.date.today()),
            status="Em Elaboração",
            categoria_id=categoria_id,
            filial_id=filial_id  # <-- Guardando a Filial!
        )
        sess.add(novo_caso)
        
        # 3. Cria as Atividades reais baseadas nas Atividades Padrão
        if categoria.atividades_padrao:
            for atividade_padrao in categoria.atividades_padrao:
                nova_atividade = Atividade(
                    caso=novo_caso,
                    atividade_desc=atividade_padrao.descricao,
                    situacao="Pendente",
                    realizado_por_id=realizado_por_id,
                    data_registro=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                sess.add(nova_atividade)
        
        sess.flush()
        return novo_caso.id

    except Exception as e:
        print(f"ERRO ao criar caso com atividades padrão: {e}")
        return None    

# Adicione esta nova função ao seu arquivo database.py

def buscar_historico_atividade_na_filial(sess, atividade_atual):
    """
    Busca o histórico das últimas 3 ocorrências de uma atividade na mesma filial.
    
    Recebe o objeto da atividade ATUAL para usar como referência.
    Retorna uma lista de objetos de atividades ANTERIORES.
    """
    try:
        # Pega as "coordenadas" da atividade atual
        descricao_alvo = atividade_atual.atividade_desc
        filial_alvo_id = atividade_atual.caso.filial_id
        caso_atual_id = atividade_atual.caso.id

        # Constrói a consulta de histórico
        historico = sess.query(Atividade)\
            .join(Atividade.caso)\
            .options(joinedload(Atividade.caso)) \
            .filter(
                Atividade.atividade_desc == descricao_alvo,
                Caso.filial_id == filial_alvo_id,
                Caso.id < caso_atual_id
            )\
            .order_by(Caso.id.desc())\
            .limit(3)\
            .all()
        
        return historico

    except Exception as e:
        print(f"ERRO ao buscar histórico da atividade: {e}")
        return [] # Retorna uma lista vazia em caso de erro

# Adicione esta nova função ao seu arquivo database.py

def buscar_historico_atividade_global(sess, atividade_atual):
    """
    Busca o histórico das últimas 5 ocorrências de uma atividade em QUALQUER filial.
    
    Recebe o objeto da atividade ATUAL para usar como referência.
    Retorna uma lista de objetos de atividades ANTERIORES.
    """
    try:
        # Pega as "coordenadas" da atividade atual
        descricao_alvo = atividade_atual.atividade_desc
        caso_atual_id = atividade_atual.caso.id

        # Constrói a consulta de histórico global
        historico = sess.query(Atividade)\
            .join(Atividade.caso)\
            .join(Caso.filial)\
            .options(
                joinedload(Atividade.caso).joinedload(Caso.filial),
                joinedload(Atividade.realizado_por)
            )\
            .filter(
                Atividade.atividade_desc == descricao_alvo,
                Caso.id < caso_atual_id
            )\
            .order_by(Caso.id.desc())\
            .limit(5)\
            .all()
            
        return historico

    except Exception as e:
        print(f"ERRO ao buscar histórico global da atividade: {e}")
        return []

if __name__ == '__main__':
    inicializar_banco()