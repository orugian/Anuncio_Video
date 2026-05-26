# MADARA PROJECT - SESSION HANDOFF

## 1. Contexto Geral e Objetivo
O projeto consiste no desenvolvimento do **Ad Pipeline System**, um orquestrador automatizado para geração de video ads (comerciais) focados em conversão para e-commerce. 
O fluxo: O usuário envia a URL de um produto para o bot do Telegram. O sistema extrai as informações da loja contornando bloqueios anti-bot, processa os atributos técnicos via LLM, escreve um roteiro persuasivo (AIDA/PAS), aguarda **aprovação humana ou feedback iterativo** via Telegram, e por fim, utiliza modelos I2V (Image-to-Video) e `ffmpeg` para gerar e entregar um comercial MP4 finalizado diretamente no chat.

**O Agente Operacional:** Você é **Madara**, um Senior AI Engineer focado em acurácia, arquitetura robusta, idempotência e certeza antes da ação.

## 2. Arquitetura Atual
* **Gateway (Telegram Bot):** `services/gateway/telegram_bot.py`. Recebe comandos, URLs e lida com o ciclo interativo via botões (Inline Keyboard).
* **Orchestrator (Hermes):** `core/orchestrator.py`. Gerencia os estados do pipeline no banco Supabase (`Received` -> `Scraping` -> `Semantic` -> `Prompt Generation` -> `Awaiting Approval` -> `Video Generation` -> `Completed`).
* **Scraper:** `services/scraper/engine.py`. Baixa a página e extrai as URLs oficiais das imagens em alta resolução do produto.
* **Semantic Processor:** `services/semantic/processor.py`. Usa Gemini para formatar descrições e specs brutas em JSON estruturado.
* **Marketing Organizer:** `services/marketing/organizer.py`. Usa Claude 4 (OpenRouter) para redigir o roteiro. Possui regras altamente restritas de *Cinematic Prompting*.
* **Video Generator:** `services/video/generator.py`. Usa a API do Muapi.ai (`kling-v3.0-standard-image-to-video`). Possui lógica nativa de Bypass WAF (baixa e hospeda a imagem), pooling assíncrono e montagem de vídeos.

## 3. Estado Atual do Sistema (Fim da Sessão Atual)

A infraestrutura inteira foi validada e o gargalo visual da API de vídeo foi corrigido. Aqui está o que foi recentemente implantado no código e está em produção (Bot reiniciado no `.venv`):

1. **Loop Interativo de Feedback:** O usuário lê o roteiro gerado no chat. Clicando em "Ajustar Roteiro", ele manda uma mensagem textual de crítica. O `MarketingOrganizer.refine_script` reescreve as cenas mantendo o JSON rígido e salvando o log em `feedback_history` (no Supabase).
2. **I2V Anchoring & Anti-Morphing Agnóstico:** Problemas graves de distorção de produto (ex: teclado virando tijolo) foram resolvidos. O Claude foi *bloqueado* de descrever atributos físicos do produto (cor, material). O prompt de cena (`visual`) deve sempre dizer *"The product from the reference image"* aliado a keywords rígidas de física (*"rigid body motion, no morphing"*). Funciona para qualquer nicho de e-commerce.
3. **Duração Cravada (30s):** O Claude estava encurtando o vídeo por "preguiça". Foi imposta uma restrição absoluta de **EXATAMENTE 6 CENAS de 5 segundos** para forçar a IA a redigir o roteiro inteiro do comercial.
4. **Assembly (Junção) via FFmpeg:** O orquestrador envia a melhor foto extraída da loja e os 6 prompts para o Kling V3. O `VideoGenerator` aguarda, baixa os 6 recortes curtos, costura eles cronologicamente via `ffmpeg-python` (concat demuxer) num arquivo `.mp4` temporário. O bot faz upload desse vídeo completo no Telegram do usuário e descarta o temporário.

## 4. Próximos Passos (Para a Nova Sessão)
- **Ação Imediata Esperada:** O usuário irá mandar uma nova URL no Telegram para validar se o comercial gerado vem perfeitamente estruturado em 30 segundos e se o produto físico não sofre mais deformação (Morphing) graças ao I2V Anchoring.
- **Troubleshooting:** Se algo falhar na geração, audite os logs do bot ou cheque a tabela `marketing_scripts` no Supabase para validar se o LLM seguiu a regra das 6 cenas.
- **Feature Roadmap (Fase 4):** A próxima grande evolução do projeto é utilizar RAG sobre a coluna `feedback_history` para que o sistema *lembre* dos ajustes passados do usuário (ex: "sempre prefiro fundo escuro") e os aplique de forma *Zero-Shot* antes mesmo da geração do primeiro roteiro.

## 5. Axiomas Fundamentais do Madara (Nunca Quebre)
1. **Certeza antes da ação:** Se houver risco de impacto estrutural ou gasto de recursos (API/Créditos), consulte o usuário antes.
2. **Tratamento Fidedigno:** Código sempre testado, retornos formatados corretamente. Nunca deixe pontas soltas.
3. **Nivelamento:** Pare e explique o diagnóstico de forma brutalmente transparente, como foi feito com o erro de 5 segundos do Claude.