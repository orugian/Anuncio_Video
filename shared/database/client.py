import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

class SupabaseClient:
    """
    Cliente centralizado para operações no Supabase.
    Encapsula a conexão e fornece interface para as tabelas do pipeline.
    """
    def __init__(self):
        # Garante que as variáveis mais recentes do .env sejam carregadas
        load_dotenv(override=True)
        url: str = os.getenv("SUPABASE_URL")
        key: str = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL e SUPABASE_KEY devem estar configuradas no .env")
            
        self.client: Client = create_client(url, key)

    def insert_job(self, user_id: str, url: str) -> dict:
        """Cria um novo job no banco."""
        data = {
            "user_id": user_id,
            "url": url,
            "status": "received"
        }
        response = self.client.table("jobs").insert(data).execute()
        return response.data[0]

    def update_job_status(self, job_id: str, status: str):
        """Atualiza o status de um job."""
        self.client.table("jobs").update({"status": status}).eq("id", job_id).execute()

    def save_scraped_content(self, job_id: str, raw_json: dict, images: list):
        """Persiste os dados brutos do scraping."""
        data = {
            "job_id": job_id,
            "raw_json": raw_json,
            "images": images
        }
        self.client.table("scraped_content").insert(data).execute()

    def save_semantic_context(self, job_id: str, semantic_json: dict):
        """Persiste o contexto semântico processado pela IA."""
        data = {
            "job_id": job_id,
            "semantic_json": semantic_json
        }
        self.client.table("semantic_context").insert(data).execute()

    def save_marketing_script(self, job_id: str, script_json: dict):
        """Persiste o roteiro de marketing gerado."""
        data = {
            "job_id": job_id,
            "script_json": script_json,
            "feedback_history": []
        }
        self.client.table("marketing_scripts").upsert(data).execute()

    def get_scraped_content(self, job_id: str) -> dict:
        """Busca o conteúdo extraído de um job, incluindo as imagens."""
        response = self.client.table("scraped_content").select("*").eq("job_id", job_id).execute()
        return response.data[0] if response.data else None

    def get_marketing_script(self, job_id: str) -> dict:
        """Busca o roteiro e histórico de um job."""
        response = self.client.table("marketing_scripts").select("*").eq("job_id", job_id).execute()
        return response.data[0] if response.data else None

    def get_job_status(self, job_id: str) -> str:
        """Retorna o status atual de um job."""
        response = self.client.table("jobs").select("status").eq("id", job_id).execute()
        return response.data[0]["status"] if response.data else None

    def update_script_feedback(self, job_id: str, script_json: dict, feedback_history: list):
        """Atualiza o roteiro e o histórico de feedbacks."""
        data = {
            "script_json": script_json,
            "feedback_history": feedback_history
        }
        self.client.table("marketing_scripts").update(data).eq("job_id", job_id).execute()

# Instância singleton para uso no projeto
db = SupabaseClient()
