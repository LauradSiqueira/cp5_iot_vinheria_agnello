//Autor: Vinícius Valentim de Melo Ferreira + Laura de Siqueira Silva
//Resumo: Esse programa monitora temperatura, umidade e luminosidade de uma vinheria, mostra um painel de fácil leitura no monitor serial e publica os valores no Broker MQTT para o FIWARE (IoT Agent MQTT e STH-Comet). O alerta local por LED RGB e buzzer funciona mesmo sem internet e também pode ser acionado remotamente pelo dashboard.
//Revisões:
//Rev1: 08-10-2026 Código base com conexão Wi-Fi, MQTT, leitura dos sensores e alerta local
//Autor Rev1:
//Rev2: 09-10-2026 Painel de leitura no monitor serial, alerta local independente da internet e buzzer compatível com o core ESP32 2.x e 3.x
//Autor Rev2:
//Rev3: 22-10-2026 Módulo RTC DS1307 (I2C) para registrar data e hora de cada leitura junto com os dados do ambiente
//Autor Rev3:
//Rev4: 28-10-2026 Conexão completa com o FIWARE: tópicos montados por API_KEY e ID_DISPOSITIVO, recebe comandos do dashboard e confirma a execução
//Autor Rev4:
//Rev5: 29-10-2026 Controle automático do cooler (via módulo relé) pela temperatura do DHT: liga acima de 18 °C e desliga abaixo de 16 °C
//Autor Rev5:
#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Wire.h>
#include <RTClib.h>

// Configurações - variáveis editáveis
const char* SSID = "FIAP-IOT"; // Nome da rede Wi-Fi
const char* PASSWORD = "F!@p25.IOT"; // Senha da rede Wi-Fi
const int CANAL_WIFI = 6; // Canal do Wokwi-GUEST (conecta mais rápido no Wokwi)
const char* BROKER_MQTT = "3.84.183.67"; // IP do Broker MQTT. Muda quando a AWS é parada e ligada: confira em EC2 > Instâncias > IPv4 público
const int BROKER_PORT = 1883; // Porta do Broker MQTT
const char* API_KEY = "TEF"; // Prefixo dos tópicos, igual ao apikey do Service Group no FIWARE
const char* ID_DISPOSITIVO = "vinheria001"; // Device ID cadastrado no FIWARE
const char* ID_MQTT = "fiware_vinheria001"; // ID MQTT
const char* NOME_DISPOSITIVO = "VINHERIA 001"; // Nome mostrado no painel

// Pinos do circuito 
int pinDHT = 26;
int pinLDR = 34;
int pinBuzzer = 27;
int pinCooler = 25; // Gate do módulo relé que aciona o cooler

int pinR = 13; // LED RGB (cátodo comum)
int pinG = 12;
int pinB = 14;

int pinSDA = 21; // RTC DS1307 (I2C)
int pinSCL = 22;

#define DHTTYPE DHT11 // O circuito do Wokwi usa o DHT22
DHT dht(pinDHT, DHTTYPE);
RTC_DS1307 rtc;

// Limites de alerta
const float TEMP_MIN = 12.0; // °C
const float TEMP_MAX = 18.0; // °C
const float UMID_MIN = 60.0; // %
const float UMID_MAX = 75.0; // %
const int LUZ_MAX = 30;      // %

const float TEMP_COOLER_LIGA = 18.0;    // °C: acima disso o cooler liga
const float TEMP_COOLER_DESLIGA = 16.0; // °C: abaixo disso o cooler desliga

const bool BUZZER_ATIVO = true; // false deixa o buzzer em silêncio
const bool LDR_INVERTIDO = true; // Se o % de luz subir quando você cobrir o sensor, troque o valor
const unsigned long INTERVALO_LEITURA = 5000;
const int FUSO_HORARIO = -3; // Brasília (UTC-3), usado só para mostrar a hora no painel
const char* SERVIDOR_NTP = "pool.ntp.org";
const unsigned long INTERVALO_SINCRONIA = 21600000; // reacerta o RTC pela internet a cada 6 h
const unsigned long TEMPO_LIMITE_WIFI = 20000;
const unsigned long INTERVALO_RECONEXAO_WIFI = 10000;
const unsigned long INTERVALO_RECONEXAO_MQTT = 10000;
const unsigned long INTERVALO_PISCA_LED = 400; // LED azul pisca a cada 400 ms em alerta do dashboard
const int BEEP_FREQUENCIA = 2000;
const int CANAL_BUZZER = 0; // Usado apenas no core ESP32 2.x

