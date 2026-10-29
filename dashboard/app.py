"""
app.py
Backend do dashboard da Vinheria (Flask).
Recebe pedidos do navegador (HTML/JS) e conversa com o FIWARE:
  - histórico de leituras        -> STH-Comet
  - valores atuais e comandos    -> Orion
  - cadastro de dispositivos     -> IoT Agent
Para rodar:  python app.py   e abrir http://127.0.0.1:5000
"""
import os
import re

import requests
from flask import Flask, jsonify, render_template, request

import config
from services import iot_agent_client, orion_client, sth_client, triggers

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

# Guarda, na memória, o último comando enviado a cada entidade.
ultimo_comando = {}


def erro(mensagem, codigo=400, detalhe=None):
    """Resposta de erro padronizada em JSON."""
    return jsonify({"erro": mensagem, "detalhe": detalhe}), codigo


def entidade_e_tipo():
    """Lê a entidade e o tipo da URL (?entidade=...&tipo=...) ou usa os padrões."""
    entidade = request.args.get("entidade", config.ENTIDADE_PADRAO)
    tipo = request.args.get("tipo", config.TIPO_PADRAO)
    return entidade, tipo


# ---------------------------------------------------------------- páginas


@app.route("/")
def index():
    """Página principal do dashboard."""
    return render_template("index.html")


# ---------------------------------------------------------------- saúde


@app.route("/api/saude")
def saude():
    """Confere se o Orion, o STH e o IoT Agent estão respondendo."""
    servicos = {
        "orion": f"{config.ORION_URL}/version",
        "sth": f"{config.STH_URL}/version",
        "iot_agent": f"{config.IOT_AGENT_URL}/iot/about",
    }
    resultado = {}
    for nome, url in servicos.items():
        try:
            resposta = requests.get(url, timeout=3)
            resultado[nome] = "ok" if resposta.ok else f"erro {resposta.status_code}"
        except requests.RequestException:
            resultado[nome] = "fora do ar"
    return jsonify({"fiware_ip": config.FIWARE_IP, "servicos": resultado})


# ---------------------------------------------------------------- histórico


@app.route("/api/historico")
def historico():
    """Consulta o histórico no STH-Comet com suporte a intervalo de datas."""
    atributo = request.args.get("atributo", "temperature")
    if atributo not in config.ATRIBUTOS:
        return erro(
            f"Atributo inválido. Use um destes: {', '.join(config.ATRIBUTOS)}."
        )
    
    entidade, tipo = entidade_e_tipo()
    data_inicio = request.args.get("data_inicio")  # Formato: YYYY-MM-DD
    data_fim = request.args.get("data_fim")        # Formato: YYYY-MM-DD
    
    try:
        quantidade = int(request.args.get("quantidade", 20))
    except ValueError:
        quantidade = 20
    quantidade = max(1, min(quantidade, 100))

    try:
        leituras = sth_client.buscar_historico(atributo, entidade, tipo, 100)
    except requests.RequestException as e:
        return erro("Não foi possível consultar o STH-Comet.", 502, str(e))

    # Filtra localmente por data se o usuário preencheu o intervalo
    if leituras and (data_inicio or data_fim):
        filtradas = []
        for l in leituras:
            hora_str = str(l.get("hora", ""))[:10]  # Extrai a parte YYYY-MM-DD
            if not hora_str:
                continue
            
            valido = True
            if data_inicio and hora_str < data_inicio:
                valido = False
            if data_fim and hora_str > data_fim:
                valido = False
            
            if valido:
                filtradas.append(l)
        leituras = filtradas[-quantidade:]
    else:
        leituras = leituras[-quantidade:] if leituras else []

    return jsonify({
        "atributo": atributo,
        "entidade": entidade,
        "leituras": leituras
    })


# ---------------------------------------------------------------- status e comandos


@app.route("/api/status")
def status():
    entidade, tipo = entidade_e_tipo()
    try:
        valores = orion_client.valores_atuais(entidade, tipo)
    except requests.RequestException as e:
        return erro("Não foi possível consultar o Orion.", 502, str(e))

    limites = triggers.carregar()
    estados, sugerido = triggers.avaliar(valores, limites)
    return jsonify(
        {
            "entidade": entidade,
            "valores": valores,
            "estados": estados,
            "limites": limites,
            "comando_sugerido": sugerido,
            "ultimo_comando": ultimo_comando.get(entidade),
        }
    )


