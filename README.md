Com certeza! Um `README.md` bem escrito é o "cartão de visita" do projeto. Como mudámos a arquitetura para **SQL Server** e adicionámos a geração de **PDFs** (que requer dependências externas), é crucial documentar os pré-requisitos.

Aqui está uma proposta completa e profissional para o seu ficheiro `README.md`. Pode copiar o código abaixo e substituir o conteúdo do seu ficheiro atual.

Estou a utilizar a norma de **Português de Portugal** conforme a configuração do sistema, mas os termos técnicos mantêm-se universais.

---

### Código para o arquivo `README.md`

```markdown
# 📊 Sistema de Gestão de Auditorias e Relatórios (SGA)

Uma plataforma web robusta para a gestão completa de auditorias operacionais, desde o planeamento e recolha de evidências até à geração de relatórios PDF profissionais e análise de conformidade.

---

## 🚀 Funcionalidades Principais

* **Gestão de Auditorias:** Criação de relatórios baseados em Filiais e Categorias personalizáveis.
* **Checklists Inteligentes:** Atividades padrão (POPs) carregadas automaticamente por categoria.
* **Fluxo de Aprovação:** Ciclo de vida completo: *Em Elaboração* → *Revisão* → *Aprovação* → *Conclusão*.
* **Evidências:** Upload de fotos e documentos por atividade.
* **Relatórios PDF:** Geração automática de relatórios profissionais com simbologia de conformidade ($\checkmark$, $X$).
* **Hierarquia de Utilizadores:** Controlo de acesso baseado em funções (Admin, Manager, Auditor).
* **Segurança:** Eliminação lógica e física de ficheiros e proteção de rotas sensíveis.

---

## 🛠️ Tecnologias Utilizadas

* **Backend:** Python 3.10+, Flask
* **Base de Dados:** SQL Server (via SQLAlchemy e PyODBC)
* **Frontend:** Bootstrap 5, Jinja2, HTML5/CSS3
* **PDF Engine:** WeasyPrint
* **Autenticação:** Sessões geridas do lado do servidor com hash de palavras-passe.

---

## 📋 Pré-requisitos

Antes de iniciar, certifique-se de que tem instalado no seu ambiente:

1.  **Python 3.8 ou superior**: [Download Python](https://www.python.org/downloads/)
2.  **Microsoft SQL Server** (Express ou Standard): Base de dados relacional.
3.  **ODBC Driver 17 for SQL Server**: Necessário para o Python comunicar com o SQL Server. [Download Microsoft](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
4.  **GTK3 Runtime (Apenas para Windows)**: Essencial para a biblioteca `WeasyPrint` gerar PDFs.
    * *Sem isto, a geração de PDF falhará com erro de `dlopen` ou `dll missing`.*
    * [Download GTK3 Installer](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases)

---

## ⚙️ Instalação e Configuração

Siga os passos abaixo para colocar o projeto a rodar localmente:

### 1. Clonar o Repositório
```bash
git clone [https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)
cd seu-repositorio

```

### 2. Criar o Ambiente Virtual

Recomendamos o uso de um ambiente virtual para isolar as dependências.

```bash
# Windows
python -m venv venv_web
.\venv_web\Scripts\activate

# Linux/Mac
python3 -m venv venv_web
source venv_web/bin/activate

```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt

```

### 4. Configurar Variáveis de Ambiente

Crie um ficheiro chamado `.env` na raiz do projeto e configure a string de conexão com o seu SQL Server:

```ini
# Exemplo de conteúdo do arquivo .env
DATABASE_URL="mssql+pyodbc://usuario:senha@SERVIDOR\INSTANCIA/NOME_DO_BANCO?driver=ODBC+Driver+17+for+SQL+Server"
SECRET_KEY="sua_chave_secreta_super_segura"

```

*Nota: Substitua `usuario`, `senha`, `SERVIDOR\INSTANCIA` e `NOME_DO_BANCO` pelos seus dados reais.*

### 5. Inicializar a Base de Dados

O sistema possui um script para criar automaticamente todas as tabelas e o utilizador administrador.

```bash
python database.py

```

*Se tudo correr bem, verá a mensagem: "Banco de dados inicializado. Usuário ADMIN criado."*

### 6. Executar a Aplicação

```bash
python app.py

```

Aceda no seu navegador: `http://127.0.0.1:5000`

---

## 🔐 Acesso Inicial

Após a inicialização da base de dados, um utilizador administrador padrão é criado:

* **Código:** `ADMIN`
* **Palavra-passe:** `admin123`

> **Importante:** Altere esta palavra-passe imediatamente após o primeiro login.

---

## 📚 Estrutura do Projeto

```text
/
├── app.py                 # Lógica principal (Rotas e Controladores)
├── database.py            # Modelos e Configuração da Base de Dados
├── requirements.txt       # Lista de dependências
├── .env                   # Variáveis de ambiente (Ignorado pelo Git)
├── templates/             # Ficheiros HTML (Jinja2)
├── static/                # CSS, JS e Imagens
└── uploads/               # Pasta onde os anexos são guardados

```

---

## 🐛 Como Contribuir / Reportar Erros

1. Faça um Fork do projeto.
2. Crie uma Branch para a sua Feature (`git checkout -b feature/NovaFeature`).
3. Faça o Commit (`git commit -m 'Adicionado nova feature'`).
4. Faça o Push (`git push origin feature/NovaFeature`).
5. Abra um Pull Request.

---

**Desenvolvido com 💙 e Python.**

```

### O que adicionei de especial neste README:

1.  **Aviso do GTK3:** Esta é a parte mais crítica. Como você usa o **WeasyPrint** no Windows, qualquer pessoa que baixar o projeto vai ter erros ao gerar PDF se não instalar o GTK3. Deixei o link direto para download.
2.  **ODBC Driver:** Especifiquei que é necessário ter o driver do SQL Server instalado, não basta ter o Python.
3.  **Setup da Base de Dados:** Expliquei claramente que devem rodar o `python database.py` antes do `app.py`.
4.  **Login Padrão:** Documentei o utilizador `ADMIN` que criámos no código anterior, senão ninguém consegue entrar na primeira vez.

Assim que atualizar o ficheiro, pode fazer o commit:

```bash
git add README.md
git commit -m "Docs: Atualizacao completa do manual de instalacao e requisitos"
git push

```