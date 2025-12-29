from flask import Blueprint, render_template, request, make_response, jsonify, redirect, url_for
from flask_login import login_required, current_user 
from db import get_connection
import io
import decimal
import csv
from datetime import datetime

bp = Blueprint("consultas", __name__, url_prefix="/consultas")

# --- SQLs ---

SQL_ANALITICO = """
SELECT
    OP_CODI, OP_DESC, SAI_CDDE,
    CASE
        WHEN OP_DEST = 'L' THEN LOJA.EMP_NFAN
        WHEN OP_DEST = 'C' THEN CLI_NOME
        WHEN OP_DEST = 'F' THEN FOR_NFAN
    END AS NOME_DEST,
    DSD_CDMT, MAT_DESC, SAI_CODI, SAI_DATA, DSD_QUAN,
    MAT_UNID, DSD_VUNI, DSD_TOTAL, EP_QUAN
FROM TB_SAID
INNER JOIN TB_DSAI ON DSD_LOJA = SAI_LOJA AND DSD_CODI = SAI_CODI
INNER JOIN TB_MATE ON MAT_CODI = DSD_CDMT
INNER JOIN TB_OPER ON SAI_OPER = OP_CODI
INNER JOIN TB_EMP ON SAI_LOJA = EMP_CODI
LEFT JOIN TB_CLIE ON CLI_CODI = SAI_CDDE AND OP_DEST = 'C'
LEFT JOIN TB_FORN ON FOR_CODI = SAI_CDDE AND OP_DEST = 'F'
LEFT JOIN TB_EMP LOJA ON LOJA.EMP_CODI = SAI_CDDE AND OP_DEST = 'L'
LEFT JOIN TB_ESTPROD ON EP_LOJA = SAI_LOJA AND EP_CDMT = DSD_CDMT
WHERE SAI_CANC = 'N'
    AND SAI_DATA BETWEEN ? AND ?
    AND SAI_LOJA = '067'
    AND DSD_CDMT IN ({placeholders})
    AND OP_CODI IN ('1H','1I')
ORDER BY MAT_DESC
"""

SQL_SINTETICO = """
SELECT
    DSD_CDMT, 
    MAT_DESC, 
    MAT_UNID,
    SUM(DSD_QUAN) AS DSD_QUAN,
    SUM(DSD_TOTAL) AS DSD_TOTAL,
    MAX(EP_QUAN) AS EP_QUAN
FROM TB_SAID
INNER JOIN TB_DSAI ON DSD_LOJA = SAI_LOJA AND DSD_CODI = SAI_CODI
INNER JOIN TB_MATE ON MAT_CODI = DSD_CDMT
INNER JOIN TB_OPER ON SAI_OPER = OP_CODI
LEFT JOIN TB_ESTPROD ON EP_LOJA = SAI_LOJA AND EP_CDMT = DSD_CDMT
WHERE SAI_CANC = 'N'
    AND SAI_DATA BETWEEN ? AND ?
    AND SAI_LOJA = '067'
    AND DSD_CDMT IN ({placeholders})
    AND OP_CODI IN ('1H','1I')
GROUP BY DSD_CDMT, MAT_DESC, MAT_UNID
ORDER BY MAT_DESC
"""

# --- 1. ROTA PRINCIPAL ---

@bp.route("/consulta")
@login_required
def consulta():
    if not current_user.tem_permissao('demanda'):
        return render_template("pagina_erro.html", mensagem="Acesso Negado a este módulo")
    return render_template("consulta_demanda.html", usuario=current_user)

# --- 2. ROTA DE BUSCA ---

