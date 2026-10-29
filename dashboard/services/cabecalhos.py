"""
cabecalhos.py
Monta os headers das chamadas ao FIWARE.
Atenção: o Orion recusa (erro 400) GET e DELETE que tenham o header Content-Type.
"""
from config import FIWARE_SERVICE, FIWARE_SERVICEPATH


def para_leitura():
    """Headers para GET e DELETE (sem Content-Type)."""
    return {
        "fiware-service": FIWARE_SERVICE,
        "fiware-servicepath": FIWARE_SERVICEPATH,
    }


def para_escrita():
    """Headers para POST e PATCH, que enviam um corpo em JSON."""
    headers = para_leitura()
    headers["Content-Type"] = "application/json"
    return headers