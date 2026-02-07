import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        # Configurações lidas do ambiente (definidas no ECS/Terraform)
        self.base_url = os.getenv("NOTIFICATION_SERVICE_URL")
        self.api_token = os.getenv("API_SECURITY_INTERNAL_TOKEN")
        
        # Validação de configuração
        if not self.base_url:
            logger.warning("⚠️ NOTIFICATION_SERVICE_URL não definida. Emails não serão enviados.")
        
        if not self.api_token:
            logger.error("❌ API_SECURITY_INTERNAL_TOKEN ausente. Falha de segurança crítica.")

    async def _send_notification(self, recipient_email: str, subject: str, content: str) -> bool:
        """
        Método interno genérico para chamar o microsserviço de notificação (Spring Boot)
        """
        if not self.base_url or not self.api_token:
            logger.warning(f"⚠️ Envio abortado para {recipient_email}: Configuração de notificação incompleta.")
            return False

        # Alinhado com a Controller Java: /api/notification/send-email
        url = f"{self.base_url.rstrip('/')}/api/notification/send-email"
        
        headers = {
            "Content-Type": "application/json",
            "x-apigateway-token": self.api_token
        }
        
        # Payload correspondente ao Record SendEmailRequestDTO do Java
        payload = {
            "to": recipient_email,
            "subject": subject,
            "body": content
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
            if response.status_code in [200, 201, 204]:
                logger.info(f"📧 Notificação enviada com sucesso para {recipient_email}")
                return True
            else:
                logger.error(f"❌ Falha no Notification Service: {response.status_code} - {response.text}")
                return False
                
        except httpx.RequestError as e:
            logger.error(f"❌ Erro de rede com Notification Service em {url}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao enviar email: {str(e)}")
            return False

    async def send_process_start(self, recipient_email: str, video_title: str):
        """
        🚀 NOVO: Notifica o usuário que o vídeo entrou na fila de processamento
        """
        subject = f"Processamento Iniciado: {video_title}"
        body = (
            f"Olá,\n\n"
            f"Recebemos o seu vídeo '{video_title}' e o processamento já começou!\n"
            f"Você receberá outro e-mail assim que os frames estiverem prontos para download.\n\n"
            f"Atenciosamente,\nVideo Processing Team"
        )
        return await self._send_notification(recipient_email, subject, body)

    async def send_process_completion(self, recipient_email: str, video_title: str, zip_filename: str):
        """Envia email de sucesso formatado"""
        subject = f"Processamento Concluído: {video_title}"
        body = (
            f"Olá,\n\n"
            f"Ótimas notícias! O vídeo '{video_title}' foi processado com sucesso.\n"
            f"O arquivo compactado '{zip_filename}' já está disponível no seu storage.\n\n"
            f"Atenciosamente,\nVideo Processing Team"
        )
        return await self._send_notification(recipient_email, subject, body)

    async def send_process_error(self, recipient_email: str, video_title: str, error_message: str):
        """Envia email de erro formatado"""
        subject = f"Falha no Processamento: {video_title}"
        body = (
            f"Olá,\n\n"
            f"Infelizmente ocorreu um erro ao extrair os frames do vídeo '{video_title}'.\n"
            f"Detalhes técnicos: {error_message}\n\n"
            f"Por favor, tente realizar o upload novamente.\n\n"
            f"Atenciosamente,\nVideo Processing Team"
        )
        return await self._send_notification(recipient_email, subject, body)