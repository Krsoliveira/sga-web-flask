import os
import hashlib
import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, Float, Boolean
# Importação completa e corrigida
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload, scoped_session 
from sqlalchemy.inspection import inspect
from contextlib import contextmanager
import sqlalchemy 

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi definida.")

# --- Configuração do SQLAlchemy ---
engine = create_engine(DATABASE_URL)
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# Criação correta da Scoped Session
ScopedSession = scoped_session(session_factory)

Base = declarative_base()

# --- Gerenciador de Contexto para Banco de Dados ---
@contextmanager
def get_db():
    """
    Fornece uma sessão transacional.
    Usa 'ScopedSession' para garantir thread-safety.
    """
    session = ScopedSession()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
        # Remove a sessão do registro para evitar vazamento de memória ou dados antigos
        ScopedSession.remove()

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Banco de dados inicializado.")
    
# Função auxiliar para converter objetos SQLAlchemy em Dicionários
def object_as_dict(obj):
    return {c.key: getattr(obj, c.key)
            for c in inspect(obj).mapper.column_attrs}

# --- Modelos (Tabelas) ---

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True)
    codigo = Column(String(50), unique=True, nullable=False)
    nome_completo = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=False) # Gerado automaticamente
    senha_hash = Column(String(128), nullable=False)
    role = Column(String(20), default='Auditor') # 'Admin', 'Manager', 'Auditor'
    
    # Auto-relacionamento para Hierarquia (Gerente -> Auditores)
    gerente_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    equipe = relationship("Usuario", backref=sqlalchemy.orm.backref('gerente', remote_side=[id]))

class Filial(Base):
    __tablename__ = 'filiais'
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)
    cidade = Column(String(100), nullable=False)
    
    # Relacionamento com Casos
    casos = relationship("Caso", back_populates="filial")

class Categoria(Base):
    __tablename__ = 'categorias'
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)
    
    # Relacionamento com Modelos de Atividade
    atividades_padrao = relationship("AtividadePadrao", back_populates="categoria", cascade="all, delete-orphan")
    # Relacionamento com Casos gerados
    casos = relationship("Caso", back_populates="categoria")

class AtividadePadrao(Base):
    __tablename__ = 'atividades_padrao'
    id = Column(Integer, primary_key=True)
    descricao = Column(Text, nullable=False)
    
    # NOVO CAMPO: POP (Procedimento Operacional Padrão)
    instrucoes = Column(Text, nullable=True) 
    
    categoria_id = Column(Integer, ForeignKey('categorias.id'), nullable=False)
    categoria = relationship("Categoria", back_populates="atividades_padrao")

class Caso(Base):
    __tablename__ = 'casos'
    id = Column(Integer, primary_key=True)
    data_inicio = Column(String(20)) # Formato YYYY-MM-DD
    data_final = Column(String(20), nullable=True)
    status = Column(String(50), default='Em Elaboração')
    contexto_apresentacao = Column(Text, nullable=True) # Notas da reunião de conclusão
    
    # Notas de revisão (se rejeitado/aprovado com ressalvas)
    notas_revisao = Column(Text, nullable=True)
    
    # Chaves Estrangeiras
    categoria_id = Column(Integer, ForeignKey('categorias.id'), nullable=True)
    filial_id = Column(Integer, ForeignKey('filiais.id'), nullable=True)
    realizado_por_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    
    # Relacionamentos
    categoria = relationship("Categoria", back_populates="casos")
    filial = relationship("Filial", back_populates="casos")
    realizado_por = relationship("Usuario", foreign_keys=[realizado_por_id])
    
    # Relacionamento com Atividades (O coração do relatório)
    atividades = relationship("Atividade", back_populates="caso", cascade="all, delete-orphan")
    
    # Relacionamento com Anexos
    anexos = relationship("Anexo", back_populates="caso", cascade="all, delete-orphan")

    @property
    def numero_relatorio(self):
        # Gera algo como "2023.001" baseado no ID
        ano = datetime.datetime.now().year
        return f"{ano}.{self.id:03d}"
        
    @property
    def numero_relatorio_display(self):
        """
        Retorna uma string formatada bonita para exibir no PDF e na Lista.
        Ex: 2025.005 10/2025 - LOJA X
        """
        ano_atual = datetime.datetime.now().year
        mes_atual = datetime.datetime.now().month
        nome_filial = self.filial.nome if self.filial else "GERAL"
        return f"{ano_atual}.{self.id:03d} {mes_atual:02d}/{ano_atual} - {nome_filial}"

