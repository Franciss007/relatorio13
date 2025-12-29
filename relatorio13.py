from flask import Blueprint, render_template, request, make_response, redirect, session, url_for
from flask_login import login_required, current_user 
from db import get_connection
import io

bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")

COLUNAS_NOMES = {
    "OP_DESC": "OPERAÇÃO",
    "EMP_NFAN": "LOJA",
    "DSD_CDMT": "CÓDIGO",
    "MAT_DESC": "DESCRIÇÃO",
    "SAI_CODI": "PEDIDO",
    "SAI_NNOT": "NOTA",
    "SAI_DATA": "DATA",
    "DSD_QUAN": "QUANTIDADE",
    "MAT_UNID": "UNIDADE",
    "DSD_VUNI": "VALOR UNITÁRIO",
    "DSD_TOTAL": "TOTAL ITEM",
    "SAI_VALO": "TOTAL PEDIDO"
}

SQL = """
SELECT 
    OP_DESC,
    EMP_NFAN,
    DSD_CDMT,
    MAT_DESC,
    SAI_CODI,
    SAI_NNOT,
    SAI_DATA,
    DSD_QUAN,
    MAT_UNID,
    DSD_VUNI,
    DSD_TOTAL,
    SAI_VALO
FROM TB_EMP 
JOIN TB_SAID ON EMP_CODI = SAI_CDDE
JOIN TB_OPER ON OP_CODI = SAI_OPER
JOIN TB_USUA ON SAI_CDUS = USU_CODI 
JOIN TB_DSAI ON DSD_LOJA = SAI_LOJA AND DSD_CODI = SAI_CODI
JOIN TB_MATE ON MAT_CODI = DSD_CDMT
WHERE SAI_CANC = 'N'
  AND SAI_LOJA = '999'
  AND SAI_OPER = ?
  AND SAI_DATA BETWEEN ? AND ?
ORDER BY SAI_CODI
"""
    
@bp.route("/")
@login_required 
def index():
    # --- SEGURANÇA: Verifica se tem permissão 'pedidos' ---
    if not current_user.tem_permissao('pedidos'):
        return render_template("pagina_erro.html", mensagem="Seu usuário não tem permissão para acessar o módulo de PEDIDOS.")
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT OP_CODI, OP_DESC FROM TB_OPER WHERE OP_TIPO ='S' ORDER BY OP_DESC")
    operacoes = cur.fetchall()
    conn.close()
    
    return render_template("pagina_relatorio13.html", operacoes=operacoes, usuario=current_user)

@bp.route("/buscar", methods=["POST", "GET"])
@login_required 
def buscar():
    # --- SEGURANÇA ---
    if not current_user.tem_permissao('pedidos'):
        return render_template("pagina_erro.html", mensagem="Acesso Negado.")

    if request.method == "POST":
        operacao = request.form.get("operacao")
        data_ini = request.form.get("data_ini")
        data_fim = request.form.get("data_fim")
    else:
        operacao = request.args.get("operacao")
        data_ini = request.args.get("data_ini")
        data_fim = request.args.get("data_fim")
    
    if not operacao or not data_ini or not data_fim:
         conn = get_connection()
         cur = conn.cursor()
         cur.execute("SELECT OP_CODI, OP_DESC FROM TB_OPER WHERE OP_TIPO ='S' ORDER BY OP_DESC")
         operacoes = cur.fetchall()
         conn.close()
         return render_template("pagina_relatorio13.html", operacoes=operacoes, usuario=current_user, erro="Preencha todos os filtros.")

    page = request.args.get("page", 1, type=int)
    per_page = 20
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(SQL, (operacao, data_ini, data_fim))
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    conn.close()
    
    dados = []
    for r in rows:
        linha = {}
        for col, valor in zip(cols, r):
            nome = COLUNAS_NOMES.get(col, col)
            linha[nome] = valor
        dados.append(linha)
        
    total = len(dados)
    start = (page - 1) * per_page
    end = start + per_page
    dados_paginados = dados[start:end]
    
    return render_template(
        "resultado.html",
        dados=dados,
        dados_paginados=dados_paginados,
        page=page,
        per_page=per_page,
        total=total,
        operacao=operacao,
        data_ini=data_ini,
        data_fim=data_fim,
        usuario=current_user 
    )

@bp.route("/exportar", methods=["POST"])
@login_required 
def exportar():
    # --- SEGURANÇA ---
    if not current_user.tem_permissao('pedidos'):
        return "Acesso Negado", 403

    operacao = request.form.get("operacao")
    data_ini = request.form.get("data_ini")
    data_fim = request.form.get("data_fim")
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(SQL, (operacao, data_ini, data_fim))
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    conn.close()
    
    output = io.StringIO()
    output.write(";".join(cols) + "\n")
    for r in rows:
        linha = []
        for v in r:
            if isinstance(v, float):
                v = f"{v:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
            linha.append(str(v))
        output.write(";".join(linha) + "\n")
        
    csv_data = output.getvalue()
    response = make_response(csv_data)
    response.headers["Content-Disposition"] = "attachment; filename=relatorio.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    
    return response

# Rota de segurança para logout
@bp.route('/logout')
def logout():
    return redirect(url_for('auth.logout'))