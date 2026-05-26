import os
import json
import logging
import httpx
from typing import Dict, Any

# Arcos narrativos por categoria de produto
CATEGORY_ARCS = {
    "Moda": [
        "HOOK: Mostre o produto em uso — a transformação que ele causa na pessoa",
        "CONTEXTO: Close no tecido/material/acabamento — qualidade que se vê",
        "DEMONSTRAÇÃO: Look completo em movimento — como caiu, como ficou",
        "BENEFÍCIO: Versatilidade — diferentes situações onde cabe",
        "PROVA SOCIAL: Reação / desejo / status que o produto gera",
        "CTA: Preço + urgência + link"
    ],
    "Eletrônicos": [
        "HOOK: O problema que todos têm e odeiam (sem o produto)",
        "CONTEXTO: Unboxing ou reveal do produto — first impression",
        "DEMONSTRAÇÃO: Interface/feature principal em uso real",
        "BENEFÍCIO: Velocidade/precisão/resultado que impressiona",
        "PROVA SOCIAL: Spec técnico mais impressionante em destaque",
        "CTA: Preço + diferencial competitivo + link"
    ],
    "Suplementos": [
        "HOOK: Dor/limitação que o público sente agora (sem o produto)",
        "CONTEXTO: Ingrediente ativo / fórmula — o que o torna diferente",
        "DEMONSTRAÇÃO: Produto em uso — textura, dose, praticidade",
        "BENEFÍCIO: Resultado esperado — performance, estética, saúde",
        "PROVA SOCIAL: Número de clientes / estudos / resultados reais",
        "CTA: Preço + escassez + link"
    ],
    "Estética": [
        "HOOK: Antes — a insatisfação que o público sente",
        "CONTEXTO: O produto em destaque — tecnologia ou ativo especial",
        "DEMONSTRAÇÃO: Aplicação / uso em tempo real",
        "BENEFÍCIO: Transformação visual — o resultado esperado",
        "PROVA SOCIAL: Antes/depois implícito ou depoimento",
        "CTA: Preço + garantia + link"
    ],
    "Construção": [
        "HOOK: O problema estrutural / a obra que dá dor de cabeça",
        "CONTEXTO: O produto como solução — resistência e praticidade",
        "DEMONSTRAÇÃO: Instalação ou aplicação rápida",
        "BENEFÍCIO: Resultado final — qualidade, durabilidade, economia",
        "PROVA SOCIAL: Especificação técnica que valida a escolha",
        "CTA: Preço por quantidade + link para orçamento"
    ],
    "Casa": [
        "HOOK: O caos / bagunça / problema doméstico que o público odeia",
        "CONTEXTO: O produto como solução elegante",
        "DEMONSTRAÇÃO: Facilidade de uso — funcionalidade em segundos",
        "BENEFÍCIO: Resultado — organização, limpeza, praticidade",
        "PROVA SOCIAL: Reação de quem usa — surpresa ou satisfação",
        "CTA: Preço + frete grátis/prazo + link"
    ]
}

CAMERA_BY_SCENE = """
| Cena | Função     | Shot Type            | Camera Movement         | Pacing   |
|------|------------|----------------------|-------------------------|----------|
| 1    | HOOK       | extreme close-up     | snap zoom in            | punchy   |
| 2    | CONTEXTO   | medium close-up      | slow dolly in           | building |
| 3    | DEMO       | macro / detail       | orbit around subject    | smooth   |
| 4    | BENEFÍCIO  | wide / hero shot     | crane up                | epic     |
| 5    | PROVA      | over-the-shoulder    | handheld subtle         | authentic|
| 6    | CTA        | front-facing hero    | push in fast            | urgent   |
"""

SYSTEM_PROMPT = """Você é um diretor criativo de UGC viral especializado em short-form video ads para TikTok e Instagram Reels no e-commerce brasileiro.

Você pensa como um editor de vídeo, não como um copywriter de blog. Cada cena é um take de 5 segundos — cada frame conta para prender a atenção.

Sua missão: transformar dados de produto em um comercial de 30s que para o scroll, cria desejo e converte.

Sua saída é sempre JSON estrito no schema fornecido. Nunca adicione texto fora do JSON."""

