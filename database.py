import sqlite3
import hashlib
from datetime import date, datetime
from contextlib import contextmanager

DB_NAME = 'gerenciador.db'

@contextmanager
def get_db_conn():
    """
    Gerenciador de contexto para conexões com o banco de dados.
    Garante que a conexão seja sempre fechada de forma segura.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        yield conn
    except sqlite3.Error as e:
        print(f"Erro de banco de dados: {e}")
        raise
    finally:
        if conn:
            conn.close()

def inicializar_banco():
    """Cria e inicializa o banco de dados e suas tabelas se não existirem."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE NOT NULL,
            nome_completo TEXT NOT NULL, username TEXT UNIQUE NOT NULL, 
            password_hash TEXT NOT NULL, nivel_acesso TEXT NOT NULL 
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS casos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, numero_relatorio TEXT UNIQUE,
            tipo TEXT NOT NULL, data_inicio TEXT NOT NULL, data_final TEXT, status TEXT NOT NULL
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS atividades (
            id INTEGER PRIMARY KEY AUTOINCREMENT, caso_id INTEGER NOT NULL, atividade_desc TEXT,
            testes_realizados TEXT, extensao_exames TEXT, criterio_amostragem TEXT,
            periodo_situacao TEXT, observacao_resumo TEXT, realizado_por TEXT,
            nao_conformidade TEXT, reincidente INTEGER, recomendacao TEXT,
            data_p_solucao TEXT, data_registro TEXT NOT NULL, situacao TEXT,
            FOREIGN KEY (caso_id) REFERENCES casos (id) ON DELETE CASCADE
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_exclusoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_caso_excluido INTEGER NOT NULL,
            numero_relatorio_excluido TEXT, titulo_excluido TEXT,
            usuario_codigo TEXT NOT NULL, usuario_nome TEXT NOT NULL, data_exclusao TEXT NOT NULL
        )''')
        conn.commit()
        # Habilitando o suporte a chaves estrangeiras, que no SQLite é desabilitado por padrão por sessão
        cursor.execute("PRAGMA foreign_keys = ON;")


def adicionar_usuario(codigo, nome_completo, username, senha, nivel_acesso):
    try:
        with get_db_conn() as conn:
            cursor = conn.cursor()
            senha_hash = hashlib.sha256(senha.encode()).hexdigest()
            cursor.execute('INSERT INTO usuarios (codigo, nome_completo, username, password_hash, nivel_acesso) VALUES (?, ?, ?, ?, ?)', 
                           (codigo, nome_completo, username, senha_hash, nivel_acesso))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        print(f"Erro: Usuário com código '{codigo}' ou username '{username}' já existe.")
        return False

def verificar_login(codigo, senha):
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT codigo, nome_completo, password_hash, nivel_acesso FROM usuarios WHERE codigo = ?", (codigo,))
        usuario = cursor.fetchone()
        if usuario:
            user_codigo, nome_completo, hash_salvo, nivel = usuario
            senha_digitada_hash = hashlib.sha256(senha.encode()).hexdigest()
            if senha_digitada_hash == hash_salvo:
                return (user_codigo, nome_completo, nivel)
    return None

def deletar_relatorio_e_registrar_log(id_caso, usuario_codigo, usuario_nome):
    try:
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT numero_relatorio, titulo FROM casos WHERE id = ?", (id_caso,))
            dados_caso = cursor.fetchone()
            if not dados_caso: return False

            num_relatorio, titulo = dados_caso
            data_hora_agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("INSERT INTO log_exclusoes (id_caso_excluido, numero_relatorio_excluido, titulo_excluido, usuario_codigo, usuario_nome, data_exclusao) VALUES (?, ?, ?, ?, ?, ?)",
                           (id_caso, num_relatorio, titulo, usuario_codigo, usuario_nome, data_hora_agora))
                                    
            cursor.execute("DELETE FROM casos WHERE id = ?", (id_caso,))
            conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Ocorreu um erro na exclusão segura: {e}")
        return False

def buscar_log_exclusoes():
    with get_db_conn() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, numero_relatorio_excluido, titulo_excluido, usuario_nome, data_exclusao FROM log_exclusoes ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]

def buscar_usuarios():
    with get_db_conn() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT codigo, nome_completo FROM usuarios ORDER BY nome_completo")
        return [dict(row) for row in cursor.fetchall()]

def buscar_casos():
    with get_db_conn() as conn:
        
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, titulo, data_inicio, data_final, status, numero_relatorio FROM casos ORDER BY data_inicio DESC")
        
        return [dict(row) for row in cursor.fetchall()]

def adicionar_novo_caso(titulo, tipo, data_inicio, status):
    with get_db_conn() as conn:
        cursor = conn.cursor()
        ano_atual = date.today().year
        cursor.execute("SELECT numero_relatorio FROM casos WHERE numero_relatorio LIKE ? ORDER BY numero_relatorio DESC LIMIT 1", (f"{ano_atual}.%",))
        resultado = cursor.fetchone()
        ultimo_num = int(resultado[0].split('.')[1]) if resultado else 0
        numero_relatorio_gerado = f"{ano_atual}.{ultimo_num + 1:03d}"
        cursor.execute("INSERT INTO casos (titulo, tipo, data_inicio, status, numero_relatorio) VALUES (?, ?, ?, ?, ?)",
                       (titulo, tipo, data_inicio, status, numero_relatorio_gerado))
        conn.commit()
        return cursor.lastrowid

def buscar_caso_por_id(id_caso):
    with get_db_conn() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM casos WHERE id = ?", (id_caso,))
        resultado = cursor.fetchone()
        return dict(resultado) if resultado else None

def salvar_atividade(dados_atividade):
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO atividades (caso_id, atividade_desc, testes_realizados, extensao_exames, 
                                  criterio_amostragem, periodo_situacao, observacao_resumo, 
                                  realizado_por, nao_conformidade, reincidente, recomendacao, 
                                  data_p_solucao, data_registro, situacao) 
            VALUES (:caso_id, :atividade_desc, :testes_realizados, :extensao_exames, 
                    :criterio_amostragem, :periodo_situacao, :observacao_resumo, 
                    :realizado_por, :nao_conformidade, :reincidente, :recomendacao, 
                    :data_p_solucao, :data_registro, :situacao)
        """, dados_atividade)
        conn.commit()
    return True

def buscar_atividade_por_id(id_atividade):
    with get_db_conn() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM atividades WHERE id = ?", (id_atividade,))
        atividade = cursor.fetchone()
        return dict(atividade) if atividade else None

def atualizar_atividade(id_atividade, dados_atividade):
    with get_db_conn() as conn:
        cursor = conn.cursor()
        query = """
            UPDATE atividades SET 
                atividade_desc = :atividade_desc, testes_realizados = :testes_realizados, 
                observacao_resumo = :observacao_resumo, extensao_exames = :extensao_exames, 
                criterio_amostragem = :criterio_amostragem, periodo_situacao = :periodo_situacao, 
                situacao = :situacao 
            WHERE id = :id
        """
        cursor.execute(query, {**dados_atividade, 'id': id_atividade})
        conn.commit()
    return True

def deletar_atividade_por_id(id_atividade):
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM atividades WHERE id = ?", (id_atividade,))
        conn.commit()
    return True

def atualizar_caso(id_caso, dados_caso):
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE casos SET titulo = :titulo, status = :status, data_final = :data_final WHERE id = :id", 
                       {**dados_caso, 'id': id_caso})
        conn.commit()
    return True

def buscar_atividades_completas_por_caso_id(id_caso):
    with get_db_conn() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM atividades WHERE caso_id = ? ORDER BY id", (id_caso,))
        return [dict(row) for row in cursor.fetchall()]

def adicionar_caso_exemplo():
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM casos")
        if cursor.fetchone() is None:
            adicionar_novo_caso('PRIMEIRO RELATÓRIO DO ANO', 'Auditoria', date.today().strftime("%Y-%m-%d"), 'ABERTO')

def adicionar_atividade_exemplo():
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM atividades WHERE caso_id = ?", (1,))
        if cursor.fetchone() is None:
            dados_ativ = {
                "caso_id": 1, "realizado_por": "Sistema", "data_registro": date.today().strftime("%Y-%m-%d"),
                "atividade_desc": "Coleta de amostras para classificação", "testes_realizados": "Verificação do processo de coleta de amostras de 12 veículos.",
                "extensao_exames": "12 veículos", "criterio_amostragem": "Descargas analisadas no sistema de câmeras da unidade",
                "periodo_situacao": "2025-08-18", "situacao": "FINALIZADO", "observacao_resumo": "Sem irregularidades.",
                "nao_conformidade": "", "reincidente": 0, "recomendacao": "", "data_p_solucao": ""
            }
            salvar_atividade(dados_ativ)

if __name__ == '__main__':
    inicializar_banco()
    adicionar_usuario("28685", "KAIQUE RAFAEL DOS SANTOS OLIVEIRA", "kaique.santos", "senha123", "Junior")
    adicionar_usuario("12345", "MARCOS VINICIUS DAMASCENO", "marcos.vinicius", "outrasenha", "Manager")
    adicionar_caso_exemplo()
    adicionar_atividade_exemplo()
    print("Banco de dados inicializado com dados de exemplo.")