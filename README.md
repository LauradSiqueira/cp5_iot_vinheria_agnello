# Sobre


Solução de Internet das Coisas (IoT) voltada ao monitoramento global de vinherias, composta por um dispositivo embarcado baseado em ESP32 e por um dashboard dinâmico para análise de dados históricos e geração de alertas.

O sistema monitora continuamente as condições de um ambiente fechado, registrando temperatura, umidade e luminosidade, cada leitura acompanhada de data e horário obtidos por um módulo de relógio em tempo real (RTC). O circuito é instalado no interior de uma caixa de madeira, estrutura que isola o ambiente e possibilita um controle mais preciso de suas condições. Ao ser acondicionada a garrafa de vinho, todas as informações coletadas passam a ser armazenadas no dashboard local, formando um histórico consultável das condições de conservação.

Quando a temperatura excede o limite recomendado, o circuito aciona automaticamente um cooler, que atua como exaustor, extraindo o ar quente da caixa e expelindo-o para o exterior. Caso qualquer variável saia da faixa ideal, o dispositivo emite alertas locais por meio de LED RGB e buzzer, os quais permanecem operantes mesmo sem conexão com a internet.

Principais características:

- Monitoramento de temperatura, umidade e luminosidade com registro de data e horário
- Controle automático de temperatura por cooler acionado via módulo relé
- Comunicação via protocolo MQTT com a plataforma FIWARE
- Dashboard dinâmico para análise de dados históricos e geração de alertas
- Alertas sonoros e visuais locais, além de alertas acionados remotamente pelo dashboard
- Servidor hospedado em nuvem (AWS EC2)
  
# Integrantes

- Vinícius Valentim de Melo Ferreira - RM570502
- Laura de Siqueira Silva - RM573796

Sala: ESPH - 2026

# Peças utilizadas

- ESP32 DevKit 1
- Sensor DHT11 (DHT22 na simulação do Wokwi)
- RTC DS1307
- Módulo relé
- Módulo LDR
- Buzzer
- LED RGB
- Três resistores
- Cooler 12V

# Programas utilizados

- AWS Academy: hospedagem do servidor na nuvem
- Postman: controle do LED
- Wokwi: simulação e prototipação
- Arduino IDE: gravação do código no ESP32

# Como executar

1. Crie e configure uma instância (EC2) dentro do AWS Academy.
2. Copie o IP público da instância.
3. No arquivo `sketch.ino`, informe esse IP na variável `BROKER_MQTT`, para que o circuito se conecte ao servidor.
4. Grave o código no ESP32 pela Arduino IDE (ou execute a simulação no Wokwi).
5. Com o circuito conectado, as informações do ambiente passam a ser salvas no dashboard local, junto com a data e o horário em que foram registradas.

# Simulação no Wokwi
[Simulação pública do circuito](https://wokwi.com/projects/479263142062213121)

# Vídeo Demonstração
[Showcase do projeto](https://youtu.be/LpG0P6CEJiU?is=einwP0Q310-Sl4f7)

# Referências
[Fiware](https://github.com/fabiocabrini/fiware)
