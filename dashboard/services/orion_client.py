"""
orion_client.py
Fala com o Orion Context Broker (porta 1026): valores atuais, comandos,
subscriptions (que alimentam o histórico do STH) e registros de comandos.
"""
import requests

from config import (
    ORION_URL, TIMEOUT, ATRIBUTOS, COMANDOS,
    STH_NOTIFY_URL, IOT_AGENT_INTERNO,
)
from services import cabecalhos


def valores_atuais(entidade, tipo):
    """
    Lê o último valor de temperatura, umidade e luminosidade da entidade.
    Devolve {"temperature": 15.5, "humidity": 60.0, "luminosity": 20.0}
    (None quando o valor ainda não existe).
    """
    url = f"{ORION_URL}/v2/entities/{entidade}"
    parametros = {"type": tipo, "options": "keyValues", "attrs": ",".join(ATRIBUTOS)}
    resposta = requests.get(
        url, params=parametros, headers=cabecalhos.para_leitura(), timeout=TIMEOUT
    )
    if resposta.status_code == 404:
        return {atributo: None for atributo in ATRIBUTOS}
    resposta.raise_for_status()

    dados = resposta.json()
    valores = {}
    for atributo in ATRIBUTOS:
        try:
            valores[atributo] = float(dados.get(atributo))
        except (TypeError, ValueError):
            valores[atributo] = None
    return valores


def enviar_comando(comando, entidade, tipo):
    """
    Envia uma ordem ao dispositivo (alerta_temp, alerta_umid, alerta_luz ou normal).
    O Orion repassa ao IoT Agent, que publica no MQTT, e o ESP32 executa.
    Devolve (código HTTP, texto da resposta). O sucesso é 204.
    """
    url = f"{ORION_URL}/v2/entities/{entidade}/attrs"
    corpo = {comando: {"type": "command", "value": ""}}
    resposta = requests.patch(
        url,
        params={"type": tipo},
        json=corpo,
        headers=cabecalhos.para_escrita(),
        timeout=TIMEOUT,
    )
    return resposta.status_code, resposta.text


def criar_subscriptions_sth(entidade, tipo):
    """
    Cria uma subscription por atributo para o Orion avisar o STH-Comet a cada mudança.
    É isso que faz o histórico ser gravado. Usa o nome do contêiner do STH,
    que não muda quando o IP do servidor muda.
    Devolve uma lista de (atributo, código HTTP).
    """
    resultados = []
    for atributo in ATRIBUTOS:
        corpo = {
            "description": f"Notifica o STH-Comet quando {atributo} de {entidade} mudar",
            "subject": {
                "entities": [{"id": entidade, "type": tipo}],
                "condition": {"attrs": [atributo]},
            },
            "notification": {
                "http": {"url": STH_NOTIFY_URL},
                "attrs": [atributo],
                "attrsFormat": "legacy",
            },
        }
        resposta = requests.post(
            f"{ORION_URL}/v2/subscriptions",
            json=corpo,
            headers=cabecalhos.para_escrita(),
            timeout=TIMEOUT,
        )
        resultados.append((atributo, resposta.status_code))
    return resultados


def registrar_comandos(entidade, tipo):
    """
    Registra no Orion que os comandos da entidade são atendidos pelo IoT Agent.
    Devolve o código HTTP (201 = criado).
    """
    corpo = {
        "description": f"Comandos de {entidade}",
        "dataProvided": {
            "entities": [{"id": entidade, "type": tipo}],
            "attrs": COMANDOS,
        },
        "provider": {
            "http": {"url": IOT_AGENT_INTERNO},
            "legacyForwarding": True,
        },
    }
    resposta = requests.post(
        f"{ORION_URL}/v2/registrations",
        json=corpo,
        headers=cabecalhos.para_escrita(),
        timeout=TIMEOUT,
    )
    return resposta.status_code


def _apagar_itens(caminho, entidade, campo_entidades):
    """Apaga as subscriptions ou registros que citam a entidade. Devolve quantos apagou."""
    resposta = requests.get(
        f"{ORION_URL}/v2/{caminho}",
        params={"limit": 1000},
        headers=cabecalhos.para_leitura(),
        timeout=TIMEOUT,
    )
    resposta.raise_for_status()
    apagados = 0
    for item in resposta.json():
        entidades = item.get(campo_entidades[0], {}).get(campo_entidades[1], [])
        if any(e.get("id") == entidade for e in entidades):
            requests.delete(
                f"{ORION_URL}/v2/{caminho}/{item['id']}",
                headers=cabecalhos.para_leitura(),
                timeout=TIMEOUT,
            )
            apagados += 1
    return apagados


def apagar_subscriptions_e_registros(entidade):
    """Remove as subscriptions e os registros de comandos de uma entidade."""
    subs = _apagar_itens("subscriptions", entidade, ("subject", "entities"))
    regs = _apagar_itens("registrations", entidade, ("dataProvided", "entities"))
    return {"subscriptions": subs, "registros": regs}


def apagar_entidade(entidade, tipo):
    """Apaga a entidade (e seus valores atuais) do Orion. Devolve o código HTTP."""
    resposta = requests.delete(
        f"{ORION_URL}/v2/entities/{entidade}",
        params={"type": tipo},
        headers=cabecalhos.para_leitura(),
        timeout=TIMEOUT,
    )
    return resposta.status_code