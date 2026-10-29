"use strict";

/* ============================ 1. CONFIGURAÇÕES E ESTADO ============================ */
const INTERVALO_MS = 5000;          // Intervalo de atualização (5s)
const FUSO = "America/Sao_Paulo";   // Fuso horário exibido nas telas
const ENTIDADE_FALLBACK = "urn:ngsi-ld:Vinheria:001";
const TIPO_FALLBACK = "Vinheria";

const LIMITES_INICIAIS = {
  temperature: { min: 12, max: 18 },
  humidity: { min: 60, max: 75 },
  luminosity: { min: 0, max: 30 },
};

const ATRIBUTOS = {
  temperature: { nome: "Temperatura", unidade: "°C", casas: 1 },
  humidity: { nome: "Umidade", unidade: "%", casas: 1 },
  luminosity: { nome: "Luminosidade", unidade: "%", casas: 0 },
};

const COMANDOS = {
  alerta_temp: "temperatura fora do limite (1 beep longo)",
  alerta_umid: "umidade fora do limite (2 beeps curtos)",
  alerta_luz: "luminosidade fora do limite (3 beeps curtos)",
  normal: "tudo normal",
};

const ROTULOS_ESTADO = {
  ok: "Normal",
  alto: "Acima do limite",
  baixo: "Abaixo do limite",
  sem_dado: "Sem dados",
};

const PAGINAS = {
  "visao-geral": ["Visão geral", "Valores atuais e estado dos alertas."],
  "historico": ["Histórico e gráficos", "Leituras gravadas no STH-Comet."],
  "dispositivos": ["Dispositivos", "Cadastre e gerencie os dispositivos IoT."],
  "limites": ["Limites e alertas", "Defina quando o LED azul e o buzzer devem ser acionados."],
};

const estado = {
  entidade: ENTIDADE_FALLBACK,
  tipo: TIPO_FALLBACK,
  dispositivos: [],
  limites: JSON.parse(JSON.stringify(LIMITES_INICIAIS)),
  graficos: {},
  historico: {},
  tentativa: { comando: null, em: 0 },
  ocupado: false,
};

/* ============================ 2. FUNÇÕES DE APOIO ============================ */
const $ = (id) => document.getElementById(id);

function criar(tag, atributos = {}, filhos = []) {
  const elemento = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (chave === "texto") elemento.textContent = valor;
    else elemento.setAttribute(chave, valor);
  }
  for (const filho of [].concat(filhos)) elemento.append(filho);
  return elemento;
}

async function api(caminho, opcoes = {}) {
  let resposta;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch (e) {
    throw new Error("Sem conexão com o servidor do dashboard.");
  }

  let corpo = null;
  try {
    corpo = await resposta.json();
  } catch (e) {
    corpo = null;
  }
  if (!resposta.ok) throw new Error((corpo && corpo.erro) || `Erro ${resposta.status}`);
  return corpo;
}

function enviarJson(metodo, corpo) {
  return { method: metodo, headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) };
}

function parametrosDispositivo() {
  return `entidade=${encodeURIComponent(estado.entidade)}&tipo=${encodeURIComponent(estado.tipo)}`;
}

let temporizadorAviso = null;

function avisar(texto, tipo = "ok") {
  const aviso = $("aviso");
  aviso.textContent = texto;
  aviso.className = `aviso ${tipo}`;
  aviso.hidden = false;
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => { aviso.hidden = true; }, 5000);
}

function formatarHora(iso) {
  return new Date(iso).toLocaleTimeString("pt-BR", { timeZone: FUSO });
}

function formatarDataHora(iso) {
  return new Date(iso).toLocaleString("pt-BR", { timeZone: FUSO });
}

