import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        # Configurações lidas do ambiente (definidas no Kubernetes)
        self.base_url = os.getenv("NOTIFICATION_SERVICE_URL")
        self.api_token = os.getenv("API_SECURITY_INTERNAL_TOKEN")
        
        # Validação de configuração
        if not self.base_url:
            logger.warning("⚠️ NOTIFICATION_SERVICE_URL não definida. Emails não serão enviados.")
        
        if not self.api_token:
            logger.error("❌ API_SECURITY_INTERNAL_TOKEN ausente. Falha de segurança crítica.")

    async def _send_notification(self, recipient_email: str, subject: str, content: str) -> bool:
        """
        Método interno genérico para chamar o microsserviço de notificação
        via HTTP POST com o token de segurança.
        """
        if not self.base_url or not self.api_token:
            logger.warning("⚠️ Tentativa de envio de email abortada: Configuração ausente.")
            return False

        # Garante que a URL não tenha barra duplicada e adiciona o endpoint
        url = f"{self.base_url.rstrip('/')}/notification/send-email"
        
        headers = {
            "Content-Type": "application/json",
            "x-apigateway-token": self.api_token  # Header obrigatório para o ALB/Gateway
        }
        
        payload = {
            "to": recipient_email,
            "subject": subject,
            "body": content
        }

        try:
            # httpx.AsyncClient é usado para não bloquear o loop de eventos do FastAPI
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
            if response.status_code == 200:
                logger.info(f"📧 Notificação enviada com sucesso para {recipient_email}")
                return True
            else:
                logger.error(f"❌ Falha no Notification Service: {response.status_code} - {response.text}")
                return False
                
        except httpx.RequestError as e:
            logger.error(f"❌ Erro de conexão com Notification Service: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao enviar email: {str(e)}")
            return False

    async def send_process_completion(self, recipient_email: str, video_title: str, zip_filename: str):
        """Envia email de sucesso formatado"""
        subject = f"Processamento Concluído: {video_title}"
        body = (
            f"Olá,\n\n"
            f"O vídeo '{video_title}' foi processado com sucesso!\n"
            f"O arquivo '{zip_filename}' já está disponível para download na plataforma.\n\n"
            f"Atenciosamente,\nVideo Processing Team"
        )
        return await self._send_notification(recipient_email, subject, body)

    async def send_process_error(self, recipient_email: str, video_title: str, error_message: str):
        """Envia email de erro formatado"""
        subject = f"Falha no Processamento: {video_title}"
        body = (
            f"Olá,\n\n"
            f"Infelizmente ocorreu um erro ao processar o vídeo '{video_title}'.\n"
            f"Detalhe do erro: {error_message}\n\n"
            f"Por favor, tente enviar o vídeo novamente.\n"
            f"Atenciosamente,\nVideo Processing Team"
        )
        return await self._send_notification(recipient_email, subject, body)