import os
import json
import logging
import httpx
from typing import Dict, Any

class DataExtractor:
    """
    Agente responsável por transformar dados brutos de scraping em informações técnicas estruturadas.
    Foco: Preço, Especificações, Descrição Técnica e Mídia.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-lite-001")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def extract(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa o conteúdo extraído e gera um JSON técnico estruturado.
        """
        self.logger.info("Iniciando extração de dados estruturados com Gemini...")
        
        prompt = f"""
        Analise o conteúdo de uma página de produto abaixo e extraia dados TÉCNICOS, FINANCEIROS e de MARKETING.

        REGRAS CRÍTICAS:
        1. PREÇO: Procure por símbolos (R$, $, USD) e valores. Extraia o preço à vista principal.
        2. ESPECIFICAÇÕES: Liste detalhes técnicos (dimensões, peso, hardware, material).
        3. IMAGENS: Retorne APENAS URLs que mostram o produto em si. Ignore logos, ícones, banners e backgrounds. Ordene da melhor para a pior (maior resolução e mais detalhada primeiro). Máximo 9 URLs.
        4. USP: Identifique o diferencial único do produto (o que nenhum concorrente tem ou o principal benefício).
        5. DOR PRIMÁRIA: A dor ou problema que este produto resolve.
        6. PÚBLICO: Quem é o comprador típico (idade, gênero, estilo de vida, nicho).
        7. TOM: Defina o tom ideal da campanha para este produto e categoria (ex: "Aspiracional e elegante", "Urgente e agressivo", "Técnico e confiável", "Emocional e transformador").
        8. CATEGORIA: Uma das seguintes — Moda, Eletrônicos, Suplementos, Estética, Construção, Casa. Se não se encaixar, use a mais próxima.

        Retorne APENAS um JSON válido:
        {{
            "product_name": "Nome oficial",
            "price": {{
                "amount": 0.0,
                "currency": "Sigla",
                "full_text": "Ex: R$ 1.500,00"
            }},
            "technical_specs": {{
                "chave": "valor detalhado"
            }},
            "full_description": "Descrição técnica concisa",
            "usp": "Diferencial único do produto em 1 frase",
            "primary_pain": "Dor ou problema que o produto resolve em 1 frase",
            "target_audience": "Perfil do comprador ideal",
            "campaign_tone": "Tom ideal da campanha",
            "media": {{
                "images": ["URLs filtradas e ordenadas do produto, máx 9"],
                "videos": []
            }},
            "category": "Moda|Eletrônicos|Suplementos|Estética|Construção|Casa"
        }}

        CONTEÚDO:
        Título: {scraped_data.get('title')}
        Metadados: {scraped_data.get('meta_description')}
        Texto da Página: {scraped_data.get('all_text')}
        Lista de Imagens: {json.dumps(scraped_data.get('images', []))}
        """

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/projeto-itamar",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Você é um extrator de dados de alta precisão. Foque em preços e especificações técnicas."},
                {"role": "user", "content": prompt}
            ],
            "response_format": { "type": "json_object" }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.url, headers=headers, json=payload)
                if response.status_code != 200:
                    self.logger.error(f"OpenRouter Error {response.status_code}: {response.text}")
                response.raise_for_status()
                result = response.json()
                
                content = result['choices'][0]['message']['content']
                return json.loads(content)
                
        except Exception as e:
            self.logger.error(f"Erro na extração de dados: {str(e)}")
            return {
                "product_name": "Erro",
                "price": {"amount": 0.0, "currency": "N/A", "full_text": "N/A"},
                "technical_specs": {},
                "full_description": "Falha na extração",
                "media": {"images": [], "videos": []},
                "category": "N/A"
            }