class MarketingOrganizer:
    """
    Agente responsável por transformar dados técnicos estruturados em roteiros publicitários virais.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = "anthropic/claude-sonnet-4"
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def _validate_script(self, script: Dict[str, Any]) -> Dict[str, Any]:
        """Garante restrições de tokens e imagem por cena. Corta no limite sem perguntar."""
        scenes = script.get("scenes", [])
        num_images = script.get("_num_images", 1)
        for scene in scenes:
            # audio ≤ 12 palavras
            audio = scene.get("audio", "")
            words = audio.split()
            if len(words) > 12:
                scene["audio"] = " ".join(words[:12])
            # text_overlay ≤ 4 palavras
            overlay = scene.get("text_overlay", "")
            words_ov = overlay.split()
            if len(words_ov) > 4:
                scene["text_overlay"] = " ".join(words_ov[:4])
            # image_index dentro do range disponível
            idx = scene.get("image_index", 1)
            scene["image_index"] = max(1, min(idx, max(num_images, 1)))
        return script

    async def generate_script(self, semantic_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera um roteiro de vídeo baseado nos dados semânticos do produto.
        """
        self.logger.info("Iniciando geração de roteiro de marketing...")

        category = semantic_data.get("category", "Casa")
        arc = CATEGORY_ARCS.get(category, CATEGORY_ARCS["Casa"])
        num_images = len(semantic_data.get("media", {}).get("images", [])) or 1

        arc_text = "\n".join(f"  CENA {i+1}: {desc}" for i, desc in enumerate(arc))

        prompt = f"""
PRODUTO: {semantic_data.get('product_name')}
CATEGORIA: {category}
PREÇO: {semantic_data.get('price', {}).get('full_text', 'N/A')}
USP: {semantic_data.get('usp', '')}
DOR PRIMÁRIA: {semantic_data.get('primary_pain', '')}
PÚBLICO: {semantic_data.get('target_audience', '')}
TOM: {semantic_data.get('campaign_tone', 'Aspiracional e dinâmico')}
SPECS: {json.dumps(semantic_data.get('technical_specs', {}), ensure_ascii=False)}
DESCRIÇÃO: {semantic_data.get('full_description', '')}
IMAGENS DISPONÍVEIS: {num_images} imagem(ns) de referência (referenciadas como @image1 até @image{num_images})

ARCO NARRATIVO PARA {category.upper()}:
{arc_text}

REGRAS DE CÂMERA POR CENA (siga exatamente):
{CAMERA_BY_SCENE}

REGRAS DO CAMPO 'visual':
- DEVE ser escrito em inglês.
- NUNCA descreva cor, material ou forma do produto — a imagem já carrega isso.
- Descreva apenas: ambiente, iluminação, movimento de câmera, clima emocional.
- Estrutura: [Shot Type], [Environment/Mood], [Lighting], [Camera Movement], [Pacing — 5 seconds], rigid body motion, subject locked, photorealistic, 9:16
- Cada slot máximo 6 palavras.

REGRAS DE ÁUDIO:
- Máximo 12 palavras por cena (equivale a ~5 segundos de locução).
- Tom direto, imperativo, sem enchimento. Corte tudo que não converte.

REGRAS DE TEXT_OVERLAY:
- Máximo 4 palavras. É o que aparece na tela em destaque.

REGRAS DE image_index:
- Escolha qual das {num_images} imagem(ns) disponíveis âncora cada cena (inteiro de 1 a {num_images}).
- Varie as imagens entre cenas para criar diversidade visual. Se houver apenas 1 imagem, use 1 em todas.

Retorne um JSON com EXATAMENTE este schema:
{{
    "analysis": {{
        "usp": "diferencial único em 1 frase",
        "primary_pain": "dor resolvida em 1 frase",
        "emotional_arc": "ex: curiosidade → desejo → urgência",
        "hook_angle": "abordagem do hook: dor, transformação, número ou surpresa"
    }},
    "headline": "Título chamativo em português (máx 8 palavras)",
    "scenes": [
        {{
            "time": "0-5s",
            "audio": "Locução em português (máx 12 palavras)",
            "visual": "English cinematic prompt (shot, env, light, camera, pacing, rigid body motion, subject locked, 9:16)",
            "text_overlay": "Texto tela PT (máx 4 palavras)",
            "image_index": 1
        }}
    ],
    "marketing_hooks": ["Hook alternativo 1", "Hook alternativo 2"],
    "target_audience": "Perfil do comprador ideal"
}}

EXATAMENTE 6 cenas. Não crie mais, não crie menos.
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/projeto-itamar",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

                content = result['choices'][0]['message']['content']
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                try:
                    script = json.loads(content)
                    script["_num_images"] = num_images
                    return self._validate_script(script)
                except json.JSONDecodeError as je:
                    self.logger.error(f"Erro ao decodificar JSON: {content[:200]}")
                    raise je

        except Exception as e:
            self.logger.error(f"Erro na geração do roteiro: {str(e)}")
            if 'response' in locals():
                self.logger.error(f"Resposta bruta: {response.text[:500]}")
            return {
                "headline": "Erro ao gerar roteiro",
                "scenes": [],
                "marketing_hooks": [],
                "target_audience": "N/A",
                "analysis": {}
            }

    async def refine_script(self, current_script: Dict[str, Any], feedback_text: str) -> Dict[str, Any]:
        """
        Refina um roteiro existente com base no feedback do usuário.
        """
        self.logger.info(f"Refinando roteiro com feedback: {feedback_text}")

        num_images = current_script.get("_num_images", 1)

        prompt = f"""
ROTEIRO ATUAL:
{json.dumps(current_script, indent=2, ensure_ascii=False)}

FEEDBACK DO USUÁRIO:
"{feedback_text}"

TAREFA:
1. Aplique EXCLUSIVAMENTE o ajuste solicitado. Não mude o que não foi pedido.
2. Mantenha EXATAMENTE 6 cenas com a mesma estrutura JSON.
3. REGRAS do campo 'visual': inglês, sem descrever cor/forma/material do produto, descrever apenas ambiente/luz/câmera/clima, estrutura: [Shot Type], [Env/Mood], [Lighting], [Camera], [Pacing 5s], rigid body motion, subject locked, 9:16.
4. REGRAS de áudio: máx 12 palavras. text_overlay: máx 4 palavras.
5. image_index: inteiro de 1 a {num_images}.

Retorne APENAS o JSON atualizado com a mesma estrutura.
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/projeto-itamar",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Você é um diretor criativo de UGC viral. Aplica ajustes cirúrgicos em roteiros de video ads. Retorne apenas JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(self.url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

                content = result['choices'][0]['message']['content']
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                refined = json.loads(content)
                refined["_num_images"] = num_images
                return self._validate_script(refined)
        except Exception as e:
            self.logger.error(f"Erro no refinamento do roteiro: {str(e)}")
            return current_script