class Anexo(Base):
    __tablename__ = 'anexos'
    id = Column(Integer, primary_key=True)
    nome_arquivo = Column(String(255), nullable=False) # Nome original
    caminho_arquivo = Column(String(500), nullable=False) # Caminho salvo no servidor
    nome_seguro = Column(String(255), nullable=False) # Nome seguro gerado
    data_upload = Column(String(20))
    
    caso_id = Column(Integer, ForeignKey('casos.id'), nullable=False)
    caso = relationship("Caso", back_populates="anexos")    

class Atividade(Base):
    __tablename__ = 'atividades'
    id = Column(Integer, primary_key=True)
    atividade_desc = Column(Text, nullable=False)
    testes_realizados = Column(Text, nullable=True)
    
    # Resultado da Auditoria
    observacao_resumo = Column(Text, nullable=True)
    nao_conformidade = Column(Text, nullable=True)
    recomendacao = Column(Text, nullable=True)
    situacao = Column(String(50), nullable=True) # "Conforme", "Não Conforme", etc.
    
    # Campos de Auditoria
    data_registro = Column(String(20))
    
    # NOVOS CAMPOS TÉCNICOS
    periodo_inicio = Column(String(20), nullable=True)
    periodo_fim = Column(String(20), nullable=True)
    extensao_exames = Column(String(200), nullable=True) # Ex: "100% das notas"
    criterio_amostragem = Column(Text, nullable=True)    # Ex: "Aleatório"
    
    # NOVO CAMPO: POP (Copiado da AtividadePadrao)
    instrucoes = Column(Text, nullable=True)
    
    caso_id = Column(Integer, ForeignKey('casos.id'), nullable=False)
    caso = relationship("Caso", back_populates="atividades")
    
    realizado_por_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    realizado_por = relationship("Usuario")

# --- Funções de Autenticação e Usuário ---

def adicionar_usuario(session, dados):
    try:
        # Gera username: primeiro_nome.ultimo_nome (ex: joao.silva)
        nomes = dados['nome_completo'].lower().split()
        if len(nomes) > 1:
            username_base = f"{nomes[0]}.{nomes[-1]}"
        else:
            username_base = nomes[0]
            
        # Verifica duplicidade simples (pode ser melhorado)
        username = username_base
        contador = 1
        while session.query(Usuario).filter_by(username=username).first():
            username = f"{username_base}{contador}"
            contador += 1
            
        senha_hash = hashlib.sha256(dados['senha'].encode()).hexdigest()
        
        novo_usuario = Usuario(
            codigo=dados['codigo'],
            nome_completo=dados['nome_completo'],
            username=username,
            senha_hash=senha_hash,
            role=dados.get('role', 'Auditor'),
            gerente_id=dados.get('gerente_id')
        )
        session.add(novo_usuario)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Erro ao criar usuário: {e}")
        return False

def verificar_login(session, codigo, senha):
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    usuario = session.query(Usuario).filter_by(codigo=codigo, senha_hash=senha_hash).first()
    if usuario:
        # Retorna um dicionário simples para guardar na sessão do Flask
        return {'id': usuario.id, 'nome': usuario.nome_completo, 'role': usuario.role}
    return None

def buscar_usuario_por_id(session, user_id):
    return session.query(Usuario).filter_by(id=user_id).first()

def buscar_todos_usuarios(session):
    return session.query(Usuario).all()

def buscar_usuario_por_codigo(session, codigo):
    usuario = session.query(Usuario).filter_by(codigo=codigo).first()
    if usuario:
        return object_as_dict(usuario)
    return None

