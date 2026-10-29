"""
config.py
Configurações do dashboard. Lê o arquivo .env (na pasta dashboard) e define
os endereços, as portas e os nomes usados para falar com o FIWARE.
Quando o IP do servidor mudar, só o FIWARE_IP do arquivo .env precisa ser trocado.
"""
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env (se ele existir)
load_dotenv()

# --- Servidor FIWARE (o IP muda a cada sessão do laboratório da AWS) ---
FIWARE_IP = os.getenv("FIWARE_IP", "127.0.0.1")

# Portas dos serviços
PORTA_ORION = int(os.getenv("PORTA_ORION", "1026"))
PORTA_IOT_AGENT = int(os.getenv("PORTA_IOT_AGENT", "4041"))
PORTA_STH = int(os.getenv("PORTA_STH", "8666"))

# Endereços base usados pelo backend
ORION_URL = f"http://{FIWARE_IP}:{PORTA_ORION}"
IOT_AGENT_URL = f"http://{FIWARE_IP}:{PORTA_IOT_AGENT}"
STH_URL = f"http://{FIWARE_IP}:{PORTA_STH}"

# Headers padrão do FIWARE (separam os dados por "serviço")
FIWARE_SERVICE = os.getenv("FIWARE_SERVICE", "smart")
FIWARE_SERVICEPATH = os.getenv("FIWARE_SERVICEPATH", "/")

# --- Dispositivo padrão do projeto ---
API_KEY = os.getenv("API_KEY", "TEF")
DISPOSITIVO_PADRAO = os.getenv("DISPOSITIVO_PADRAO", "vinheria001")
ENTIDADE_PADRAO = os.getenv("ENTIDADE_PADRAO", "urn:ngsi-ld:Vinheria:001")
TIPO_PADRAO = os.getenv("TIPO_PADRAO", "Vinheria")

# Dispositivos que o dashboard não deixa apagar (protege o da apresentação)
DISPOSITIVOS_PROTEGIDOS = [DISPOSITIVO_PADRAO]

# Endereços usados DENTRO da rede do Docker (nomes de contêiner, não mudam com o IP)
STH_NOTIFY_URL = os.getenv("STH_NOTIFY_URL", "http://fiware-sth-comet:8666/notify")
IOT_AGENT_INTERNO = os.getenv("IOT_AGENT_INTERNO", "http://fiware-iot-agent:4041")

# Atributos medidos e comandos aceitos pelo dispositivo
ATRIBUTOS = ["temperature", "humidity", "luminosity"]
COMANDOS = ["alerta_temp", "alerta_umid", "alerta_luz", "normal"]

# Tempo máximo de espera nas chamadas ao FIWARE (em segundos)
TIMEOUT = 5

# Arquivo onde os limites (triggers) ficam salvos
ARQUIVO_TRIGGERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "triggers.json")