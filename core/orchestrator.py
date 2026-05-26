import logging
import uuid
import os
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from shared.database.client import db
from services.scraper.engine import ScraperService
from services.semantic.processor import DataExtractor
from services.marketing.organizer import MarketingOrganizer
from services.video.generator import VideoGenerator
from shared.models.schemas import JobStatus

class HermesOrchestrator:
    """
    Controlador central de fluxo do Ad Pipeline System.
    Responsável por coordenar os estágios e persistir o estado no Supabase.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scraper = ScraperService()
        self.extractor = DataExtractor()
        self.marketing = MarketingOrganizer()
        self.video = VideoGenerator()
        
        # Inicializa bot para notificações diretas
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.bot = Bot(token=token) if token else None

    async def start_pipeline(self, user_id: str, url: str):
        """
        Inicia o ciclo de vida de um novo job de anúncio.
        """
        job_id = None
        try:
            # 1. Registro do Job no Supabase (Status: Received)
            self.logger.info(f"Registrando novo job para usuário {user_id} - URL: {url}")
            job = db.insert_job(user_id, url)
            job_id = job['id']
            
            # 2. Estágio: Scraping
            db.update_job_status(job_id, JobStatus.SCRAPING)
            self.logger.info(f"[{job_id}] Iniciando estágio de Scraping...")
            
            scraped_data = await self.scraper.run(url)
            
            # 3. Salvar dados do Scraping
            db_raw_data = {
                "title": scraped_data['raw_data']['title'],
                "meta_description": scraped_data['raw_data']['meta_description'],
                "h1": scraped_data['raw_data']['h1'],
                "content_summary": scraped_data['raw_data']['all_text'][:500]
            }
            
            db.save_scraped_content(
                job_id=job_id,
                raw_json=db_raw_data,
                images=scraped_data['images']
            )
            
            # 4. Estágio: Data Extraction
            db.update_job_status(job_id, JobStatus.SEMANTIC_PROCESSING)
            self.logger.info(f"[{job_id}] Iniciando extração de dados estruturados...")
            
            product_data = await self.extractor.extract({
                **scraped_data['raw_data'],
                'images': scraped_data['images']
            })
            
            # 5. Salvar dados Estruturados
            db.save_semantic_context(job_id, product_data)

            # 6. Estágio: Marketing Script Generation
            db.update_job_status(job_id, JobStatus.PROMPT_GENERATION)
            self.logger.info(f"[{job_id}] Iniciando geração do roteiro de marketing...")
            
            marketing_script = await self.marketing.generate_script(product_data)

            # Embute a lista de imagens filtradas no script para uso na geração de vídeo
            filtered_images = product_data.get("media", {}).get("images", [])[:9]
            if not filtered_images:
                filtered_images = scraped_data.get("images", [])[:9]
            marketing_script["_images"] = filtered_images

            # 7. Salvar Roteiro e Pausar para Aprovação
            db.save_marketing_script(job_id, marketing_script)
            
            # Mudança de status para AWAITING_APPROVAL (novo estado planejado)
            db.update_job_status(job_id, "awaiting_approval")
            self.logger.info(f"[{job_id}] Pipeline pausado aguardando aprovação do usuário.")
            
            # Notificar via Telegram
            if self.bot:
                await self._notify_approval(user_id, job_id, marketing_script)
            
            return job_id

        except Exception as e:
            self.logger.error(f"Falha no pipeline para o job {job_id}: {str(e)}")
            if job_id:
                db.update_job_status(job_id, JobStatus.FAILED)
            raise e

    @staticmethod
    def _esc(text: str) -> str:
        """Escapa chars especiais do HTML para uso no Telegram (parse_mode=HTML)."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    async def _notify_approval(self, user_id: str, job_id: str, script: dict):
        """Envia o roteiro para o Telegram com botões de aprovação."""
        headline = self._esc(script.get('headline', ''))
        short_id = str(job_id)[:8]

        text = f"🎬 <b>Roteiro do seu comercial</b>\n\n"
        text += f"<b>{headline}</b>\n\n"

        for i, scene in enumerate(script.get('scenes', [])):
            audio = self._esc(scene.get('audio', ''))
            overlay = self._esc(scene.get('text_overlay', ''))
            line = f"<b>Cena {i+1}:</b> {audio}"
            if overlay:
                line += f" — <i>{overlay}</i>"
            text += line + "\n"

        text += f"\n<i>ID: {short_id}</i>\n\nO que deseja fazer?"

        keyboard = [
            [
                InlineKeyboardButton("✅ Aprovar e Gerar Vídeo", callback_data=f"appr_{job_id}"),
                InlineKeyboardButton("✏️ Ajustar Roteiro", callback_data=f"edit_{job_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except Exception as e:
            self.logger.error(f"Erro ao enviar notificação de aprovação: {e}")

    async def resume_for_video(self, job_id: str, user_id: str):
        """Retoma o pipeline para geração de vídeo após aprovação."""
        self.logger.info(f"[{job_id}] Roteiro aprovado. Iniciando geração de vídeo...")
        db.update_job_status(job_id, JobStatus.VIDEO_GENERATION)
        
        try:
            current_data = db.get_marketing_script(job_id)
            if not current_data:
                self.logger.error(f"Roteiro não encontrado para o job {job_id}")
                return

            if self.bot:
                await self.bot.send_message(
                    chat_id=user_id,
                    text="🎬 Gerando seu comercial agora. Tempo estimado: 5-10 min.\n\n⏳ Processando cenas..."
                )

            current_script = current_data['script_json']

            # Recupera imagens filtradas salvas no script (fallback: scraped bruto)
            product_images = current_script.get("_images", [])
            if not product_images:
                scraped_data = db.get_scraped_content(job_id)
                product_images = (scraped_data or {}).get("images", [])[:9]
            self.logger.info(f"[{job_id}] Usando {len(product_images)} imagem(ns) de referência.")

            # Chama o gerador passando a lista de imagens
            video_results = await self.video.generate_from_script(current_script, product_images=product_images)
            
            self.logger.info(f"[{job_id}] Geração de vídeo finalizada. Resultados: {video_results}")
            
            # Filtrar apenas as URLs com sucesso para a montagem
            successful_urls = [res.get('url') for res in video_results if res.get('status') == 'completed' and res.get('url')]
            
            if successful_urls:
                # Montar o vídeo final
                final_video_path = await self.video.stitch_videos(successful_urls, job_id)
                db.update_job_status(job_id, JobStatus.COMPLETED)

                if self.bot:
                    headline = self._esc(current_script.get('headline', ''))
                    caption = f"✅ <b>{headline}</b>\n\nSeu comercial está pronto!"
                    with open(final_video_path, 'rb') as video_file:
                        await self.bot.send_video(
                            chat_id=user_id,
                            video=video_file,
                            caption=caption,
                            parse_mode='HTML',
                            supports_streaming=True,
                            read_timeout=300,
                            write_timeout=300,
                            connect_timeout=60,
                        )

                    try:
                        os.remove(final_video_path)
                    except:
                        pass
            else:
                db.update_job_status(job_id, JobStatus.FAILED)
                if self.bot:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="❌ Não foi possível gerar as cenas do comercial. Tente novamente com outra URL ou entre em contato."
                    )

        except Exception as e:
            self.logger.error(f"Erro na geração de vídeo para o job {job_id}: {e}")
            # Não sobrescreve COMPLETED — o vídeo pode ter sido entregue mesmo com timeout de rede
            current_status = db.get_job_status(job_id)
            if current_status != JobStatus.COMPLETED:
                db.update_job_status(job_id, JobStatus.FAILED)
            if self.bot:
                await self.bot.send_message(
                    chat_id=user_id,
                    text="❌ Erro durante a geração do comercial. Tente novamente."
                )

    async def resume_with_feedback(self, job_id: str, feedback: str, user_id: str):
        """Refina o roteiro com base no feedback e solicita nova aprovação."""
        self.logger.info(f"[{job_id}] Feedback recebido: {feedback}. Refinando roteiro...")
        
        try:
            # 1. Recuperar o roteiro atual e histórico
            current_data = db.get_marketing_script(job_id)
            if not current_data:
                self.logger.error(f"Roteiro não encontrado para o job {job_id}")
                return

            current_script = current_data['script_json']
            history = current_data.get('feedback_history', [])
            
            # 2. Chamar Marketing.refine_script para gerar a nova versão
            refined_script = await self.marketing.refine_script(current_script, feedback)

            # Preserva metadados internos que Claude não devolve
            refined_script["_images"] = current_script.get("_images", [])

            # 3. Atualizar histórico e salvar no banco
            history.append(feedback)
            db.update_script_feedback(job_id, refined_script, history)
            
            # 4. Notificar usuário com a nova versão
            await self._notify_approval(user_id, job_id, refined_script)
            
        except Exception as e:
            self.logger.error(f"Erro ao processar feedback para o job {job_id}: {e}")
            if self.bot:
                await self.bot.send_message(chat_id=user_id, text="❌ Ocorreu um erro ao refinar seu roteiro. Tente novamente.")

# Instância única do orquestrador
hermes = HermesOrchestrator()
