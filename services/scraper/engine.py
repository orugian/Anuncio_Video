import logging
from scrapling import StealthyFetcher
from typing import Dict, Any, List

class ScraperService:
    """
    Serviço especializado em extração de dados brutos utilizando StealthyFetcher (Chromium).
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def run(self, url: str) -> Dict[str, Any]:
        """
        Executa o scraping da URL usando um browser stealth real.
        """
        self.logger.info(f"Iniciando scraping stealth na URL: {url}")
        try:
            # StealthyFetcher é baseado em Chromium e passa na maioria dos testes anti-bot
            page = await StealthyFetcher.async_fetch(
                url, 
                headless=True,
                timeout=60000, # 60s para garantir carregamento em sites pesados
                network_idle=True # Espera o network ficar ocioso (garante renderização de JS)
            )
            
            # Extração aprimorada: capturando todo o texto para o Gemini encontrar preços/specs
            data = {
                "title": page.css("title")[0].text if page.css("title") else "N/A",
                "meta_description": page.css('meta[name="description"]::attr(content)')[0].text if page.css('meta[name="description"]') else "N/A",
                "h1": [h.text for h in page.css("h1")],
                "all_text": page.get_all_text()[:6000], 
                "raw_html_length": len(page.html_content)
            }
            
            # Coleta de imagens com filtro avançado de ruído
            all_images = [img.attrib.get("src") for img in page.css("img") if img.attrib.get("src")]
            exclude_list = [
                'logo', 'icon', 'avatar', 'pixel', 'sprite', 'banner', 'loading', 'svg', 
                'mercadolibre', 'mlstatic', 'facebook', 'instagram', 'twitter', 'youtube',
                'payment', 'frete', 'truck', 'shield', 'secure', 'card', 'visa', 'mastercard'
            ]
            
            filtered_images = []
            for img in all_images:
                img_lower = img.lower()
                if not any(ex in img_lower for ex in exclude_list):
                    if any(img_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        filtered_images.append(img)
            
            return {
                "raw_data": data,
                "images": filtered_images[:12]
            }
        except Exception as e:
            self.logger.error(f"Erro durante o scraping stealth: {str(e)}")
            raise e
