import asyncio
import json
import logging
import boto3
import os
from typing import Dict, Any, Optional
import aioboto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class SQSConsumer:
    def __init__(self, queue_url: str, aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 aws_session_token: Optional[str] = None,
                 region_name: str = "us-east-1"):
        
        self.queue_url = queue_url
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_session_token = aws_session_token or os.getenv("AWS_SESSION_TOKEN")
        self.region_name = region_name
        
        # Configurar cliente SQS com session token se existir
        if self.aws_session_token:
            logger.info("🔑 Usando credenciais AWS com Session Token")
            self.sqs_client = boto3.client(
                'sqs',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_session_token=self.aws_session_token,
                region_name=self.region_name
            )
        else:
            logger.info("🔑 Usando credenciais AWS permanentes")
            self.sqs_client = boto3.client(
                'sqs',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name
            )
        
        # Configurar sessão aioboto3
        session_kwargs = {
            'aws_access_key_id': self.aws_access_key_id,
            'aws_secret_access_key': self.aws_secret_access_key,
            'region_name': self.region_name
        }
        
        if self.aws_session_token:
            session_kwargs['aws_session_token'] = self.aws_session_token
        
        self.session = aioboto3.Session(**session_kwargs)
    
    async def consume_messages(self, max_messages: int = 10, wait_time: int = 20):
        """Consome mensagens da fila SQS"""
        try:
            async with self.session.client('sqs') as sqs:
                response = await sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=max_messages,
                    WaitTimeSeconds=wait_time,
                    MessageAttributeNames=['All']
                )
                
                messages = response.get('Messages', [])
                if messages:
                    logger.info(f"📩 Recebidas {len(messages)} mensagens da fila")
                else:
                    logger.debug("📭 Nenhuma mensagem na fila")
                
                processed_messages = []
                for message in messages:
                    try:
                        body = json.loads(message['Body'])
                        receipt_handle = message['ReceiptHandle']
                        
                        logger.info(f"🔍 Processando mensagem: {body.get('s3Key', 'unknown')}")
                        
                        # Processar a mensagem
                        processed = await self.process_message(body)
                        
                        if processed:
                            # Deletar mensagem da fila
                            await sqs.delete_message(
                                QueueUrl=self.queue_url,
                                ReceiptHandle=receipt_handle
                            )
                            logger.info(f"✅ Mensagem processada e deletada: {body.get('s3Key')}")
                        else:
                            logger.warning(f"⚠️ Mensagem não processada: {body.get('s3Key')}")
                        
                        processed_messages.append({
                            'message': body,
                            'processed': processed
                        })
                        
                    except Exception as e:
                        logger.error(f"❌ Erro ao processar mensagem: {e}")
                        # Não deletar mensagem em caso de erro
                
                return processed_messages
                
        except Exception as e:
            logger.error(f"❌ Erro ao consumir mensagens SQS: {e}")
            return []
    
    async def process_message(self, message: Dict[str, Any]) -> bool:
        """Processa uma mensagem individual - deve ser sobrescrito"""
        logger.info(f"📨 Mensagem recebida: {message}")
        return True