// Padrões do buzzer, em milissegundos: ligado, desligado, ligado, desligado...
const unsigned long PADRAO_TEMP[] = {1000, 1500};                    // temperatura: 1 beep longo
const unsigned long PADRAO_UMID[] = {200, 200, 200, 1500};           // umidade: 2 beeps curtos
const unsigned long PADRAO_LUZ[]  = {200, 200, 200, 200, 200, 1500}; // luminosidade: 3 beeps curtos

float temperatura = 0;
float umidade = 0;
int luminosity = 0;
int statusTemp = 0; // -1 abaixo do ideal, 0 ok, 1 acima do ideal
int statusUmid = 0;
int statusLuz = 0;
bool leituraDHTok = false;
bool alerta = false; // alerta local (algum valor fora do limite)
bool coolerLigado = false;
bool envioOk = false;
char payload[96] = "";
char dataHoraUTC[24] = "";
char dataHoraLocal[24] = "";
bool rtcOk = false;
bool relogioSincronizado = false;
unsigned long numeroLeitura = 0;
unsigned long ultimaLeitura = 0;

// Alerta acionado pelo dashboard: 0 = normal | 1 = temperatura | 2 = umidade | 3 = luminosidade
int alertaRemoto = 0;

// Tópicos MQTT, montados a partir de API_KEY e ID_DISPOSITIVO
char topicoDados[64];    // ESP32 publica as leituras
char topicoComando[64];  // dashboard envia as ordens
char topicoResposta[64]; // ESP32 confirma que cumpriu a ordem

WiFiClient espClient;
PubSubClient MQTT(espClient);

void initSerial() {
    Serial.begin(115200);
}

void initWiFi() {
    delay(10);
    Serial.println("------Conexao WI-FI------");
    Serial.print("Conectando-se na rede: ");
    Serial.println(SSID);
    Serial.println("Aguarde");
    WiFi.mode(WIFI_STA);
    WiFi.begin(SSID, PASSWORD, CANAL_WIFI);
    unsigned long inicio = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - inicio < TEMPO_LIMITE_WIFI) {
        delay(250);
        Serial.print(".");
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("Conectado com sucesso na rede ");
        Serial.print("IP obtido: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("Sem Wi-Fi por enquanto. O alerta local continua funcionando e a conexão será tentada de novo.");
    }
}

void initRTC() {
    Wire.begin(pinSDA, pinSCL);
    rtcOk = rtc.begin();
    if (!rtcOk) {
        Serial.println("RTC não encontrado. Confira SDA (GPIO21), SCL (GPIO22) e a alimentação. Os dados seguem sem data e hora.");
        return;
    }
    if (!rtc.isrunning())
        rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
}

void initMQTT() {
    snprintf(topicoDados, sizeof(topicoDados), "/%s/%s/attrs", API_KEY, ID_DISPOSITIVO);
    snprintf(topicoComando, sizeof(topicoComando), "/%s/%s/cmd", API_KEY, ID_DISPOSITIVO);
    snprintf(topicoResposta, sizeof(topicoResposta), "/%s/%s/cmdexe", API_KEY, ID_DISPOSITIVO);
    MQTT.setServer(BROKER_MQTT, BROKER_PORT);
    MQTT.setCallback(callbackMQTT);
}

void initBuzzer() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcAttach(pinBuzzer, BEEP_FREQUENCIA, 8);
#else
    ledcSetup(CANAL_BUZZER, BEEP_FREQUENCIA, 8);
    ledcAttachPin(pinBuzzer, CANAL_BUZZER);
#endif
    ligarSom(false);
}

void InitOutput() {
    pinMode(pinLDR, INPUT);
    pinMode(pinBuzzer, OUTPUT);
    pinMode(pinCooler, OUTPUT);
    pinMode(pinR, OUTPUT);
    pinMode(pinG, OUTPUT);
    pinMode(pinB, OUTPUT);

    digitalWrite(pinCooler, LOW);
    setLed(LOW, LOW, LOW);
    initBuzzer();
}

void setup() {
    InitOutput();
    initSerial();
    initRTC();
    exibirLegenda();
    initWiFi();
    initMQTT();
    dht.begin();
    Serial.println("Aguardando a primeira leitura...");
}

