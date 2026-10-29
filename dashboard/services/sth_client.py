"""
sth_client.py
Lê o histórico de leituras guardado no STH-Comet (porta 8666).
"""
import requests

from config import STH_URL, TIMEOUT, ENTIDADE_PADRAO, TIPO_PADRAO
from services import cabecalhos


def buscar_historico(atributo, entidade=ENTIDADE_PADRAO, tipo=TIPO_PADRAO, quantidade=20):
    """
    Devolve as últimas leituras de um atributo, da mais antiga para a mais nova.
    Cada leitura é um dicionário: {"hora": "2026-10-28T12:00:00.000Z", "valor": 15.5}
    A hora vem em UTC; quem exibe (o navegador) converte para o horário de Brasília.
    """
    url = f"{STH_URL}/STH/v1/contextEntities/type/{tipo}/id/{entidade}/attributes/{atributo}"
    resposta = requests.get(
        url,
        params={"lastN": quantidade},
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