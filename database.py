import os
import datetime
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload, scoped_session 
from sqlalchemy.inspection import inspect
from contextlib import contextmanager
import sqlalchemy 

# --- Carregamento de Ambiente ---
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi definida.")

# --- Configuração do SQLAlchemy ---
engine = create_engine(DATABASE_URL)
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
ScopedSession = scoped_session(session_factory)

Base = declarative_base()

# --- Gerenciador de Contexto (Context Manager) ---
@contextmanager
def get_db():
    """
    Fornece uma sessão transacional segura.
    Usa 'yield' para entregar a sessão e 'finally' para fechar.
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
        ScopedSession.remove()

def init_db():
    """Cria as tabelas no banco de dados se não existirem."""
    Base.metadata.create_all(bind=engine)
    print("Banco de dados inicializado com sucesso.")
    
def object_as_dict(obj):
    """Converte um objeto SQLAlchemy num dicionário Python."""
    return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

# --- MODELOS (TABELAS) ---

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True)
    codigo = Column(String(50), unique=True, nullable=False)
    nome_completo = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    senha_hash = Column(String(256), nullable=False)
    role = Column(String(20), default='Auditor') # Admin, Manager, Auditor
    
    # Auto-relacionamento (Gerente -> Equipe)
    gerente_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    equipe = relationship("Usuario", backref=sqlalchemy.orm.backref('gerente', remote_side=[id]))

class Filial(Base):
    __tablename__ = 'filiais'
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)
    cidade = Column(String(100), nullable=False)
    
    # Relacionamento: Uma filial tem muitos casos
    casos = relationship("Caso", back_populates="filial")

class Categoria(Base):
    __tablename__ = 'categorias'
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)
    
    # Relacionamento com Atividades Padrão (Manuais/POPs)
    atividades_padrao = relationship("AtividadePadrao", back_populates="categoria", cascade="all, delete-orphan")
    
    # Relacionamento com Casos gerados
    casos = relationship("Caso", back_populates="categoria")

# === ESTRUTURA DE POP (BLOCOS) ===

class AtividadePadrao(Base):
    """
    Representa o cabeçalho de um manual (POP).
    Ex: 'Verificação de Extintores'
    """
    __tablename__ = 'atividades_padrao'
    id = Column(Integer, primary_key=True)
    titulo = Column(String(200), nullable=False) 
    
    # Status: 'Rascunho', 'Em Aprovação', 'Publicado'
    status = Column(String(50), default='Rascunho')
    
    # Autor do manual
    autor_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    autor = relationship("Usuario", foreign_keys=[autor_id])
    
    categoria_id = Column(Integer, ForeignKey('categorias.id'), nullable=False)
    categoria = relationship("Categoria", back_populates="atividades_padrao")
    
    # Os passos (blocos) do manual
    passos = relationship("PassoPOP", back_populates="atividade_padrao", cascade="all, delete-orphan", order_by="PassoPOP.ordem")

class PassoPOP(Base):
    """
    Representa um BLOCO individual de informação (Texto, Imagem, Alerta).
    """
    __tablename__ = 'passos_pop'
    id = Column(Integer, primary_key=True)
    tipo = Column(String(20), default='texto') # 'texto', 'imagem', 'alerta', 'titulo_secao'
    conteudo = Column(Text, nullable=True)     # O texto HTML ou o caminho da imagem
    ordem = Column(Integer, nullable=False)    # Sequência de exibição (1, 2, 3...)
    
    atividade_padrao_id = Column(Integer, ForeignKey('atividades_padrao.id'), nullable=False)
    atividade_padrao = relationship("AtividadePadrao", back_populates="passos") 

class Caso(Base):
    __tablename__ = 'casos'
    id = Column(Integer, primary_key=True)
    data_inicio = Column(String(20))
    data_final = Column(String(20), nullable=True)
    status = Column(String(50), default='Em Elaboração')
    
    # Campos de Texto Longo
    notas_revisao = Column(Text, nullable=True)
    contexto_apresentacao = Column(Text, nullable=True) # Notas da reunião final
    
    # Chaves Estrangeiras
    categoria_id = Column(Integer, ForeignKey('categorias.id'), nullable=True)
    filial_id = Column(Integer, ForeignKey('filiais.id'), nullable=True)
    realizado_por_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    
    # Relacionamentos
    categoria = relationship("Categoria", back_populates="casos")
    filial = relationship("Filial", back_populates="casos")
    realizado_por = relationship("Usuario", foreign_keys=[realizado_por_id])
    
    # Relacionamentos em Cascata (Se apagar o caso, apaga atividades e anexos)
    atividades = relationship("Atividade", back_populates="caso", cascade="all, delete-orphan")
    anexos = relationship("Anexo", back_populates="caso", cascade="all, delete-orphan")

    @property
    def numero_relatorio_display(self):
        """Formata o número do relatório para exibição (Ex: 2026.001)"""
        ano = datetime.datetime.now().year
        return f"{ano}.{self.id:03d}"

class Anexo(Base):
    __tablename__ = 'anexos'
    id = Column(Integer, primary_key=True)
    nome_arquivo = Column(String(255), nullable=False)
    caminho_arquivo = Column(String(500), nullable=False)
    nome_seguro = Column(String(255), nullable=False)
    data_upload = Column(String(20))
    
    caso_id = Column(Integer, ForeignKey('casos.id'), nullable=False)
    caso = relationship("Caso", back_populates="anexos") 

class Atividade(Base):
    __tablename__ = 'atividades'
    id = Column(Integer, primary_key=True)
    atividade_desc = Column(Text, nullable=False)
    
    # Link para o POP original
    atividade_padrao_id = Column(Integer, ForeignKey('atividades_padrao.id'), nullable=True)
    
    # Campos de Auditoria
    testes_realizados = Column(Text, nullable=True)
    observacao_resumo = Column(Text, nullable=True)
    
    # === CORREÇÃO: COLUNAS RESTAURADAS PARA EVITAR ERRO ===
    nao_conformidade = Column(Text, nullable=True)
    recomendacao = Column(Text, nullable=True)
    # ======================================================

    situacao = Column(String(50), nullable=True) 
    data_registro = Column(String(20))
    
    # Campos Técnicos
    periodo_inicio = Column(String(20), nullable=True)
    periodo_fim = Column(String(20), nullable=True)
    extensao_exames = Column(String(200), nullable=True)
    criterio_amostragem = Column(Text, nullable=True)
    
    caso_id = Column(Integer, ForeignKey('casos.id'), nullable=False)
    caso = relationship("Caso", back_populates="atividades")
    
    realizado_por_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    realizado_por = relationship("Usuario") 

# --- LÓGICA DE NEGÓCIO: USUÁRIOS ---

def adicionar_usuario(session, dados):
    try:
        # Gera username: joao.silva
        nomes = dados['nome_completo'].lower().split()
        username_base = f"{nomes[0]}.{nomes[-1]}" if len(nomes) > 1 else nomes[0]
        
        # Garante unicidade
        username = username_base
        contador = 1
        while session.query(Usuario).filter_by(username=username).first():
            username = f"{username_base}{contador}"
            contador += 1
            
        senha_hash = generate_password_hash(dados['senha'])

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
        print(f"Erro ao adicionar usuário: {e}")
        return False

def verificar_login(session, codigo, senha):
    usuario = session.query(Usuario).filter_by(codigo=codigo).first()
    if usuario and check_password_hash(usuario.senha_hash, senha):
        return {'id': usuario.id, 'nome': usuario.nome_completo, 'role': usuario.role}
    return None

def buscar_usuario_por_id(session, user_id):
    # O joinedload(Usuario.gerente) impede que o sistema trave ao tentar ler o gerente depois
    return session.query(Usuario).options(
        joinedload(Usuario.gerente)
    ).filter_by(id=user_id).first()

def buscar_todos_usuarios(session):
    # Carrega o usuário E o seu gerente na mesma consulta
    return session.query(Usuario).options(joinedload(Usuario.gerente)).all()

def buscar_usuario_por_codigo(session, codigo):
    usuario = session.query(Usuario).filter_by(codigo=codigo).first()
    return object_as_dict(usuario) if usuario else None

def atualizar_usuario(session, user_id, dados_novos):
    try:
        usuario = session.query(Usuario).filter_by(id=user_id).first()
        if not usuario: return False
            
        if 'nome_completo' in dados_novos: usuario.nome_completo = dados_novos['nome_completo']
        if 'codigo' in dados_novos: usuario.codigo = dados_novos['codigo']
        if 'role' in dados_novos: usuario.role = dados_novos['role']
        if 'gerente_id' in dados_novos: usuario.gerente_id = dados_novos['gerente_id']
        
        if 'senha' in dados_novos and dados_novos['senha']:
            usuario.senha_hash = generate_password_hash(dados_novos['senha'])
            
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False

# --- LÓGICA DE NEGÓCIO: RELATÓRIOS ---

def buscar_casos(session):
    # Carrega Categoria, Filial e Usuário Responsável de uma vez só
    return session.query(Caso).options(
        joinedload(Caso.categoria),
        joinedload(Caso.filial),
        joinedload(Caso.realizado_por) 
    ).all()

def buscar_caso_por_id(session, caso_id):
    """Busca um caso completo, incluindo atividades, usuários e anexos."""
    return session.query(Caso).options(
        joinedload(Caso.categoria),
        joinedload(Caso.filial),
        joinedload(Caso.realizado_por),
        joinedload(Caso.atividades).joinedload(Atividade.realizado_por),
        joinedload(Caso.anexos)
    ).filter_by(id=caso_id).first()

def criar_caso_com_atividades_padrao(session, categoria_id, filial_id, realizado_por_id):
    try:
        categoria = session.query(Categoria).filter_by(id=categoria_id).first()
        if not categoria: return None
        
        # 1. Cria o Cabeçalho do Caso
        novo_caso = Caso(
            data_inicio=datetime.datetime.now().strftime("%Y-%m-%d"),
            categoria_id=categoria_id, 
            filial_id=filial_id, 
            realizado_por_id=realizado_por_id,
            status='Em Elaboração'
        )
        session.add(novo_caso)
        session.flush()
        
        # 2. Copia as Atividades do POP (Apenas as PUBLICADAS)
        for atividade_padrao in categoria.atividades_padrao:
            if atividade_padrao.status == 'Publicado':
                nova_atividade = Atividade(
                    caso=novo_caso,
                    atividade_desc=atividade_padrao.titulo,
                    atividade_padrao_id=atividade_padrao.id,
                    situacao="Pendente",
                    data_registro=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                session.add(nova_atividade)
            
        session.commit()
        return novo_caso.id
    except Exception as e:
        session.rollback()
        print(f"Erro criar caso: {e}")
        return None

def atualizar_relatorio(session, id_caso, dados_atualizados):
    try: 
        session.query(Caso).filter_by(id=id_caso).update(dados_atualizados)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False

def deletar_caso(session, caso_id):
    try:
        caso = session.query(Caso).filter_by(id=caso_id).first()
        if not caso: return False
        
        # Apaga arquivos físicos
        for anexo in caso.anexos:
            if anexo.caminho_arquivo and os.path.exists(anexo.caminho_arquivo):
                try:
                    os.remove(anexo.caminho_arquivo)
                except OSError:
                    pass
                
        session.delete(caso)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False 

# --- LÓGICA DE NEGÓCIO: ATIVIDADES E ANEXOS ---

def buscar_atividade_por_id(session, atividade_id):
    return session.query(Atividade).options(joinedload(Atividade.realizado_por)).filter_by(id=atividade_id).first()

def salvar_atividade(session, dados):
    try:
        # Tenta criar a atividade (Agora o modelo aceita nao_conformidade)
        nova_atividade = Atividade(**dados)
        session.add(nova_atividade)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        # Debug essencial
        print(f"🔴 ERRO AO SALVAR ATIVIDADE: {e}") 
        return False

def atualizar_atividade(session, id_atividade, dados_atualizados):
    try: 
        session.query(Atividade).filter_by(id=id_atividade).update(dados_atualizados)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False

def adicionar_anexo(session, caso_id, nome, seguro, caminho):
    try:
        novo = Anexo(
            nome_arquivo=nome, 
            nome_seguro=seguro, 
            caminho_arquivo=caminho, 
            data_upload=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            caso_id=caso_id
        )
        session.add(novo)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False

# --- FUNÇÕES AUXILIARES (CRUDs GERAIS) ---

def adicionar_categoria(session, nome):
    try:
        session.add(Categoria(nome=nome))
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False

def buscar_todas_categorias(session): return session.query(Categoria).all()
def buscar_categoria_por_id(session, id): return session.query(Categoria).filter_by(id=id).first()

def atualizar_categoria(session, id, nome):
    try:
        session.query(Categoria).filter_by(id=id).update({'nome': nome})
        session.commit()
        return True
    except Exception:
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
    except Exception:
        session.rollback()
        return False

def adicionar_filial(session, nome, cidade):
    try:
        session.add(Filial(nome=nome, cidade=cidade))
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False

def buscar_todas_filiais(session): return session.query(Filial).all()
def buscar_filial_por_id(session, id): return session.query(Filial).filter_by(id=id).first()

def atualizar_filial(session, id, nome, cidade):
    try:
        fil = session.query(Filial).filter_by(id=id).first()
        if fil:
            fil.nome = nome
            fil.cidade = cidade
            session.commit()
            return True
        return False
    except Exception:
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
    except Exception:
        session.rollback()
        return False

# --- BLOCO DE EXECUÇÃO PRINCIPAL ---
if __name__ == '__main__':
    # Cria as tabelas
    init_db()
    
    # Cria usuário ADMIN padrão se não existir
    try:
        with get_db() as sess:
            if not sess.query(Usuario).filter_by(codigo='ADMIN').first():
                print("Criando usuário ADMIN padrão...")
                admin = Usuario(
                    codigo='ADMIN',
                    nome_completo='ADMINISTRADOR DO SISTEMA',
                    username='admin',
                    senha_hash=generate_password_hash('admin123'),
                    role='Admin'
                )
                sess.add(admin)
                sess.commit()
                print("Usuário ADMIN criado (Senha: admin123).")
    except Exception as e:
        print(f"Erro ao verificar/criar admin: {e}")               