void loop() {
    VerificaConexoesWiFIEMQTT();
    MQTT.loop();
    sincronizarRelogio();

    if (millis() - ultimaLeitura >= INTERVALO_LEITURA) {
        ultimaLeitura = millis();
        lerSensores();
        avaliarAlerta();
        controlarCooler();
        lerRelogio();
        publicarDados();
        exibirPainel();
    }

    atualizarLed();
    atualizarBuzzer();
}

void reconectWiFi() {
    static unsigned long ultimaTentativa = 0;
    if (WiFi.status() == WL_CONNECTED)
        return;
    if (millis() - ultimaTentativa < INTERVALO_RECONEXAO_WIFI)
        return;
    ultimaTentativa = millis();
    Serial.println("Wi-Fi desconectado, tentando reconectar");
    WiFi.disconnect();
    WiFi.begin(SSID, PASSWORD, CANAL_WIFI);
}

const char* motivoFalhaMQTT(int codigo) {
    if (codigo == -2) return "servidor inacessível, confira IP, porta 1883 e firewall";
    if (codigo == -4) return "tempo esgotado";
    return "erro MQTT";
}

void reconnectMQTT() {
    static unsigned long ultimaTentativa = 0;
    if (ultimaTentativa != 0 && millis() - ultimaTentativa < INTERVALO_RECONEXAO_MQTT)
        return;
    ultimaTentativa = millis();
    Serial.print("* Tentando se conectar ao Broker MQTT: ");
    Serial.println(BROKER_MQTT);
    if (MQTT.connect(ID_MQTT)) {
        Serial.println("Conectado com sucesso ao broker MQTT!");
        MQTT.subscribe(topicoComando); // passa a escutar as ordens do dashboard
        Serial.printf("Publicando leituras em: %s\n", topicoDados);
        Serial.printf("Escutando comandos em: %s\n", topicoComando);
    } else {
        Serial.printf("Falha ao conectar no broker (%s). Nova tentativa em %lu s.\n", motivoFalhaMQTT(MQTT.state()), INTERVALO_RECONEXAO_MQTT / 1000);
    }
}

void VerificaConexoesWiFIEMQTT() {
    reconectWiFi();
    if (WiFi.status() == WL_CONNECTED && !MQTT.connected())
        reconnectMQTT();
}

// Chamada automaticamente quando chega uma ordem do dashboard.
void callbackMQTT(char* topico, byte* dados, unsigned int tamanho) {
    char msg[64];
    unsigned int n = tamanho < sizeof(msg) - 1 ? tamanho : sizeof(msg) - 1;
    memcpy(msg, dados, n);
    msg[n] = '\0';
    Serial.printf("Comando recebido: %s\n", msg);

    char* arroba = strchr(msg, '@');
    if (arroba == NULL)
        return;
    char* comando = arroba + 1;
    char* barra = strchr(comando, '|');
    if (barra != NULL)
        *barra = '\0';

    if (strcmp(comando, "alerta_temp") == 0)
        alertaRemoto = 1;
    else if (strcmp(comando, "alerta_umid") == 0)
        alertaRemoto = 2;
    else if (strcmp(comando, "alerta_luz") == 0)
        alertaRemoto = 3;
    else if (strcmp(comando, "normal") == 0)
        alertaRemoto = 0;
    else {
        Serial.println("Comando desconhecido, ignorado.");
        return;
    }
    Serial.printf("Alerta do dashboard agora: %s\n", nomeAlertaRemoto());

    // Confirma ao FIWARE que cumpriu a ordem. Exemplo: vinheria001@alerta_temp|ok
    char resposta[80];
    snprintf(resposta, sizeof(resposta), "%s@%s|ok", ID_DISPOSITIVO, comando);
    MQTT.publish(topicoResposta, resposta);
}

const char* nomeAlertaRemoto() {
    if (alertaRemoto == 1) return "TEMPERATURA";
    if (alertaRemoto == 2) return "UMIDADE";
    if (alertaRemoto == 3) return "LUMINOSIDADE";
    return "nenhum";
}

// O RTC guarda a hora em UTC. A internet (NTP) acerta o relógio e, depois disso, ele segue sozinho
void sincronizarRelogio() {
    static bool iniciado = false;
    static unsigned long ultimaSincronia = 0;
    if (!rtcOk || WiFi.status() != WL_CONNECTED)
        return;
    if (!iniciado) {
        configTime(0, 0, SERVIDOR_NTP);
        iniciado = true;
    }
    if (relogioSincronizado && millis() - ultimaSincronia < INTERVALO_SINCRONIA)
        return;
    time_t agora = time(nullptr);
    if (agora < 1700000000)
        return;
    rtc.adjust(DateTime((uint32_t)agora));
    relogioSincronizado = true;
    ultimaSincronia = millis();
    Serial.println("Relógio (RTC) acertado pela internet.");
}