@app.route("/api/comando", methods=["POST"])
def comando():
    dados = request.get_json(silent=True) or {}
    nome = dados.get("comando")
    if nome not in config.COMANDOS:
        return erro(
            f"Comando inválido. Use um destes: {', '.join(config.COMANDOS)}."
        )
    entidade = dados.get("entidade", config.ENTIDADE_PADRAO)
    tipo = dados.get("tipo", config.TIPO_PADRAO)

    try:
        codigo, texto = orion_client.enviar_comando(nome, entidade, tipo)
    except requests.RequestException as e:
        return erro("Não foi possível falar com o Orion.", 502, str(e))
    if codigo not in (200, 204):
        return erro("O Orion recusou o comando.", 502, f"{codigo}: {texto}")

    ultimo_comando[entidade] = nome
    return jsonify({"enviado": nome, "entidade": entidade})


# ---------------------------------------------------------------- limites (triggers)


@app.route("/api/triggers", methods=["GET", "POST"])
def limites():
    if request.method == "GET":
        return jsonify(triggers.carregar())
    dados = request.get_json(silent=True) or {}
    try:
        salvos = triggers.salvar(dados)
    except ValueError as e:
        return erro(str(e))
    return jsonify(salvos)


# ---------------------------------------------------------------- dispositivos


@app.route("/api/dispositivos", methods=["GET"])
def listar_dispositivos():
    try:
        return jsonify(iot_agent_client.listar_dispositivos())
    except requests.RequestException as e:
        return erro("Não foi possível consultar o IoT Agent.", 502, str(e))


@app.route("/api/dispositivos", methods=["POST"])
def criar_dispositivo():
    dados = request.get_json(silent=True) or {}
    device_id = str(dados.get("device_id", "")).strip()
    if not re.fullmatch(r"[a-z0-9_]{3,40}", device_id):
        return erro(
            "O nome do dispositivo deve ter de 3 a 40 caracteres: letras minúsculas, números e _ (sem espaços)."
        )

    tipo = str(dados.get("entity_type") or config.TIPO_PADRAO).strip()
    entidade = str(dados.get("entity_name") or "").strip()
    if not entidade:
        final = re.search(r"(\d+)$", device_id)
        entidade = (
            f"urn:ngsi-ld:{tipo}:{final.group(1) if final else device_id}"
        )

    try:
        codigo, texto = iot_agent_client.criar_dispositivo(
            device_id, entidade, tipo
        )
        if codigo == 409:
            return erro("Já existe um dispositivo com esse nome.", 409)
        if codigo not in (200, 201):
            return erro(
                "O IoT Agent recusou o cadastro.", 502, f"{codigo}: {texto}"
            )
        subs = orion_client.criar_subscriptions_sth(entidade, tipo)
        registro = orion_client.registrar_comandos(entidade, tipo)
    except requests.RequestException as e:
        return erro("Não foi possível falar com o FIWARE.", 502, str(e))

    return (
        jsonify(
            {
                "device_id": device_id,
                "entity_name": entidade,
                "entity_type": tipo,
                "subscriptions": [
                    {"atributo": a, "codigo": c} for a, c in subs
                ],
                "registro_comandos": registro,
            }
        ),
        201,
    )


@app.route("/api/dispositivos/<device_id>", methods=["DELETE"])
def apagar_dispositivo(device_id):
    if device_id in config.DISPOSITIVOS_PROTEGIDOS:
        return erro(
            "Esse dispositivo é o principal do projeto e não pode ser apagado pelo dashboard.",
            403,
        )
    try:
        existente = next(
            (
                d
                for d in iot_agent_client.listar_dispositivos()
                if d["device_id"] == device_id
            ),
            None,
        )
        if existente is None:
            return erro("Dispositivo não encontrado.", 404)
        entidade, tipo = existente["entity_name"], existente["entity_type"]

        codigo = iot_agent_client.apagar_dispositivo(device_id)
        if codigo not in (200, 204):
            return erro(
                "O IoT Agent não conseguiu apagar o dispositivo.",
                502,
                str(codigo),
            )
        limpeza = orion_client.apagar_subscriptions_e_registros(entidade)
        orion_client.apagar_entidade(entidade, tipo)
    except requests.RequestException as e:
        return erro("Não foi possível falar com o FIWARE.", 502, str(e))

    ultimo_comando.pop(entidade, None)
    return jsonify({"apagado": device_id, "removidos": limpeza})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)