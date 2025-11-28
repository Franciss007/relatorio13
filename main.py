from flask import Flask, render_template, redirect

app = Flask(__name__)

# importar os módulos
from cortes import bp as cortes_bp
from relatorio13 import bp as resultado_bp

# registrar
app.register_blueprint(cortes_bp)
app.register_blueprint(resultado_bp)


@app.route("/")
def login():
    return render_template("login.html")


@app.route("/selecionar/<opcao>")
def selecionar(opcao):
    if opcao == "cortes":
        return redirect("/cortes")
    if opcao == "resultado":
        return redirect("/pedidos")
    return "Opção inválida!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=True)
