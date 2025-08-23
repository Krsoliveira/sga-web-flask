# SGA-Web-Flask: Sistema de Gestão de Atividades

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)

Sistema web construído com Python e Flask para gestão de relatórios e atividades de auditoria. A aplicação permite a criação de relatórios, registo de atividades detalhadas, autenticação de usuários e gestão de dados através de um banco de dados SQLite.

## ✨ Funcionalidades Principais

- **Autenticação de Usuários:** Sistema de login seguro com senhas "hasheadas".
- **Gestão de Relatórios:** Crie, visualize e delete relatórios de auditoria.
- **Registo de Atividades:** Adicione, edite e remova atividades detalhadas para cada relatório.
- **Persistência de Dados:** Todas as informações são guardadas num banco de dados SQLite.
- **Configuração Segura:** Utiliza variáveis de ambiente para dados sensíveis como a `SECRET_KEY`.

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python
- **Framework:** Flask
- **Banco de Dados:** SQLite
- **Frontend:** HTML5, CSS3
- **Bibliotecas Python:** `python-dotenv`

## 🚀 Como Executar o Projeto Localmente

Siga os passos abaixo para configurar e executar o projeto no seu ambiente de desenvolvimento.

1.  **Clone o Repositório**
    ```bash
    git clone [https://github.com/Krsoliveira/sga-web-flask.git](https://github.com/Krsoliveira/sga-web-flask.git)
    cd sga-web-flask
    ```

2.  **Crie e Ative o Ambiente Virtual**
    ```bash
    # Criar o ambiente
    python -m venv venv_web

    # Ativar no Windows (PowerShell)
    .\venv_web\Scripts\Activate.ps1
    ```

3.  **Instale as Dependências**
    O arquivo `requirements.txt` contém todas as bibliotecas necessárias.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as Variáveis de Ambiente**
    - Crie um arquivo chamado `.env` na raiz do projeto.
    - Adicione a seguinte linha a ele, gerando uma chave aleatória:
    ```
    SECRET_KEY='sua_chave_secreta_super_forte_e_aleatoria'
    ```

5.  **Inicialize o Banco de Dados**
    Na primeira vez que executar o projeto, pode ser necessário inicializar o banco de dados e criar um usuário de exemplo. O `database.py` pode ser executado diretamente para isso:
    ```bash
    python database.py
    ```

6.  **Execute a Aplicação**
    ```bash
    flask run
    ```
    A aplicação estará disponível em `http://127.0.0.1:5000`.

## 📈 Próximos Passos (Roadmap)

- [ ] Implementar gestão de usuários (CRUD) pela interface.
- [ ] Adicionar hierarquia e fluxo de aprovação de relatórios.
- [ ] Implementar exportação de relatórios para PDF.
- [ ] Adicionar tabelas de apoio (Filiais, Setores, etc.).