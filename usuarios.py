from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from db import db
from flask_login import UserMixin

auth_bp = Blueprint('auth', __name__)

# USUÁRIO 
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    primeiro_acesso = db.Column(db.Boolean, default=True)
    modulos = db.Column(db.String(255), default='')

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
    def tem_permissao(self, modulo_necessario):
        if self.nome == 'admin': 
            return True
        if self.modulos and modulo_necessario in self.modulos.split(','):
            return True
        return False

# --- ROTAS DE AUTH ---

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        nome = request.form.get('nome')
        senha = request.form.get('senha')
        user = Usuario.query.filter_by(nome=nome).first()
        if user and user.verificar_senha(senha):
            login_user(user)
            if user.primeiro_acesso:
                flash('Por segurança, altere sua senha.')
                return redirect(url_for('auth.alterar_senha'))
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha incorretos.')
            return render_template('login_geral.html', erro="Dados inválidos")

    return render_template('login_geral.html')

@auth_bp.route('/alterar_senha', methods=['GET', 'POST'])
@login_required
def alterar_senha():
    if request.method == 'POST':
        nova = request.form.get('nova_senha')
        confirma = request.form.get('confirmar_senha')
        if nova != confirma:
            return render_template('alterar_senha.html', erro="Senhas não conferem!")
        current_user.definir_senha(nova)
        current_user.primeiro_acesso = False
        db.session.commit()
        flash("Senha alterada com sucesso!")
        return redirect(url_for('index'))

    return render_template('alterar_senha.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# ADMIN 

@auth_bp.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar():
    if current_user.nome not in ['admin','lucas']:
        return "Acesso Negado."

    if request.method == 'POST':
        nome = request.form.get('nome')
        senha = request.form.get('senha')
        lista_permissoes = request.form.getlist('permissoes')
        string_permissoes = ",".join(lista_permissoes)

        if Usuario.query.filter_by(nome=nome).first():
            return render_template('registro.html', erro="Usuário já existe!")

        novo = Usuario(nome=nome, primeiro_acesso=True, modulos=string_permissoes)
        novo.definir_senha(senha)
        db.session.add(novo)
        db.session.commit()
        
        flash(f"Usuário {nome} criado com acesso a: {string_permissoes}")
        return redirect(url_for('auth.registrar'))

    return render_template('registro.html')

@auth_bp.route('/resetar_senha', methods=['POST'])
@login_required
def resetar_senha():
    if current_user.nome != 'admin': return "Acesso Negado."
    nome = request.form.get('nome_usuario')
    user = Usuario.query.filter_by(nome=nome).first()
    if user:
        user.definir_senha('1234')
        user.primeiro_acesso = True
        db.session.commit()
        flash(f"Senha de {nome} resetada.")
    else:
        flash("Usuário não encontrado.", "error")
    return redirect(url_for('auth.registrar'))

@auth_bp.route('/criar_admin')
def criar_admin():
    if Usuario.query.filter_by(nome='admin').first(): return "Admin existe"
    # Admin tem acesso total, nem precisa preencher 'modulos'
    u = Usuario(nome='admin', primeiro_acesso=False) 
    u.definir_senha('1234')
    db.session.add(u)
    db.session.commit()
    return "Admin criado"