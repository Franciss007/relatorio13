from flask import Blueprint, render_template, request, make_response, jsonify, session, url_for, redirect
from flask_login import login_required, current_user # <--- Importação obrigatória
from db import get_connection
import io
import decimal
import csv

bp = Blueprint("consultas", __name__, url_prefix="/consultas")

SQL = """
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

# --- 1. ROTA PRINCIPAL (TELA DE PESQUISA) ---
# No arquivo consultas.py (exemplo)

@bp.route("/consulta")
@login_required
def consulta():
    # Verifica se o usuário tem a permissão 'demanda' (ou se é admin)
    if not current_user.tem_permissao('demanda'):
        return render_template("pagina_erro.html", mensagem="Acesso Negado a este módulo")
        # Ou simplesmente: return "Acesso Negado", 403

    return render_template("consulta_demanda.html", usuario=current_user)


# --- 3. ROTA DE BUSCA (PROCESSAR DADOS) ---
@bp.route("/buscar", methods=["GET", "POST"])
@login_required # <--- Protegido
def buscar():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    if request.method == 'POST':
        data_ini = request.form.get("data_ini")
        data_fim = request.form.get("data_fim")
        nomes_produtos = request.form.getlist("produtos[]")
    else:
        data_ini = request.args.get("data_ini")
        data_fim = request.args.get("data_fim")
        nomes_produtos = request.args.getlist("produtos[]")
        
    if not nomes_produtos:
        return "Nenhum produto informado.", 400
        
    codigos = []
    for item in nomes_produtos:
        parts = item.split("-")
        if parts:
            codigo = parts[0].strip()
            if codigo.isdigit():
                codigos.append(codigo)
                
    if not codigos:
        return "Nenhum código válido encontrado.", 400
        
    placeholders = ", ".join(["?"] * len(codigos))
    sql_final = SQL.format(placeholders=placeholders)
    
    conn = get_connection()
    cur = conn.cursor()
    params = [data_ini, data_fim] + codigos
    cur.execute(sql_final, params)
    rows = cur.fetchall()
    colunas_db = [d[0] for d in cur.description]
    dados_completos = [dict(zip(colunas_db, r)) for r in rows]
    conn.close()

    # --- PAGINAÇÃO ---
    total = len(dados_completos)
    start = (page - 1) * per_page
    end = start + per_page
    dados_paginados = dados_completos[start:end]
    
    nomes_amigaveis = {
        "OP_CODI": "OP", "OP_DESC": "Operação", "SAI_CDDE": "Cod. Loja",
        "NOME_DEST": "Loja", "DSD_CDMT": "Cód. Prod.", "MAT_DESC": "Nome do Produto",
        "SAI_CODI": "Pedido", "SAI_LOJA": "Loja", "SAI_DATA": "Data",
        "DSD_QUAN": "Qtd.", "MAT_UNID": "Unid.", "PESO": "Peso Total",
        "DSD_VUNI": "Vlr. Unit.", "DSD_TOTAL": "Vlr. Total", "EP_QUAN": "Estoque Atual"
    }

    return render_template(
        "resultado_demanda.html",
        dados_paginados=dados_paginados,
        dados=dados_completos,
        produtos=nomes_produtos,
        data_ini=data_ini,
        data_fim=data_fim,
        titulos=nomes_amigaveis,
        page=page,
        per_page=per_page,
        total=total,
        usuario=current_user
    )

# --- 4. BUSCA MANUAL (MODAL) ---
@bp.route("/buscar_produto_manual", methods=["POST"])
@login_required # <--- Protegido
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
            return jsonify({"sucesso": False, "mensagem": "Produto não encontrado! Certifique de inserir os 5 digitos, contando com os zeros a esquerda!"})

    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": f"Erro interno: {str(e)}"})

# --- 5. EXPORTAR CSV ---
@bp.route("/exportar_csv", methods=["POST"])
@login_required # <--- Protegido
def exportar_csv():
    data_ini = request.form.get("data_ini")
    data_fim = request.form.get("data_fim")
    nomes_produtos = request.form.getlist("produtos[]")
    
    if not nomes_produtos:
        return "Nenhum produto informado.", 400
        
    codigos = [item.split("-")[0].strip() for item in nomes_produtos if item.split("-")[0].strip().isdigit()]
    
    if not codigos:
        return "Nenhum código válido encontrado.", 400

    placeholders = ", ".join(["?"] * len(codigos))
    sql_final = SQL.format(placeholders=placeholders)

    conn = get_connection()
    cur = conn.cursor()
    params = [data_ini, data_fim] + codigos
    cur.execute(sql_final, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    
    rows_formatadas = []
    for row in rows:
        nova_linha = []
        for valor in row:
            if isinstance(valor, (float, decimal.Decimal)):
                nova_linha.append(str(valor).replace('.', ','))
            else:
                nova_linha.append(valor)
        rows_formatadas.append(nova_linha)
        
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', lineterminator='\n')
    writer.writerow(cols)
    writer.writerows(rows_formatadas)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=resultados_demanda.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"

    return response

# --- ROTA LEGADA DE LOGOUT (FIX) ---
# Adicionamos de volta para não quebrar o HTML que chama 'consultas.logout'
@bp.route('/logout')
def logout():
    return redirect(url_for('auth.logout'))