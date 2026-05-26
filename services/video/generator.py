import os
import logging
import asyncio
import random
import httpx
import tempfile
import ffmpeg
from typing import Dict, Any, List, Optional

class VideoGenerator:
    """
    Agente responsável pela geração de vídeos via Muapi.ai (SD 2 Omni Reference).
    Suporta até 9 imagens de referência por vídeo, referenciadas no prompt via @image1..@image9.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = os.getenv("MUAPI_KEY")
        self.base_url = "https://api.muapi.ai/api/v1"
        self.model = "sd-2-vip-omni-reference-1080p"
        self.aspect_ratio = "9:16"

    async def generate_from_script(
        self,
        script_data: Dict[str, Any],
        product_images: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Gera uma sequência de vídeos baseada nas cenas do roteiro.
        Faz upload de todas as imagens para o CDN Muapi antes de iniciar as gerações.
        """
        if not self.api_key:
            raise ValueError("MUAPI_KEY não configurada.")

        # Upload paralelo de todas as imagens para o CDN Muapi
        hosted_images: List[str] = []
        if product_images:
            images_to_upload = product_images[:9]
            self.logger.info(f"Fazendo upload de {len(images_to_upload)} imagem(ns) para o CDN Muapi...")
            upload_tasks = [self._upload_image(url, i + 1) for i, url in enumerate(images_to_upload)]
            hosted_images = list(await asyncio.gather(*upload_tasks))
            hosted_images = [u for u in hosted_images if u]  # remove falhas
            self.logger.info(f"{len(hosted_images)} imagem(ns) hospedada(s) com sucesso.")

        scenes = script_data.get("scenes", [])
        self.logger.info(f"Iniciando geração de {len(scenes)} cenas com {len(hosted_images)} referência(s).")

        tasks = [self.generate_scene(scene, i, hosted_images) for i, scene in enumerate(scenes)]
        return list(await asyncio.gather(*tasks))

    async def stitch_videos(self, video_urls: List[str], job_id: str) -> str:
        """
        Baixa as cenas e concatena em um único .mp4 via FFmpeg concat demuxer.
        Retorna o caminho local do arquivo final.
        """
        self.logger.info(f"Baixando e concatenando {len(video_urls)} cenas...")
        temp_dir = tempfile.mkdtemp()
        local_files = []

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                for i, url in enumerate(video_urls):
                    if not url:
                        continue
                    file_path = os.path.join(temp_dir, f"scene_{i:02d}.mp4")
                    res = await client.get(url)
                    res.raise_for_status()
                    with open(file_path, "wb") as f:
                        f.write(res.content)
                    local_files.append(file_path)

            if not local_files:
                raise Exception("Nenhuma cena foi baixada com sucesso.")

            list_file_path = os.path.join(temp_dir, "file_list.txt")
            with open(list_file_path, "w") as f:
                for path in local_files:
                    f.write(f"file '{path}'\n")

            output_path = f"/tmp/final_ad_{job_id}.mp4"
            self.logger.info(f"Executando FFmpeg → {output_path}")
            (
                ffmpeg
                .input(list_file_path, format="concat", safe=0)
                .output(output_path, c="copy")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            self.logger.info("Vídeo final concatenado.")
            return output_path

        except ffmpeg.Error as e:
            error_log = e.stderr.decode("utf8") if e.stderr else str(e)
            self.logger.error(f"Erro no FFmpeg: {error_log}")
            raise Exception(f"Falha ao concatenar: {error_log}")
        except Exception as e:
            self.logger.error(f"Erro na montagem: {str(e)}")
            raise
        finally:
            for path in local_files:
                if os.path.exists(path):
                    os.remove(path)
            list_fp = locals().get("list_file_path")
            if list_fp and os.path.exists(list_fp):
                os.remove(list_fp)
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass

    async def _upload_image(self, source_url: str, index: int) -> Optional[str]:
        """
        Baixa a imagem da origem e faz upload para o CDN Muapi (WAF bypass).
        """
        self.logger.info(f"Upload imagem {index}: {source_url[:80]}...")
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                res = await client.get(
                    source_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                res.raise_for_status()
                image_content = res.content

            upload_url = f"{self.base_url}/upload_file"
            headers = {"x-api-key": self.api_key}
            files = {"file": (f"ref_{index}.png", image_content, "image/png")}

            async with httpx.AsyncClient(timeout=60.0) as upload_client:
                upload_res = await upload_client.post(upload_url, headers=headers, files=files)
                upload_res.raise_for_status()
                cdn_url = upload_res.json().get("url")
                self.logger.info(f"Imagem {index} hospedada: {cdn_url}")
                return cdn_url

        except Exception as e:
            self.logger.error(f"Falha ao hospedar imagem {index}: {str(e)}")
            return None

    async def generate_scene(
        self,
        scene: Dict[str, Any],
        index: int,
        hosted_images: List[str]
    ) -> Dict[str, Any]:
        """
        Gera um clipe de 5s para uma cena com retry (3 tentativas, backoff exponencial).
        Constrói o prompt final injetando @imageN conforme image_index da cena.
        """
        image_index = scene.get("image_index", 1)
        visual = scene.get("visual", "").strip()

        # Prefixa @imageN no prompt se a imagem estiver disponível
        if hosted_images and 1 <= image_index <= len(hosted_images):
            prompt = f"@image{image_index} {visual}"
        else:
            prompt = visual

        self.logger.info(f"Cena {index} — image_index={image_index} — prompt: {prompt[:80]}...")

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": self.aspect_ratio,
            "duration": 5,
        }
        if hosted_images:
            payload["images_list"] = hosted_images

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.base_url}/{self.model}",
                        headers=headers,
                        json=payload
                    )
                    response.raise_for_status()
                    data = response.json()

                request_id = data.get("request_id") or data.get("id")
                if not request_id:
                    return {"index": index, "url": data.get("url"), "status": "completed"}

                video_url = await self._poll_result(request_id, headers)
                return {"index": index, "request_id": request_id, "url": video_url, "status": "completed"}

            except Exception as e:
                wait = (2 ** attempt) + random.uniform(0, 1)
                self.logger.warning(f"Cena {index} tentativa {attempt + 1} falhou: {e}. Retry em {wait:.1f}s...")
                if attempt < 2:
                    await asyncio.sleep(wait)
                else:
                    self.logger.error(f"Cena {index} falhou após 3 tentativas.")
                    return {"index": index, "status": "failed", "error": str(e)}

    async def _poll_result(self, request_id: str, headers: Dict[str, str]) -> str:
        """
        Polling adaptativo: 5s nos primeiros 60s, 10s depois. Cap total: 10 minutos.
        """
        poll_url = f"{self.base_url}/predictions/{request_id}/result"
        elapsed = 0

        while elapsed < 600:
            interval = 5 if elapsed < 60 else 10
            await asyncio.sleep(interval)
            elapsed += interval

            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    res = await client.get(poll_url, headers=headers)
                    if res.status_code != 200:
                        continue
                    data = res.json()
                except Exception:
                    continue

            status = data.get("status", "").lower()

            if status in ("completed", "succeeded", "success"):
                url = (
                    (data.get("outputs") or [None])[0]
                    or data.get("url")
                    or (data.get("output") or {}).get("url")
                )
                if url:
                    return url
                raise Exception(f"Status OK mas sem URL na resposta: {data}")

            if status in ("failed", "error"):
                raise Exception(f"Geração falhou: {data.get('error', 'sem detalhe')}")

        raise TimeoutError(f"Timeout de 10min para o request_id {request_id}")