def atualizar_usuario(session, user_id, dados_novos):
    try:
        usuario = session.query(Usuario).filter_by(id=user_id).first()
        if not usuario:
            return False
            
        if 'nome_completo' in dados_novos: usuario.nome_completo = dados_novos['nome_completo']
        if 'codigo' in dados_novos: usuario.codigo = dados_novos['codigo']
        if 'role' in dados_novos: usuario.role = dados_novos['role']
        if 'username' in dados_novos: usuario.username = dados_novos['username']
        if 'gerente_id' in dados_novos: usuario.gerente_id = dados_novos['gerente_id']
        
        if 'senha' in dados_novos and dados_novos['senha']:
            usuario.senha_hash = hashlib.sha256(dados_novos['senha'].encode()).hexdigest()
            
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Erro ao atualizar usuário: {e}")
        return False    
    
# --- Funções de Negócio (Relatórios) ---

def buscar_casos(session):
    """
    Retorna todos os casos, já carregando as relações para evitar erros.
    CORREÇÃO: Usando 'realizado_por' em vez de 'responsavel'.
    """
    return session.query(Caso).options(
        joinedload(Caso.categoria),
        joinedload(Caso.filial),
        joinedload(Caso.realizado_por) 
    ).all()

def buscar_caso_por_id(session, caso_id):
    """
    Busca um caso completo com TODAS as suas relações carregadas.
    CORREÇÃO: Usando 'realizado_por' e 'joinedload' para atividades.
    """
    return session.query(Caso).options(
        joinedload(Caso.categoria),
        joinedload(Caso.filial),
        joinedload(Caso.realizado_por),
        joinedload(Caso.atividades).joinedload(Atividade.realizado_por),
        joinedload(Caso.anexos)
    ).filter_by(id=caso_id).first()

def buscar_atividade_por_id(session, atividade_id):
    return session.query(Atividade).options(
        joinedload(Atividade.realizado_por)
    ).filter_by(id=atividade_id).first()

def deletar_caso(session, caso_id):
    """
    Remove um caso completo, incluindo atividades, anexos do banco
    E os arquivos físicos da pasta de uploads.
    """
    try:
        caso = session.query(Caso).filter_by(id=caso_id).first()
        if not caso:
            return False

        # 1. Apagar arquivos físicos dos anexos
        for anexo in caso.anexos:
            if anexo.caminho_arquivo and os.path.exists(anexo.caminho_arquivo):
                try:
                    os.remove(anexo.caminho_arquivo)
                except Exception as e:
                    print(f"Erro ao apagar arquivo físico {anexo.caminho_arquivo}: {e}")

        # 2. Ao deletar o Caso, o SQLAlchemy deve apagar as Atividades e Anexos (Cascade)
        session.delete(caso)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Erro ao deletar caso: {e}")
        return False

# --- (Restante das funções auxiliares, como buscar filiais, categorias, etc) ---
def buscar_todas_categorias(session):
    return session.query(Categoria).all()

def buscar_todas_filiais(session):
    return session.query(Filial).all()

def buscar_categoria_por_id(session, id):
    return session.query(Categoria).filter_by(id=id).first()

def buscar_filial_por_id(session, id):
    return session.query(Filial).filter_by(id=id).first()