void lerRelogio() {
    dataHoraUTC[0] = '\0';
    dataHoraLocal[0] = '\0';
    if (!rtcOk)
        return;
    DateTime utc = rtc.now();
    if (!utc.isValid())
        return;
    DateTime local = utc + TimeSpan(0, FUSO_HORARIO, 0, 0);
    snprintf(dataHoraUTC, sizeof(dataHoraUTC), "%04d-%02d-%02dT%02d:%02d:%02dZ",
             utc.year(), utc.month(), utc.day(), utc.hour(), utc.minute(), utc.second());
    snprintf(dataHoraLocal, sizeof(dataHoraLocal), "%02d/%02d/%04d %02d:%02d:%02d",
             local.day(), local.month(), local.year(), local.hour(), local.minute(), local.second());
}

void setLed(bool r, bool g, bool b) {
    digitalWrite(pinR, r);
    digitalWrite(pinG, g);
    digitalWrite(pinB, b);
}

void ligarSom(bool ligar) {
    int frequencia = ligar ? BEEP_FREQUENCIA : 0;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWriteTone(pinBuzzer, frequencia);
#else
    ledcWriteTone(CANAL_BUZZER, frequencia);
#endif
}

void lerSensores() {
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (isnan(t) || isnan(h)) { // tenta mais uma vez se a primeira leitura falhar
        delay(500);
        t = dht.readTemperature();
        h = dht.readHumidity();
    }
    leituraDHTok = !(isnan(t) || isnan(h));
    if (leituraDHTok) {
        temperatura = t;
        umidade = h;
    }

    int leitura = analogRead(pinLDR);
    if (LDR_INVERTIDO)
        leitura = 4095 - leitura;
    luminosity = constrain(map(leitura, 0, 4095, 0, 100), 0, 100);
}

int classificar(float valor, float minimo, float maximo) {
    if (valor < minimo) return -1;
    if (valor > maximo) return 1;
    return 0;
}

// Compara as leituras com os limites e guarda o resultado
void avaliarAlerta() {
    statusLuz = classificar(luminosity, 0, LUZ_MAX);
    statusTemp = leituraDHTok ? classificar(temperatura, TEMP_MIN, TEMP_MAX) : 0;
    statusUmid = leituraDHTok ? classificar(umidade, UMID_MIN, UMID_MAX) : 0;
    alerta = statusTemp != 0 || statusUmid != 0 || statusLuz != 0;
}

// Entre 16 e 18 °C o cooler mantém o estado atual (evita liga/desliga repetido)
void controlarCooler() {
    if (!leituraDHTok)
        return;
    if (temperatura > TEMP_COOLER_LIGA)
        coolerLigado = true;
    else if (temperatura < TEMP_COOLER_DESLIGA)
        coolerLigado = false;
    digitalWrite(pinCooler, coolerLigado);
}

// Formato UltraLight 2.0: chave|valor|chave|valor (t = temperature, h = humidity, l = luminosity, ts = data e hora do RTC em UTC)
void publicarDados() {
    int n;
    if (leituraDHTok)
        n = snprintf(payload, sizeof(payload), "t|%.1f|h|%.1f|l|%d", temperatura, umidade, luminosity);
    else
        n = snprintf(payload, sizeof(payload), "l|%d", luminosity);
    if (dataHoraUTC[0] != '\0')
        snprintf(payload + n, sizeof(payload) - n, "|ts|%s", dataHoraUTC);

    envioOk = MQTT.connected() && MQTT.publish(topicoDados, payload);
}

// Qual alerta está ativo: 0 = nenhum | 1 = temperatura | 2 = umidade | 3 = luminosidade
// O comando do dashboard tem prioridade sobre o alerta local
int tipoAlertaAtual() {
    if (alertaRemoto != 0) return alertaRemoto;
    if (statusTemp != 0) return 1;
    if (statusUmid != 0) return 2;
    if (statusLuz != 0) return 3;
    return 0;
}

