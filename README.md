# SGA — Sistema de Gestão de Auditorias

Plataforma web para gestão completa de auditorias operacionais: criação de relatórios estruturados por POPs (Procedimentos Operacionais Padrão), fluxo de aprovação por hierarquia, upload de evidências e geração de relatórios em PDF.

---

## Funcionalidades

- **Relatórios baseados em POPs** — ao iniciar uma auditoria, as atividades padrão da categoria são carregadas automaticamente
- **Fluxo de aprovação** — `Em Elaboração → Pendente de Revisão → Aprovado → Concluído`
- **Editor de POPs** — crie e publique procedimentos com blocos de texto, alertas e títulos de seção
- **Geração de PDF** — relatório profissional gerado em memória via ReportLab
- **Upload de evidências** — anexe fotos e documentos a cada relatório
- **Controle de acesso por papel** — Admin, Manager e Auditor com permissões distintas
- **Filtro e busca** no dashboard por status, filial e categoria
- **Hash seguro de senhas** via werkzeug (scrypt)

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.10+, Flask 3.x |
| Banco de dados | SQL Server + SQLAlchemy 2.x + PyODBC |
| Frontend | Bootstrap 5, Jinja2, Font Awesome 6 |
| PDF | ReportLab |
| Segurança | werkzeug.security (scrypt) |

---

## Pré-requisitos

1. **Python 3.10+** — [python.org](https://www.python.org/downloads/)
2. **Microsoft SQL Server** (Express é suficiente)
3. **ODBC Driver 17 for SQL Server** — [download Microsoft](https://learn.microsoft.com/pt-br/sql/connect/odbc/download-odbc-driver-for-sql-server)

---

## Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/Krsoliveira/sga-web-flask.git
cd sga-web-flask
```

### 2. Criar e ativar o ambiente virtual

```bash
# Windows
python -m venv venv_web
.\venv_web\Scripts\Activate.ps1

# Linux / Mac
python3 -m venv venv_web
source venv_web/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

Crie o arquivo `.env` na raiz do projeto:

```ini
SECRET_KEY="sua_chave_secreta_aqui"

# Autenticação Windows (recomendado para ambiente local)
DATABASE_URL="mssql+pyodbc://@localhost/SGA_DB?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"

# Autenticação por usuário e senha
# DATABASE_URL="mssql+pyodbc://usuario:senha@servidor/SGA_DB?driver=ODBC+Driver+17+for+SQL+Server"
```

### 5. Criar o banco de dados e o usuário admin

Crie o banco `SGA_DB` no SQL Server e execute:

```bash
python database.py
```

Isso cria todas as tabelas e o usuário `ADMIN` com a senha `admin123`.

> **Atenção:** se o banco já existia antes da versão atual, a coluna `senha_hash` precisa ser ampliada para `NVARCHAR(256)`. Execute uma única vez:
> ```bash
> python -c "
> from sqlalchemy import text
> from database import engine
> with engine.connect() as conn:
>     conn.execute(text('ALTER TABLE dbo.usuarios ALTER COLUMN senha_hash NVARCHAR(256) NOT NULL'))
>     conn.commit()
>     print('Migração concluída.')
> "
> ```

### 6. Rodar a aplicação

```bash
python app.py
```

Acesse: **http://127.0.0.1:5000**

---

## Acesso inicial

| Campo | Valor |
|---|---|
| Código | `ADMIN` |
| Senha | `admin123` |

> Altere a senha após o primeiro login em **Minha Conta → Editar Perfil**.

---

## Estrutura do projeto

```
sga-web-flask/
├── app.py              # Rotas e controladores Flask
├── database.py         # Modelos SQLAlchemy e lógica de negócio
├── pdf_generator.py    # Geração de relatórios PDF com ReportLab
├── requirements.txt    # Dependências Python
├── .env                # Variáveis de ambiente (não versionado)
├── templates/          # Templates Jinja2
│   ├── base.html
│   ├── dashboard.html
│   ├── relatorio.html
│   ├── admin_*.html    # Painéis de administração
│   └── ...
└── uploads/            # Arquivos anexados pelos usuários (não versionado)
```

---

## Papéis de usuário

| Papel | Permissões |
|---|---|
| **Admin** | Acesso total — gerencia usuários, categorias, filiais, POPs e pode forçar conclusão de relatórios |
| **Manager** | Aprova/rejeita relatórios, gerencia POPs e equipe |
| **Auditor** | Cria e preenche relatórios, submete para revisão |

---

## Fluxo de uma auditoria

```
1. Admin/Manager cadastra Categoria + POPs publicados
2. Auditor seleciona Categoria + Filial → relatório criado com atividades pré-carregadas
3. Auditor preenche cada atividade e submete para revisão
4. Manager aprova ou devolve com notas
5. Relatório aprovado → PDF gerado → Auditoria concluída e arquivada
```

---

## Licença

Distribuído sob a licença MIT.
