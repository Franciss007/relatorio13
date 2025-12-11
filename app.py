import os
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for
from datetime import timedelta
from flask_login import LoginManager, login_required, current_user
from db import db 
from usuarios import auth_bp, Usuario 
from cortes import bp as cortes_bp
from relatorio13 import bp as resultado_bp
from consulta import bp as consultas_bp 

load_dotenv() 

app = Flask(__name__)
app.secret_key = 'Fribal_sistema_2025'

# --- CONFIGURAÇÃO BANCO DE DADOS (POSTGRES) ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("POSTGRES_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
with app.app_context():
    db.create_all()

# --- CONFIGURAÇÃO DO LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' 
login_manager.login_message = "Por favor, faça login para acessar este módulo."

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# --- REGISTRO DOS BLUEPRINTS ---
app.register_blueprint(cortes_bp)
app.register_blueprint(resultado_bp)
app.register_blueprint(consultas_bp)
app.register_blueprint(auth_bp, url_prefix='/auth') 

# --- ROTAS PRINCIPAIS ---

@app.route("/")
def index():
    """
    Rota Raiz:
    - Se logado: Mostra o Menu de Módulos.
    - Se não logado: Redireciona para o Login.
    """
    if current_user.is_authenticated:
        return render_template("menu_selecao.html")
    
    return redirect(url_for('auth.login'))


@app.route("/selecionar/<opcao>")
@login_required 
def selecionar(opcao):    
    if opcao == "cortes":
        return redirect("/cortes") 
    if opcao == "resultado":
        return redirect("/pedidos")
    if opcao == "demanda":
        return redirect("/consultas/consulta")
    return "Módulo não encontrado ou em desenvolvimento."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=True, use_reloader=False)