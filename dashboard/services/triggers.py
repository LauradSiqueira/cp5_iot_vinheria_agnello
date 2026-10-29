"""
triggers.py
Guarda os limites (triggers) de temperatura, umidade e luminosidade e
decide, a partir dos valores atuais, qual comando deve estar ativo.
Os limites ficam no arquivo data/triggers.json e a tela "Limites" os altera.
"""
import json
import os

from config import ARQUIVO_TRIGGERS, ATRIBUTOS

# Limites iniciais (usados quando o arquivo ainda não existe)
PADRAO = {
    "temperature": {"min": 12.0, "max": 18.0},
    "humidity": {"min": 60.0, "max": 75.0},
    "luminosity": {"min": 0.0, "max": 30.0},
}

# Quando duas anomalias acontecem juntas, vale a primeira desta lista
PRIORIDADE = [
    ("temperature", "alerta_temp"),
    ("humidity", "alerta_umid"),
    ("luminosity", "alerta_luz"),
]


def carregar():
    """Lê os limites do arquivo. Se ele não existir, cria com os valores padrão."""
    if not os.path.exists(ARQUIVO_TRIGGERS):
        salvar(PADRAO)
        return json.loads(json.dumps(PADRAO))
    with open(ARQUIVO_TRIGGERS, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar(novos):
    """
    Valida e grava os limites. Formato esperado:
    {"temperature": {"min": 12, "max": 18}, "humidity": {...}, "luminosity": {...}}
    Levanta ValueError (com uma mensagem clara) se algo estiver errado.
    """
    limpos = {}
    for atributo in ATRIBUTOS:
        if atributo not in novos:
            raise ValueError(f"Faltam os limites de {atributo}.")
        try:
            minimo = float(novos[atributo]["min"])
            maximo = float(novos[atributo]["max"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Os limites de {atributo} precisam ser números (min e max).")
        if minimo >= maximo:
            raise ValueError(f"Em {atributo}, o mínimo precisa ser menor que o máximo.")
        limpos[atributo] = {"min": minimo, "max": maximo}

    os.makedirs(os.path.dirname(ARQUIVO_TRIGGERS), exist_ok=True)
    with open(ARQUIVO_TRIGGERS, "w", encoding="utf-8") as arquivo:
        json.dump(limpos, arquivo, indent=2)
    return limpos


def avaliar(valores, limites):
    """
    Compara os valores atuais com os limites.
    Devolve (estados, comando):
      estados -> para cada atributo: "ok", "baixo", "alto" ou "sem_dado"
      comando -> "alerta_temp", "alerta_umid", "alerta_luz" ou "normal"
    """
    estados = {}
    for atributo in ATRIBUTOS:
        valor = valores.get(atributo)
        if valor is None:
            estados[atributo] = "sem_dado"
        elif valor < limites[atributo]["min"]:
            estados[atributo] = "baixo"
        elif valor > limites[atributo]["max"]:
            estados[atributo] = "alto"
        else:
            estados[atributo] = "ok"

    comando = "normal"
    for atributo, nome_comando in PRIORIDADE:
        if estados[atributo] in ("baixo", "alto"):
            comando = nome_comando
            break
    return estados, comando