@bp.route("/buscar", methods=["GET", "POST"])
@login_required
def buscar():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    if request.method == 'POST':
        data_ini = request.form.get("data_ini")
        data_fim = request.form.get("data_fim")
        tipo_lista = request.form.get("lista", "") # Vem do select 'lista'
        tipo_relatorio = request.form.get("tipo_relatorio")
        nomes_produtos = request.form.getlist("produtos[]")
    else:
        data_ini = request.args.get("data_ini")
        data_fim = request.args.get("data_fim")
        tipo_lista = request.args.get("tipo_lista", "")
        tipo_relatorio = request.args.get("tipo_relatorio")
        nomes_produtos = request.args.getlist("produtos[]")

    if not nomes_produtos:
        return "Nenhum produto informado.", 400

    codigos = [item.split("-")[0].strip() for item in nomes_produtos if item.split("-")[0].strip().isdigit()]
    if not codigos:
        return "Nenhum código válido encontrado.", 400

    placeholders = ", ".join(["?"] * len(codigos))
    
    if tipo_relatorio == "sintetico":
        sql_final = SQL_SINTETICO.format(placeholders=placeholders)
        titulos = {
            "DSD_CDMT": "Cód. Prod.", "MAT_DESC": "Nome do Produto",
            "DSD_QUAN": "Qtd. Total", "MAT_UNID": "Unid.",
            "DSD_TOTAL": "Vlr. Total", "EP_QUAN": "Estoque"
        }
    else:
        sql_final = SQL_ANALITICO.format(placeholders=placeholders)
        titulos = {
            "OP_CODI": "OP", "NOME_DEST": "Loja/Destino", "DSD_CDMT": "Cód.", 
            "MAT_DESC": "Produto", "SAI_DATA": "Data", "DSD_QUAN": "Qtd.", 
            "MAT_UNID": "Un.", "DSD_TOTAL": "Total", "SAI_CODI": "Pedido"
        }

    conn = get_connection()
    cur = conn.cursor()
    params = [data_ini, data_fim] + codigos
    cur.execute(sql_final, params)
    rows = cur.fetchall()
    colunas_db = [d[0] for d in cur.description]
    dados_completos = [dict(zip(colunas_db, r)) for r in rows]
    conn.close()

    total = len(dados_completos)
    total_pages = (total // per_page) + (1 if total % per_page else 0)
    start = (page - 1) * per_page
    end = start + per_page
    dados_paginados = dados_completos[start:end]

    return render_template(
        "resultado_demanda.html",
        dados_paginados=dados_paginados,
        tipo_relatorio=tipo_relatorio,
        tipo_lista=tipo_lista,
        total_pages=total_pages,
        titulos=titulos,
        produtos=nomes_produtos,
        data_ini=data_ini,
        data_fim=data_fim,
        page=page,
        per_page=per_page,
        total=total,
        usuario=current_user
    )

# --- 3. ROTA DE EXPORTAÇÃO ---

@bp.route("/exportar_csv", methods=["POST"])
@login_required
def exportar_csv():
    data_ini = request.form.get("data_ini")
    data_fim = request.form.get("data_fim")
    tipo_lista = request.form.get("tipo_lista", "").capitalize()
    tipo_relatorio = request.form.get("tipo_relatorio", "analitico")
    nomes_produtos = request.form.getlist("produtos[]")
    
    codigos = [item.split("-")[0].strip() for item in nomes_produtos if item.split("-")[0].strip().isdigit()]
    placeholders = ", ".join(["?"] * len(codigos))

    if tipo_relatorio == "sintetico":
        sql_final_base = SQL_SINTETICO
        titulos_map = {
            "DSD_CDMT": "Cod. Prod.", "MAT_DESC": "Nome do Produto",
            "MAT_UNID": "Unid.", "DSD_QUAN": "Qtd. Total",
            "DSD_TOTAL": "Vlr. Total", "EP_QUAN": "Estoque"
        }
    else:
        sql_final_base = SQL_ANALITICO
        titulos_map = {
            "OP_CODI": "OP", "NOME_DEST": "Loja/Destino", "DSD_CDMT": "Cod.", 
            "MAT_DESC": "Produto", "SAI_DATA": "Data", "DSD_QUAN": "Qtd.", 
            "MAT_UNID": "Un.", "DSD_TOTAL": "Total", "SAI_CODI": "Pedido"
        }

    sql_final = sql_final_base.format(placeholders=placeholders)

    conn = get_connection()
    cur = conn.cursor()
    params = [data_ini, data_fim] + codigos
    cur.execute(sql_final, params)
    rows = cur.fetchall()
    cols_originais = [d[0] for d in cur.description]
    conn.close()

    header_amigavel = [titulos_map.get(col, col) for col in cols_originais]

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', lineterminator='\n')
    writer.writerow(header_amigavel)

    for row in rows:
        nova_linha = []
        for valor in row:
            if isinstance(valor, (float, decimal.Decimal)):
                nova_linha.append(str(valor).replace('.', ','))
            elif isinstance(valor, datetime):
                nova_linha.append(valor.strftime('%d/%m/%Y'))
            else:
                nova_linha.append(valor)
        writer.writerow(nova_linha)

    # Formatação do nome do arquivo
    try:
        data_obj = datetime.strptime(data_ini, '%Y-%m-%d')
        data_str = data_obj.strftime('%d-%m-%Y')
    except:
        data_str = datetime.now().strftime('%d-%m-%Y')

    tipo_str = "Sintetico" if tipo_relatorio == "sintetico" else "Analitico"
    filename = f"Relatorio-{tipo_str}_{tipo_lista}_{data_str}.csv"

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"

    return response

# --- 4. BUSCA MANUAL (MODAL) ---

@bp.route("/buscar_produto_manual", methods=["POST"])
@login_required
def buscar_produto_manual():
    dados = request.get_json()
    codigo = dados.get("codigo")
    
    if not codigo:
        return jsonify({"sucesso": False, "mensagem": "Código não informado."})
        
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql_produto = "SELECT MAT_DESC FROM TB_MATE WHERE MAT_CODI = ?"
        cur.execute(sql_produto, (codigo,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            return jsonify({"sucesso": True, "codigo": codigo, "nome": row[0]})
        else:
            return jsonify({"sucesso": False, "mensagem": "Produto não encontrado!"})

    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": f"Erro interno: {str(e)}"})

# --- 5. LOGOUT ---

@bp.route('/logout')
def logout():
    return redirect(url_for('auth.logout'))