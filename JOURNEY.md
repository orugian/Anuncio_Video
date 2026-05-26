# 🗺️ Ad Pipeline System — Journey Log

> **Agente:** Madara (Senior AI Engineer)
> **Data de Atualização:** 13 de Maio de 2026
> **Status Atual:** Phase 1 (Core Extraction) Concluída.

---

## 🎯 Objetivo Original do Projeto
Construir um pipeline multi-agente automatizado que recebe URLs de anúncios via Telegram, extrai o conteúdo do produto, processa via LLMs e gera vídeos publicitários usando IA (Higgsfield). Todo o estado deve ser persistido (Axioma: Idempotência e Rastreabilidade).

---

## 🏗️ Arquitetura Implementada (Phase 1)

A base do sistema foi estabelecida com foco em estabilidade e acurácia de dados:

1.  **Gateway (Telegram Bot):** Interface de entrada configurada como um serviço `systemd` (`madara_bot.service`) operando 24/7 no Ubuntu. Possui filtro rígido de `AUTHORIZED_USER_ID`.
2.  **Orchestrator (Hermes):** O cérebro do fluxo. Coordena transições de estado (`JobStatus`) e garante que falhas em estágios isolados não quebrem o sistema.
3.  **Data Persistence (Supabase):** Schema estruturado com tabelas independentes:
    *   `jobs`: Controle de estado e ciclo de vida.
    *   `scraped_content`: HTML resumido e lista bruta de imagens.
    *   `semantic_context`: Dados técnicos organizados via IA.
4.  **Extraction Layer:**
    *   **ScraperService:** Evoluiu de requests simples para um motor de renderização stealth assíncrono (`scrapling.StealthyFetcher`).
    *   **DataExtractor (Gemini 2.0 Flash Lite):** Refatorado para focar estritamente em **Dados Técnicos** (JSON estruturado com preço, specs e mídia) ao invés de atuar como copywriter prematuramente.

---

## ⚔️ Desafios Superados e Pivôs Estratégicos

### 1. O Desafio do WAF Enterprise (Datadome)
*   **Problema:** Ao testar URLs do Mercado Livre e Amazon, o pipeline falhava na extração de dados reais, capturando apenas textos de "Acesse sua conta".
*   **Diagnóstico:** Identificamos que firewalls de IA (como o Datadome) bloqueiam nativamente requisições provenientes de IPs de Data Centers (nossa VPS), ocorrendo na camada de rede antes mesmo de o JavaScript carregar.
*   **Solução Atual:** Validamos a integridade e precisão do pipeline inteiro (Bot -> Scraper -> Gemini -> BD) usando e-commerces padrão (ex: loja oficial da Redragon), comprovando o funcionamento da lógica do código.
*   **Solução Futura (Backlog):** Para operar em e-commerces Tier-1, o `ScraperService` precisará ser roteado via uma API de Proxy Residencial (ex: ScraperAPI).

### 2. De "Semantic Copywriter" para "Data Extractor"
*   **Problema Inicial:** O Gemini estava programado para extrair "Dores, Ganchos e Benefícios" diretamente do HTML bruto.
*   **Pivô (Insight do Usuário):** Foi percebido que pedir criatividade na fase de extração gera alucinações (ex: perda de preços ou inventar especificações). 
*   **Ação Corretiva:** O prompt foi reescrito sob regras rígidas de formatação JSON (`response_format: json_object`). Agora o Gemini atua cirurgicamente encontrando valores monetários, specs de hardware e filtrando URLs de imagens pertinentes ao produto.

### 3. Filtro de Ruído Visual
*   **Ação Corretiva:** Implementamos uma heurística no Scraper que elimina imagens de UI comuns em e-commerces (logos de cartões de crédito, selos de frete, ícones de redes sociais), entregando ao Gemini uma lista muito mais limpa para a seleção final de mídia.

---

## 🏗️ Arquitetura Implementada (Phase 2 - Marketing & Feedback)

A base do sistema evoluiu de uma extração passiva para um ciclo interativo:

1.  **Marketing Layer (Claude 4 Sonnet):** Implementado o `MarketingOrganizer`. O sistema agora transforma dados técnicos em roteiros AIDA/PAS estruturados.
2.  **Interactive Feedback Loop (Telegram):**
    *   **Pausa para Aprovação:** O orquestrador agora pausa no estado `awaiting_approval` e notifica o usuário via botões Inline no Telegram.
    *   **Refinamento via IA:** Se o usuário solicitar ajustes, o agente de marketing reescreve o roteiro mantendo o contexto histórico e técnico.
3.  **Persistência de Iterações:** A tabela `marketing_scripts` agora armazena não apenas o script final, mas todo o `feedback_history` do usuário.

---

## ⚔️ Desafios Superados e Pivôs Estratégicos (Maio/2026)

### 1. Depreciação de Modelos e Parsing de Markdown
*   **Problema:** O modelo `claude-3.5-sonnet` foi descontinuado no OpenRouter. Além disso, as IAs estavam envolvendo o JSON em blocos markdown, quebrando o parsing.
*   **Solução:** Atualizamos para `anthropic/claude-sonnet-4` e implementamos um "Markdown Stripper" robusto no `MarketingOrganizer`.

### 2. Sincronização Hermes <-> Telegram Bot
*   **Desafio:** O orquestrador precisava enviar mensagens proativamente fora do fluxo normal de comando do bot.
*   **Solução:** Implementamos a injeção do objeto `Bot` no orquestrador, permitindo que o Hermes notifique o usuário assim que o roteiro estiver pronto.

---

## 🚀 Próximos Passos (Phase 3)

Com o fluxo de texto validado e aprovado pelo usuário, o foco agora é a execução audiovisual:

1.  **Video Generation (Muapi.ai/Kling):**
    *   **Status:** Código base implementado em `services/video/generator.py`.
    *   **Bloqueio:** Aguardando recarga de créditos (Erro 402).
2.  **Final Assembly:** Unir as cenas geradas em um arquivo final de vídeo (FFmpeg) e entregar via Telegram.
3.  **Analytics & Cost Tracking:** Implementar logs de custo por job baseados nos tokens do OpenRouter e créditos do Muapi.

