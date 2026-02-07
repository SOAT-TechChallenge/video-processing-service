import asyncio
import json
import logging
import boto3
import os
from typing import Dict, Any, Optional
import aioboto3
from botocore.exceptions import ClientError
import os
os.environ.pop('AWS_ACCESS_KEY_ID', None)
os.environ.pop('AWS_SECRET_ACCESS_KEY', None)
os.environ.pop('AWS_SESSION_TOKEN', None)
logger = logging.getLogger(__name__)

class SQSConsumer:
    def __init__(self, queue_url: str, region_name: str = "us-east-1"):
        """
        Inicializa o consumidor SQS.
        Removidas as chaves manuais para permitir que o SDK use automaticamente 
        as IAM Roles do ECS (Task Role).
        """
        self.queue_url = queue_url
        self.region_name = region_name
        
        logger.info("🔑 Inicializando clientes AWS via IAM Role (Default Credentials Provider Chain)")
        
        # O boto3 busca automaticamente as credenciais na ordem:
        # 1. Variáveis de ambiente (se existirem)
        # 2. Metadados do ECS (Task Role)
        self.sqs_client = boto3.client(
            'sqs',
            region_name=self.region_name
        )
        
        # Configurar sessão aioboto3 para consumo assíncrono
        self.session = aioboto3.Session(region_name=self.region_name)
    
    async def consume_messages(self, max_messages: int = 10, wait_time: int = 20):
        """Consome mensagens da fila SQS"""
        try:
            # O aioboto3.Session sem chaves explícitas também usa a Task Role
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
                        
                        processed = await self.process_message(body)
                        
                        if processed:
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
                        logger.error(f"❌ Erro ao processar mensagem individual: {e}")
                
                return processed_messages
                
        except Exception as e:
            # Aqui é onde o erro de AccessDenied era capturado antes
            logger.error(f"❌ Erro ao consumir mensagens SQS: {e}")
            return []
    
    async def process_message(self, message: Dict[str, Any]) -> bool:
        """Processa uma mensagem individual - deve ser sobrescrito"""
        logger.info(f"📨 Mensagem recebida: {message}")
        return True