import os
import requests
import asyncio
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any
import aiofiles
import time

from .s3_service import S3Service
from .sqs_consumer import SQSConsumer
from .utils import (
    extract_frames_from_video,
    create_zip_from_images,
    generate_unique_id,
    cleanup_temp_files
)
from .schemas import ProcessingStatus
from .config import S3_BUCKET_NAME, UPLOAD_DIR, OUTPUT_DIR, SQS_QUEUE_URL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações do Notification Service (Lidas do Environment do Kubernetes)
NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL')
API_TOKEN = os.getenv('API_SECURITY_INTERNAL_TOKEN')

if not NOTIFICATION_SERVICE_URL:
    logger.warning("⚠️ NOTIFICATION_SERVICE_URL não definida! Notificações não funcionarão.")

if not API_TOKEN:
    logger.error("❌ API_SECURITY_INTERNAL_TOKEN não definido! Falha de segurança crítica.")

class VideoProcessor(SQSConsumer):
    def __init__(self, upload_dir: str = UPLOAD_DIR, output_dir: str = OUTPUT_DIR):
        
        # Configurar SQS (se houver URL configurada)
        sqs_queue_url = SQS_QUEUE_URL
        if sqs_queue_url:
            super().__init__(sqs_queue_url)
        else:
            # Inicializar sem SQS se não configurado
            self.queue_url = None
            logger.warning("⚠️ SQS_QUEUE_URL não configurada - Consumidor SQS desativado")
        
        # Configurar S3
        self.s3_bucket = S3_BUCKET_NAME
        self.s3_service = S3Service()
        
        # Configurar diretórios
        self.upload_dir = Path(upload_dir)
        self.output_dir = Path(output_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.is_consuming = False
        
        logger.info(f"🎬 VideoProcessor inicializado")
        logger.info(f"📦 S3 Bucket: {self.s3_bucket}")
        if sqs_queue_url:
            logger.info(f"📫 SQS Queue: {sqs_queue_url}")
        logger.info(f"📁 Upload dir: {upload_dir}, Output dir: {output_dir}")
        logger.info(f"🔔 Notification URL: {NOTIFICATION_SERVICE_URL}")

    def _send_error_email(self, email: str, title: str, error_message: str):
        """Envia notificação de erro via HTTP para o Notification Service"""
        if not email or not NOTIFICATION_SERVICE_URL:
            logger.warning("⚠️ Não foi possível enviar notificação (Email ou URL ausente)")
            return

        try:
            # Rota ajustada conforme solicitado
            url = f"{NOTIFICATION_SERVICE_URL}/api/notification/send-email"
            
            # Payload ajustado (usando 'body' conforme solicitado)
            payload = {
                "to": email,
                "subject": f"Falha no processamento do vídeo: {title}",
                "body": f"Olá, infelizmente ocorreu um erro ao processar seu vídeo.\nErro: {error_message}"
            }

            headers = {
                "Content-Type": "application/json",
                "x-apigateway-token": API_TOKEN # Token para passar pelo ALB
            }

            logger.info(f"📧 Enviando notificação de erro para: {email}")
            # Timeout curto (5s) para não travar o processamento se o notification cair
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            
            if response.status_code == 200:
                logger.info("✅ Notificação enviada com sucesso!")
            else:
                logger.error(f"❌ Falha ao enviar notificação: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"❌ Erro crítico ao chamar Notification Service: {e}")

    async def process_message(self, message: Dict[str, Any]) -> bool:
        """Processa uma mensagem da fila SQS"""
        try:
            s3_key = message.get('s3Key')
            s3_url = message.get('s3Url')
            title = message.get('title', 'Untitled')
            description = message.get('description', '')
            uploaded_at = message.get('uploadedAt')
            email = message.get('email') # <--- Pega o email da mensagem
            
            if not s3_key:
                logger.error("❌ Mensagem sem s3Key")
                return False
            
            logger.info(f"📩 Nova mensagem SQS recebida:")
            logger.info(f"   📂 Arquivo: {s3_key}")
            logger.info(f"   📝 Título: {title}")
            logger.info(f"   👤 Email: {email}")
            logger.info(f"   🕐 Uploaded at: {uploaded_at}")
            
            # Processar vídeo do S3
            result = await self.process_video_from_s3(
                s3_key=s3_key,
                title=title,
                description=description,
                source="sqs"
            )
            
            if result.get("status") == ProcessingStatus.COMPLETED:
                logger.info(f"✅ Processamento via SQS concluído: {result.get('video_id')}")
                return True
            else:
                # Lógica de Falha: Loga o erro e tenta notificar o usuário
                error_msg = result.get('error', 'Erro desconhecido')
                logger.error(f"❌ Falha no processamento via SQS: {error_msg}")
                
                if email:
                    logger.info("🚀 Iniciando envio de notificação de erro...")
                    # Executa o requests (síncrono) em uma thread separada para não bloquear o loop async
                    await asyncio.get_event_loop().run_in_executor(
                        self.executor, 
                        self._send_error_email, 
                        email, 
                        title, 
                        error_msg
                    )
                else:
                    logger.warning("⚠️ Email não encontrado na mensagem, notificação pulada.")

                return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem SQS: {e}")
            return False
    
    async def process_video_from_s3(self, s3_key: str, title: str = "Unknown", 
                                    description: str = "", user_id: str = "system",
                                    source: str = "manual") -> dict:
        """Processa um vídeo específico do S3 (para testes manuais ou SQS)"""
        try:
            logger.info(f"🚀 Iniciando processamento do vídeo do S3")
            logger.info(f"   📂 Arquivo: {s3_key}")
            logger.info(f"   📝 Título: {title}")
            logger.info(f"   📦 Bucket: {self.s3_bucket}")
            logger.info(f"   📡 Fonte: {source}")
            
            # Verificar se o vídeo existe no S3
            if not self.s3_service.video_exists(s3_key):
                logger.error(f"❌ Vídeo não encontrado no S3: {s3_key}")
                return {
                    "video_id": "not_found",
                    "status": ProcessingStatus.FAILED,
                    "error": f"Vídeo não encontrado no S3: {s3_key}",
                    "s3_key": s3_key
                }
            
            # Baixar vídeo do S3
            video_filename = f"{generate_unique_id()}_{Path(s3_key).name}"
            video_path = self.upload_dir / video_filename
            
            logger.info(f"⬇️ Baixando vídeo do S3...")
            self.s3_service.download_video(
                s3_key=s3_key,
                local_path=str(video_path)
            )
            
            logger.info(f"✅ Vídeo baixado: {video_path.name}")
            
            # Processar vídeo
            result = await self._process_video_internal(
                video_path=str(video_path),
                user_id=user_id,
                video_metadata={
                    's3_key': s3_key,
                    'title': title,
                    'description': description,
                    'bucket': self.s3_bucket,
                    'source': source,
                    'original_filename': Path(s3_key).name
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar vídeo do S3: {e}")
            return {
                "video_id": "error",
                "status": ProcessingStatus.FAILED,
                "error": str(e),
                "s3_key": s3_key
            }
    
    async def _process_video_internal(self, video_path: str, user_id: str, 
                                     video_metadata: Dict = None) -> dict:
        """Processa um vídeo baixado do S3"""
        video_id = None
        try:
            logger.info(f"🔄 Processando vídeo local: {Path(video_path).name}")
            
            # Extrair video_id do nome do arquivo
            video_id = Path(video_path).stem.split('_')[0]
            
            # Criar diretório temporário
            temp_dir = self.output_dir / f"temp_{video_id}"
            temp_dir.mkdir(exist_ok=True)
            
            logger.info(f"🎞️ Extraindo frames do vídeo...")
            # Extrair frames do vídeo
            frame_paths = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                extract_frames_from_video,
                video_path,
                str(temp_dir),
                1  # 1 frame por segundo
            )
            
            logger.info(f"📊 Frames extraídos: {len(frame_paths)}")
            
            if not frame_paths:
                raise ValueError("Não foi possível extrair frames do vídeo")
            
            # Adicionar metadados ao nome do ZIP
            title_safe = re.sub(r'[^\w\.-]', '_', video_metadata.get('title', 'video'))
            zip_filename = f"{video_id}_{title_safe}_frames.zip"
            zip_path = self.output_dir / zip_filename
            
            logger.info(f"📦 Criando arquivo ZIP: {zip_path.name}")
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                create_zip_from_images,
                frame_paths,
                str(zip_path)
            )
            
            # Limpar arquivos temporários
            cleanup_temp_files(video_path, str(temp_dir))
            
            logger.info(f"✅ Processamento concluído!")
            
            return {
                "video_id": video_id,
                "status": ProcessingStatus.COMPLETED,
                "zip_filename": zip_filename,
                "zip_path": str(zip_path),
                "zip_url": f"/download/{zip_filename}",
                "frame_count": len(frame_paths),
                "error": None,
                "metadata": video_metadata,
                "processing_time": time.time()
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar vídeo: {str(e)}")
            
            # Limpar em caso de erro
            if video_path and os.path.exists(video_path):
                cleanup_temp_files(video_path)
            
            return {
                "video_id": video_id or "unknown",
                "status": ProcessingStatus.FAILED,
                "zip_filename": None,
                "zip_path": None,
                "frame_count": None,
                "error": str(e),
                "metadata": video_metadata
            }
    
    def list_available_videos(self, prefix: str = "videos/") -> List[Dict]:
        """Lista vídeos disponíveis no S3"""
        try:
            return self.s3_service.list_videos(prefix)
        except Exception as e:
            logger.error(f"❌ Erro ao listar vídeos do S3: {e}")
            return []
    
    def get_processed_files(self) -> List[Dict]:
        """Lista todos os arquivos ZIP processados"""
        try:
            zip_files = list(self.output_dir.glob("*.zip"))
            
            files = []
            for zip_file in zip_files:
                files.append({
                    "filename": zip_file.name,
                    "size": zip_file.stat().st_size,
                    "created_at": zip_file.stat().st_ctime,
                    "path": str(zip_file),
                    "url": f"/download/{zip_file.name}"
                })
            
            return files
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar arquivos processados: {e}")
            return []
    
    async def start_sqs_consumer(self):
        """Inicia o consumo contínuo da fila SQS (se configurado)"""
        if not self.queue_url:
            logger.warning("⚠️ Consumidor SQS não iniciado (queue_url não configurada)")
            return
        
        self.is_consuming = True
        logger.info(f"📫 Iniciando consumidor SQS...")
        
        while self.is_consuming:
            try:
                await self.consume_messages()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ Erro no consumidor SQS: {e}")
                await asyncio.sleep(30)
    
    def stop_sqs_consumer(self):
        """Para o consumo da fila SQS"""
        self.is_consuming = False
        logger.info("🛑 Consumidor SQS parado")