// Verde = seguro | Vermelho = valor fora do limite | Azul fixo = DHT sem leitura | Azul piscando = alerta do dashboard
void atualizarLed() {
    static unsigned long ultimaTroca = 0;
    static bool azulLigado = false;

    if (alertaRemoto != 0) {
        if (millis() - ultimaTroca >= INTERVALO_PISCA_LED) {
            ultimaTroca = millis();
            azulLigado = !azulLigado;
            setLed(LOW, LOW, azulLigado);
        }
        return;
    }
    azulLigado = false;
    if (alerta)
        setLed(HIGH, LOW, LOW);
    else if (leituraDHTok)
        setLed(LOW, HIGH, LOW);
    else
        setLed(LOW, LOW, HIGH);
}

// Buzzer toca um padrão diferente para cada tipo de alerta
void atualizarBuzzer() {
    static int etapa = 0;
    static unsigned long ultimaTroca = 0;
    static int tipoAnterior = 0;

    int tipo = tipoAlertaAtual();

    // Se o alerta mudou, recomeça o padrão do zero
    if (tipo != tipoAnterior) {
        tipoAnterior = tipo;
        etapa = 0;
        ultimaTroca = millis();
        ligarSom(tipo != 0 && BUZZER_ATIVO);
        return;
    }
    if (tipo == 0 || !BUZZER_ATIVO)
        return;

    const unsigned long* padrao;
    int tamanho;
    if (tipo == 1) {
        padrao = PADRAO_TEMP;
        tamanho = 2;
    } else if (tipo == 2) {
        padrao = PADRAO_UMID;
        tamanho = 4;
    } else {
        padrao = PADRAO_LUZ;
        tamanho = 6;
    }

    if (millis() - ultimaTroca >= padrao[etapa]) {
        ultimaTroca = millis();
        etapa = (etapa + 1) % tamanho;
        ligarSom(etapa % 2 == 0); // etapa par = apitando, etapa ímpar = em silêncio
    }
}

void listarParametros(int alvo) {
    bool primeiro = true;
    const char* nomes[3] = {"Temperatura", "Umidade", "Luminosidade"};
    int status[3] = {statusTemp, statusUmid, statusLuz};
    for (int i = 0; i < 3; i++) {
        if (status[i] == alvo) {
            Serial.printf("%s%s", primeiro ? "" : ", ", nomes[i]);
            primeiro = false;
        }
    }
    if (primeiro) Serial.print("nenhum");
    Serial.println();
}

void exibirLegenda() {
    Serial.println();
    Serial.println("Como ler os avisos da vinheria:");
    Serial.println("  LED verde         = SEGURO");
    Serial.println("  LED vermelho      = CRÍTICO (valor fora do limite, o buzzer apita)");
    Serial.println("  LED azul fixo     = sensor de temperatura e umidade sem leitura");
    Serial.println("  LED azul piscando = alerta acionado pelo dashboard (o buzzer apita)");
}

void exibirPainel() {
    numeroLeitura++;
    bool critico = alerta || alertaRemoto != 0 || !leituraDHTok;

    Serial.println();
    Serial.println("==============================================");
    Serial.printf(" %s | leitura %lu\n", NOME_DISPOSITIVO, numeroLeitura);
    Serial.printf(" Data e hora: %s\n", dataHoraLocal[0] ? dataHoraLocal : "sem leitura do relógio (RTC)");
    if (leituraDHTok)
        Serial.printf(" Temperatura: %.1f °C | Luminosidade: %d %% | Umidade: %.1f %%\n", temperatura, luminosity, umidade);
    else
        Serial.printf(" Temperatura: sem leitura | Luminosidade: %d %% | Umidade: sem leitura\n", luminosity);
    Serial.printf(" ESTADO: %s\n", critico ? "CRÍTICO" : "SEGURO");
    if (alerta || !leituraDHTok) {
        Serial.print(" Acima do recomendado: ");
        listarParametros(1);
        Serial.print(" Abaixo do recomendado: ");
        listarParametros(-1);
        if (!leituraDHTok) Serial.println(" Atenção: sensor DHT sem leitura");
    }
    Serial.printf(" Alerta do dashboard: %s\n", nomeAlertaRemoto());
    Serial.printf(" Conexão: Wi-Fi %s | Servidor %s | Último envio %s\n",
                  WiFi.status() == WL_CONNECTED ? "OK" : "FORA",
                  MQTT.connected() ? "OK" : "FORA",
                  envioOk ? "OK" : "falhou");
    Serial.println("==============================================");