function formatarNumero(valor, casas) {
  if (valor === null || valor === undefined) return "--";
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

function formatarLimite(valor) {
  return valor.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
}

function corDoTema(nome) {
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || "#6b1f3a";
}

function definirConexao(ligado, mensagem = "") {
  $("conexao-ponto").className = `ponto ${ligado ? "ligado" : "desligado"}`;
  $("conexao-texto").textContent = ligado
    ? `Conectado. Atualizado às ${new Date().toLocaleTimeString("pt-BR", { timeZone: FUSO })}`
    : "Sem conexão";
  const banner = $("banner");
  banner.hidden = ligado;
  if (!ligado) banner.textContent = `Não foi possível atualizar os dados. ${mensagem}`;
}

/* ============================ 3. NAVEGAÇÃO ============================ */
function paginaAtual() {
  const nome = location.hash.replace("#", "");
  return PAGINAS[nome] ? nome : "visao-geral";
}

function mostrarPagina() {
  const atual = paginaAtual();
  for (const nome of Object.keys(PAGINAS)) {
    $(`pagina-${nome}`).hidden = nome !== atual;
    const link = document.querySelector(`[data-pagina="${nome}"]`);
    link.classList.toggle("ativo", nome === atual);
    if (nome === atual) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  $("titulo-pagina").textContent = PAGINAS[atual][0];
  $("subtitulo-pagina").textContent = PAGINAS[atual][1];

  if (atual === "historico") carregarHistorico();
  if (atual === "dispositivos") carregarDispositivos().catch((e) => avisar(e.message, "erro"));
  if (atual === "limites") carregarLimites().catch((e) => avisar(e.message, "erro"));
}

/* ============================ 4. VISÃO GERAL ============================ */
function mostrarStatus(r) {
  estado.limites = r.limites;
  for (const [atributo, info] of Object.entries(ATRIBUTOS)) {
    const cartao = document.querySelector(`[data-atributo="${atributo}"]`);
    const situacao = r.estados[atributo];

    cartao.querySelector("[data-valor]").textContent = formatarNumero(r.valores[atributo], info.casas);
    const chip = cartao.querySelector("[data-chip]");
    chip.textContent = ROTULOS_ESTADO[situacao];
    chip.className = `chip ${situacao}`;
    const limite = r.limites[atributo];
    cartao.querySelector("[data-faixa]").textContent =
      `Faixa ideal: ${formatarLimite(limite.min)} a ${formatarLimite(limite.max)} ${info.unidade}`;
    cartao.classList.toggle("fora", situacao === "alto" || situacao === "baixo");
  }
  $("resumo-alerta").textContent = r.comando_sugerido === "normal"
    ? "Tudo dentro dos limites. O dispositivo deve estar sem alerta."
    : `Alerta: ${COMANDOS[r.comando_sugerido]}. O LED azul deve piscar e o buzzer deve tocar.`;
  $("ultimo-comando").textContent = r.ultimo_comando || "nenhum";
}

async function enviarComando(nome, origem) {
  try {
    await api("/api/comando", enviarJson("POST", { comando: nome, entidade: estado.entidade, tipo: estado.tipo }));
    $("ultimo-comando").textContent = nome;
    avisar(`Comando "${nome}" enviado ao dispositivo (${origem}).`);
    return true;
  } catch (e) {
    avisar(`Falha ao enviar "${nome}": ${e.message}`, "erro");
    return false;
  }
}

async function aplicarAutomacao(r) {
  if (!$("automatico").checked) return;
  if (r.comando_sugerido === r.ultimo_comando) return;
  const tentativa = estado.tentativa;
  if (tentativa.comando === r.comando_sugerido && Date.now() - tentativa.em < 15000) return;
  estado.tentativa = { comando: r.comando_sugerido, em: Date.now() };
  await enviarComando(r.comando_sugerido, "automático");
}

async function atualizarStatus() {
  try {
    const r = await api(`/api/status?${parametrosDispositivo()}`);
    definirConexao(true);
    mostrarStatus(r);
    await aplicarAutomacao(r);
  } catch (e) {
    definirConexao(false, e.message);
  }
}

async function comandoManual(nome) {
  $("automatico").checked = false;
  const enviado = await enviarComando(nome, "teste manual");
  if (enviado) avisar(`Comando "${nome}" enviado. Os alertas automáticos foram desligados para o teste.`);
}

/* ============================ 5. HISTÓRICO E GRÁFICOS ============================ */
function criarGraficos() {
  if (typeof Chart === "undefined") {
    avisar("A biblioteca de gráficos não foi encontrada (static/js/chart.umd.js).", "erro");
    return;
  }
  for (const [atributo, info] of Object.entries(ATRIBUTOS)) {
    const linha = corDoTema("--cor-linha");
    const alerta = corDoTema("--cor-alerta");
    estado.graficos[atributo] = new Chart($(`grafico-${atributo}`), {
      type: "line",
      data: {
        labels: [],
        datasets: [
          { label: info.nome, data: [], borderColor: linha, backgroundColor: linha, borderWidth: 2, pointRadius: 2, tension: 0.25 },
          { label: "Limite máximo", data: [], borderColor: alerta, borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0 },
          { label: "Limite mínimo", data: [], borderColor: alerta, borderDash: [2, 4], borderWidth: 1.5, pointRadius: 0 },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: { y: { title: { display: true, text: info.unidade } } },
        plugins: { legend: { position: "bottom" } },
      },
    });
  }
}

function desenharGrafico(atributo, leituras) {
  estado.historico[atributo] = leituras;
  const grafico = estado.graficos[atributo];
  const limite = estado.limites[atributo];
  if (grafico) {
    grafico.data.labels = leituras.map((l) => formatarHora(l.hora));
    grafico.data.datasets[0].data = leituras.map((l) => l.valor);
    grafico.data.datasets[1].data = leituras.map(() => limite.max);
    grafico.data.datasets[2].data = leituras.map(() => limite.min);
    grafico.update("none");
  }
  const info = ATRIBUTOS[atributo];
  const ultima = leituras[leituras.length - 1];
  $(`ultima-${atributo}`).textContent = ultima
    ? `Última leitura: ${formatarNumero(ultima.valor, info.casas)} ${info.unidade} em ${formatarDataHora(ultima.hora)}`
    : "Ainda não há leituras gravadas para este sensor.";
}

async function carregarHistorico() {
  const quantidade = $("quantidade").value;
  const dataInicio = $("data-inicio") ? $("data-inicio").value : "";
  const dataFim = $("data-fim") ? $("data-fim").value : "";

  try {
    await Promise.all(Object.keys(ATRIBUTOS).map(async (atributo) => {
      let url = `/api/historico?atributo=${atributo}&quantidade=${quantidade}&${parametrosDispositivo()}`;
      
      if (dataInicio) url += `&data_inicio=${dataInicio}`;
      if (dataFim) url += `&data_fim=${dataFim}`;

      const r = await api(url);
      desenharGrafico(atributo, r.leituras);
    }));
  } catch (e) {
    avisar(`Não foi possível carregar o histórico. ${e.message}`, "erro");
  }
}

function limparFiltroData() {
  if ($("data-inicio")) $("data-inicio").value = "";
  if ($("data-fim")) $("data-fim").value = "";
  carregarHistorico();
}

function baixarCsv(atributo) {
  const leituras = estado.historico[atributo] || [];
  const info = ATRIBUTOS[atributo];
  const linhas = [`data_hora;${info.nome} (${info.unidade})`];
  for (const l of leituras) linhas.push(`${formatarDataHora(l.hora)};${String(l.valor).replace(".", ",")}`);
  const blob = new Blob(["\ufeff" + linhas.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = criar("a", { href: url, download: `historico_${atributo}.csv` });
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/* ============================ 6. DISPOSITIVOS ============================ */
function preencherSeletor(lista) {
  const seletor = $("dispositivo");
  const anterior = seletor.value;
  seletor.replaceChildren(...lista.map((d) => criar("option", { value: d.device_id, texto: d.device_id })));
  const existe = lista.some((d) => d.device_id === anterior);
  const padrao = lista.find((d) => d.protegido) || lista[0];
  if (existe) seletor.value = anterior;
  else if (padrao) seletor.value = padrao.device_id;
  escolherDispositivo(seletor.value);
}

function escolherDispositivo(deviceId) {
  const d = estado.dispositivos.find((item) => item.device_id === deviceId);
  if (d) {
    estado.entidade = d.entity_name;
    estado.tipo = d.entity_type;
  }
}

function criarLinhaDispositivo(d) {
  const apagar = criar("button", { type: "button", class: "botao perigo", texto: "Apagar" });
  if (d.protegido) {
    apagar.disabled = true;
    apagar.title = "Dispositivo principal do projeto";
  } else {
    apagar.addEventListener("click", () => apagarDispositivo(d.device_id));
  }
  return criar("tr", {}, [
    criar("td", { texto: d.device_id }),
    criar("td", { texto: d.entity_name }),
    criar("td", { texto: d.entity_type }),
    criar("td", { texto: d.atributos.join(", ") }),
    criar("td", { texto: d.comandos.join(", ") }),
    criar("td", {}, [apagar]),
  ]);
}

async function carregarDispositivos() {
  const lista = await api("/api/dispositivos");
  estado.dispositivos = lista;
  preencherSeletor(lista);
  $("tabela-dispositivos").replaceChildren(...lista.map(criarLinhaDispositivo));
  $("sem-dispositivos").hidden = lista.length > 0;
}

function mostrarResultadoCadastro(r) {
  const caixa = $("resultado-cadastro");
  const subs = r.subscriptions.map((s) => `${s.atributo}: ${s.codigo}`).join(" | ");

  caixa.replaceChildren(
    criar("p", {}, [criar("strong", { texto: `Dispositivo "${r.device_id}" cadastrado.` })]),
    criar("p", { texto: `Entidade: ${r.entity_name} (tipo ${r.entity_type})` }),
    criar("p", { texto: `Subscriptions do histórico: ${subs}` }),
    criar("p", { texto: `Registro dos comandos: ${r.registro_comandos}` }),
    criar("p", { texto: `No ESP32, publique em /TEF/${r.device_id}/attrs e escute /TEF/${r.device_id}/cmd.` }),
  );
  caixa.hidden = false;
}

async function cadastrarDispositivo(evento) {
  evento.preventDefault();
  const nome = $("device_id").value.trim();
  try {
    const r = await api("/api/dispositivos", enviarJson("POST", { device_id: nome }));
    mostrarResultadoCadastro(r);
    $("form-dispositivo").reset();
    await carregarDispositivos();
    avisar(`Dispositivo "${nome}" cadastrado.`);
  } catch (e) {
    avisar(e.message, "erro");
  }
}

async function apagarDispositivo(deviceId) {
  const certeza = confirm(`Apagar o dispositivo "${deviceId}"? Isso remove o cadastro, as subscriptions e a entidade dele.`);
  if (!certeza) return;
  try {
    await api(`/api/dispositivos/${encodeURIComponent(deviceId)}`, { method: "DELETE" });
    avisar(`Dispositivo "${deviceId}" apagado.`);
    $("resultado-cadastro").hidden = true;
    await carregarDispositivos();
  } catch (e) {
    avisar(e.message, "erro");
  }
}

/* ============================ 7. LIMITES (TRIGGERS) ============================ */
function preencherFormLimites(limites) {
  for (const atributo of Object.keys(ATRIBUTOS)) {
    $(`lim-${atributo}-min`).value = limites[atributo].min;
    $(`lim-${atributo}-max`).value = limites[atributo].max;
  }
}

async function carregarLimites() {
  const limites = await api("/api/triggers");
  estado.limites = limites;
  preencherFormLimites(limites);
}

async function salvarLimites(evento) {
  evento.preventDefault();
  const novos = {};
  for (const atributo of Object.keys(ATRIBUTOS)) {
    novos[atributo] = {
      min: parseFloat($(`lim-${atributo}-min`).value),
      max: parseFloat($(`lim-${atributo}-max`).value),
    };
  }
  try {
    estado.limites = await api("/api/triggers", enviarJson("POST", novos));
    avisar("Limites salvos. Os alertas passam a usar os novos valores na próxima leitura.");
  } catch (e) {
    avisar(e.message, "erro");
  }
}

/* ============================ 8. INICIALIZAÇÃO ============================ */
async function ciclo() {
  if (estado.ocupado) return;
  estado.ocupado = true;
  try {
    await atualizarStatus();
    if (paginaAtual() === "historico") await carregarHistorico();
  } finally {
    estado.ocupado = false;
  }
}

function ligarEventos() {
  window.addEventListener("hashchange", mostrarPagina);
  $("dispositivo").addEventListener("change", (e) => {
    escolherDispositivo(e.target.value);
    estado.tentativa = { comando: null, em: 0 };
    atualizarStatus();
    if (paginaAtual() === "historico") carregarHistorico();
  });
  document.querySelectorAll("[data-comando]").forEach((botao) => {
    botao.addEventListener("click", () => comandoManual(botao.dataset.comando));
  });
  document.querySelectorAll("[data-csv]").forEach((botao) => {
    botao.addEventListener("click", () => baixarCsv(botao.dataset.csv));
  });
  $("quantidade").addEventListener("change", carregarHistorico);
  $("atualizar-historico").addEventListener("click", carregarHistorico);
  
  if ($("limpar-historico")) {
    $("limpar-historico").addEventListener("click", limparFiltroData);
  }
  if ($("data-inicio")) $("data-inicio").addEventListener("change", carregarHistorico);
  if ($("data-fim")) $("data-fim").addEventListener("change", carregarHistorico);

  $("form-dispositivo").addEventListener("submit", cadastrarDispositivo);
  $("form-limites").addEventListener("submit", salvarLimites);
  $("restaurar-limites").addEventListener("click", () => preencherFormLimites(LIMITES_INICIAIS));
}

async function iniciar() {
  criarGraficos();
  ligarEventos();
  try {
    await carregarDispositivos();
  } catch (e) {
    avisar(`Não foi possível listar os dispositivos. ${e.message}`, "erro");
  }
  mostrarPagina();
  await atualizarStatus();
  setInterval(ciclo, INTERVALO_MS);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
else iniciar();