from flask import Blueprint, render_template, request, make_response, url_for, session, redirect
from flask_login import login_required, current_user 
from db import get_connection
import io

bp = Blueprint("cortes", __name__, url_prefix="/cortes")

SQL = """
SELECT 
    MSE_DESC AS CATEGORIA,
    MGR_DESC AS GRUPO,
    SAI_CDDE AS COD,
    e2.EMP_NFAN AS LOJA,
    SAI_CODI AS PEDIDO,
    u2.USU_NOME AS USU_PEDIDO,
    SAI_DATA AS DATA_PEDIDO,
    DSC_PRODUTO AS COD_P,
    MAT_DESC AS PRODUTO,
    MAT_UNID AS SKU,
    MAT_EMBALAGEM AS EMBALAGEM,
    DSC_QTDPEDIDA AS QTD_PEDIDA,
    DSC_QTDCORTADA AS QTD_CORTADA,
    u1.USU_NOME AS USU_CORTE,
    DSC_QTDENTREGUE AS QTD_ENTREGUE,
    COALESCE(DSD_VUNI, 0) AS PRECO,
    DSC_DH AS DATA_CORTE,
    (DSC_QTDCORTADA * COALESCE(DSD_VUNI, 0)) AS VALOR,
    EP_QUAN AS ESTOQUE
FROM TB_SAID
    INNER JOIN TB_OPER ON OP_CODI = SAI_OPER
    INNER JOIN TB_EMP te ON TE.EMP_CODI = SAI_LOJA
    INNER JOIN TB_EMP e2 ON e2.EMP_CODI = SAI_CDDE
    INNER JOIN TB_DSAICORTADOS SP 
        ON SP.DSC_LOJA = SAI_LOJA 
        AND SP.DSC_PEDIDO = SAI_CODI 
        AND SP.DSC_FASE IN (0, 1)
    INNER JOIN TB_USUA u1 ON u1.USU_CODI = DSC_USCORTE
    INNER JOIN TB_USUA u2 ON u2.USU_CODI = SAI_CDUS
    INNER JOIN TB_MATE ON MAT_CODI = DSC_PRODUTO
    INNER JOIN TB_ESTPROD ON EP_LOJA = SAI_LOJA AND EP_CDMT = MAT_CODI
    LEFT JOIN TB_SEPARADOR ON SAI_SEPARADOR = SP_CODI
    LEFT JOIN TB_CONF ON SAI_CDCO = CON_CODI
    LEFT JOIN TB_DSAI ON DSD_LOJA = SAI_LOJA AND DSD_CODI = SAI_CODI AND DSD_CDMT = MAT_CODI
    LEFT JOIN TB_MAT_SEC ON MAT_CDSE = MSE_CODI
    LEFT JOIN TB_MAT_GRUP tmg ON MAT_CDSE = tmg.MGR_CDSE AND MAT_CDGR = MGR_CODI
WHERE 
    SAI_CANC = 'N'
    AND SAI_LOJA = '999'
    AND SAI_DATA BETWEEN ? AND ?
    AND MSE_CODI IN ('002','003','004','006','007','008')
ORDER BY 1, SAI_DATA;
"""

@bp.route("/")
@login_required 
def index():
    # --- SEGURANÇA: Verifica se tem permissão 'cortes' ---
    if not current_user.tem_permissao('cortes'):
        return render_template("pagina_erro.html", mensagem="Seu usuário não tem permissão para acessar o módulo de CORTES.")

    return render_template("pagina_cortes.html", usuario=current_user)

@bp.route("/buscar", methods=["GET", "POST"])
@login_required 
def buscar():
    # --- SEGURANÇA ---
    if not current_user.tem_permissao('cortes'):
        return render_template("pagina_erro.html", mensagem="Acesso Negado.")

    page = request.args.get("page", 1, type=int)
    per_page = 20

    if request.method == "POST":
        data_ini = request.form.get("data_ini")
        data_fim = request.form.get("data_fim")
    else:
        data_ini = request.args.get("data_ini")
        data_fim = request.args.get("data_fim")
    
    if not data_ini or not data_fim:
        return render_template("pagina_cortes.html", usuario=current_user, erro="Selecione as datas.")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(SQL, (data_ini, data_fim))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    
    dados = [dict(zip(cols, r)) for r in rows]
    total = len(dados)
    start = (page - 1) * per_page
    end = start + per_page
    dados_paginados = dados[start:end]
    
    return render_template(
        "resultado_cortes.html",
        dados=dados,
        dados_paginados=dados_paginados,
        page=page,
        per_page=per_page,
        total=total,
        data_ini=data_ini,
        data_fim=data_fim,
        usuario=current_user 
    )

@bp.route("/exportar", methods=["POST"])
@login_required 
def exportar():
    # --- SEGURANÇA ---
    if not current_user.tem_permissao('cortes'):
        return "Acesso Negado", 403

    data_ini = request.form.get("data_ini")
    data_fim = request.form.get("data_fim")
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(SQL, (data_ini, data_fim))
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
    response.headers["Content-Disposition"] = "attachment; filename=cortes.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    
    return response

# Rota de segurança para logout
@bp.route('/logout')
def logout():
    return redirect(url_for('auth.logout'))