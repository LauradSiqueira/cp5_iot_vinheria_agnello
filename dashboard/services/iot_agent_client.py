"""
iot_agent_client.py
Cadastro e gerenciamento dos dispositivos IoT no IoT Agent (porta 4041).
"""
import requests

from config import IOT_AGENT_URL, TIMEOUT, COMANDOS
from services import cabecalhos


def listar_dispositivos():
    """Devolve a lista de dispositivos cadastrados, em um formato simples."""
    resposta = requests.get(
        f"{IOT_AGENT_URL}/iot/devices",
        headers=cabecalhos.para_leitura(),
        timeout=TIMEOUT,
    )
    resposta.raise_for_status()
    lista = []
    for d in resposta.json().get("devices", []):
        lista.append({
            "device_id": d.get("device_id"),
            "entity_name": d.get("entity_name"),
            "entity_type": d.get("entity_type"),
            "atributos": [a.get("name") for a in d.get("attributes", [])],
            "comandos": [c.get("name") for c in d.get("commands", [])],
        })
    return lista


def criar_dispositivo(device_id, entidade, tipo):
    """
    Cadastra um dispositivo com os atributos t, h, l (temperatura, umidade e
    luminosidade) e os quatro comandos. Devolve (código HTTP, texto da resposta).
    """
    corpo = {
        "devices": [{
            "device_id": device_id,
            "entity_name": entidade,
            "entity_type": tipo,
            "protocol": "PDI-IoTA-UltraLight",
            "transport": "MQTT",
            "commands": [{"name": nome, "type": "command"} for nome in COMANDOS],
            "attributes": [
                {"object_id": "t", "name": "temperature", "type": "Number"},
                {"object_id": "h", "name": "humidity", "type": "Number"},
                {"object_id": "l", "name": "luminosity", "type": "Number"},
            ],
        }]
    }
    resposta = requests.post(
        f"{IOT_AGENT_URL}/iot/devices",
        json=corpo,
        headers=cabecalhos.para_escrita(),
        timeout=TIMEOUT,
    )
    return resposta.status_code, resposta.text


def apagar_dispositivo(device_id):
    """Remove o dispositivo do IoT Agent. Devolve o código HTTP (204 = apagado)."""
    resposta = requests.delete(
        f"{IOT_AGENT_URL}/iot/devices/{device_id}",
        headers=cabecalhos.para_leitura(),
        timeout=TIMEOUT,
    )
    return resposta.status_code