def criar_caso_com_atividades_padrao(session, categoria_id, filial_id, realizado_por_id):
    try:
        categoria = session.query(Categoria).filter_by(id=categoria_id).first()
        if not categoria: return None
        
        # Cria o caso
        novo_caso = Caso(
            data_inicio=datetime.datetime.now().strftime("%Y-%m-%d"),
            categoria_id=categoria_id,
            filial_id=filial_id,
            realizado_por_id=realizado_por_id,
            status='Em Elaboração'
        )
        session.add(novo_caso)
        session.flush() # Garante que novo_caso ganhe um ID
        
        # Copia atividades padrão
        for atividade_padrao in categoria.atividades_padrao:
            nova_atividade = Atividade(
                caso=novo_caso,
                atividade_desc=atividade_padrao.descricao,
                instrucoes=atividade_padrao.instrucoes, # Copia o manual POP
                situacao="Pendente",
                data_registro=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            session.add(nova_atividade)
            
        session.commit()
        return novo_caso.id
    except Exception as e:
        session.rollback()
        print(f"Erro ao criar caso: {e}")
        return None

def salvar_atividade(session, dados):
    try:
        # Verifica se já existe atividade (lógica simplificada para insert novo)
        nova_atv = Atividade(**dados)
        session.add(nova_atv)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Erro: {e}")
        return False

def atualizar_atividade(session, id_atividade, dados_atualizados):
    try:
        session.query(Atividade).filter_by(id=id_atividade).update(dados_atualizados)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Erro ao atualizar atividade: {e}")
        return False

def atualizar_relatorio(session, id_caso, dados_atualizados):
    try:
        session.query(Caso).filter_by(id=id_caso).update(dados_atualizados)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Erro ao atualizar relatorio: {e}")
        return False
        
def adicionar_anexo(session, caso_id, nome_orig, nome_seguro, caminho):
    try:
        novo = Anexo(
            nome_arquivo=nome_orig,
            nome_seguro=nome_seguro,
            caminho_arquivo=caminho,
            data_upload=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            caso_id=caso_id
        )
        session.add(novo)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Erro anexo: {e}")
        return False

def adicionar_categoria(session, nome):
    try:
        nova = Categoria(nome=nome)
        session.add(nova)
        session.commit()
        return True
    except:
        session.rollback()
        return False

def adicionar_filial(session, nome, cidade):
    try:
        nova = Filial(nome=nome, cidade=cidade)
        session.add(nova)
        session.commit()
        return True
    except:
        session.rollback()
        return False

def atualizar_categoria(session, id, nome):
    try:
        cat = session.query(Categoria).filter_by(id=id).first()
        if cat:
            cat.nome = nome
            session.commit()
            return True
        return False
    except:
        session.rollback()
        return False

def deletar_categoria(session, id):
    try:
        cat = session.query(Categoria).filter_by(id=id).first()
        if cat:
            session.delete(cat)
            session.commit()
            return True
        return False
    except:
        session.rollback()
        return False

def atualizar_filial(session, id, nome, cidade):
    try:
        fil = session.query(Filial).filter_by(id=id).first()
        if fil:
            fil.nome = nome
            fil.cidade = cidade
            session.commit()
            return True
        return False
    except:
        session.rollback()
        return False

def deletar_filial(session, id):
    try:
        fil = session.query(Filial).filter_by(id=id).first()
        if fil:
            session.delete(fil)
            session.commit()
            return True
        return False
    except:
        session.rollback()
        return False
        
# --- Funções para Histórico (Usadas na API) ---

def buscar_historico_atividade_na_filial(session, atividade_atual):
    """
    Busca atividades anteriores com a mesma descrição, na mesma filial, mas de casos diferentes.
    """
    if not atividade_atual.caso or not atividade_atual.caso.filial_id:
        return []

    return session.query(Atividade).join(Caso).filter(
        Atividade.atividade_desc == atividade_atual.atividade_desc, # Mesma descrição
        Caso.filial_id == atividade_atual.caso.filial_id,           # Mesma filial
        Caso.id != atividade_atual.caso_id,                         # Não é o caso atual
        # Opcional: Apenas casos concluídos ou anteriores? Por enquanto traz tudo.
    ).order_by(Caso.id.desc()).limit(5).all() # Traz os últimos 5

def buscar_historico_atividade_global(session, atividade_atual):
    """
    Busca atividades anteriores com a mesma descrição, em TODAS as filiais.
    """
    return session.query(Atividade).join(Caso).filter(
        Atividade.atividade_desc == atividade_atual.atividade_desc, # Mesma descrição
        Caso.id != atividade_atual.caso_id                          # Não é o caso atual
    ).order_by(Caso.id.desc()).limit(10).all() # Traz os últimos 10

if __name__ == '__main__':
    # Cria as tabelas se não existirem
    init_db()
    
    # Opcional: Cria um usuário Admin padrão se o banco estiver vazio
    try:
        with get_db() as sess:
            if not sess.query(Usuario).filter_by(codigo='ADMIN').first():
                print("Criando usuário ADMIN padrão...")
                # Criação manual para garantir o primeiro acesso
                admin = Usuario(
                    codigo='ADMIN',
                    nome_completo='ADMINISTRADOR DO SISTEMA',
                    username='admin',
                    senha_hash=hashlib.sha256('admin123'.encode()).hexdigest(),
                    role='Admin'
                )
                sess.add(admin)
                sess.commit()
                print("Usuário ADMIN criado (Senha: admin123).")
    except Exception as e:
        print(f"Erro ao verificar/criar admin: {e}")   