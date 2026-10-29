"""
sth_client.py
Lê o histórico de leituras guardado no STH-Comet (porta 8666).
"""
import requests

from config import STH_URL, TIMEOUT, ENTIDADE_PADRAO, TIPO_PADRAO
from services import cabecalhos

def buscar_historico(atributo, entidade=ENTIDADE_PADRAO, tipo=TIPO_PADRAO, quantidade=20, data_inicio=None, data_fim=None):
    url = f"{STH_URL}/STH/v1/contextEntities/type/{tipo}/id/{entidade}/attributes/{atributo}"
    
    # Parâmetros da busca: Limite de quantidade e Filtro de Datas (se houver)
    parametros = {"lastN": quantidade}
    if data_inicio:
        parametros["dateFrom"] = f"{data_inicio}T00:00:00.000Z"
    if data_fim:
        parametros["dateTo"] = f"{data_fim}T23:59:59.999Z"
        
    resposta = requests.get(
        url,
        params=parametros,
        headers=cabecalhos.para_leitura(),
        timeout=TIMEOUT,
    )

    # O STH responde 404 quando ainda não existe nenhum dado: tratamos como lista vazia
    if resposta.status_code == 404:
        return []
    resposta.raise_for_status()

    dados = resposta.json()
    try:
        valores = dados["contextResponses"][0]["contextElement"]["attributes"][0]["values"]
    except (KeyError, IndexError):
        return []

    leituras = []
    for item in valores:
        try:
            valor = float(item["attrValue"])
        except (KeyError, TypeError, ValueError):
            continue  # ignora valores que não são números
        leituras.append({"hora": item["recvTime"], "valor": valor})
    return leituras