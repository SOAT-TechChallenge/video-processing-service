import os
import asyncio
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Optional
import time

from .s3_service import S3Service
from .sqs_consumer import SQSConsumer
from .email_service import EmailService
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

class VideoProcessor(SQSConsumer):
    def __init__(self, email_service: Optional[EmailService] = None, upload_dir: str = UPLOAD_DIR, output_dir: str = OUTPUT_DIR):
        
        # Configurar SQS
        sqs_queue_url = SQS_QUEUE_URL
        if sqs_queue_url:
            super().__init__(sqs_queue_url)
        else:
            self.queue_url = None
            logger.warning("⚠️ SQS_QUEUE_URL não configurada - Consumidor SQS desativado")
        
        self.email_service = email_service
        self.s3_bucket = S3_BUCKET_NAME
        self.s3_service = S3Service()
        
        self.upload_dir = Path(upload_dir)
        self.output_dir = Path(output_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.is_consuming = False
        
        logger.info(f"🎬 VideoProcessor inicializado")
        logger.info(f"📦 S3 Bucket: {self.s3_bucket}")

    async def process_message(self, message: Dict[str, Any]) -> bool:
        """Processa uma mensagem da fila SQS"""
        try:
            s3_key = message.get('s3Key')
            title = message.get('title', 'Untitled')
            description = message.get('description', '')
            email = message.get('email') # Extração do e-mail vindo do Java/Uploader
            
            if not s3_key:
                logger.error("❌ Mensagem sem s3Key")
                return False
            
            logger.info(f"📩 Processando mensagem SQS: {title} ({email})")
            
            result = await self.process_video_from_s3(
                s3_key=s3_key,
                title=title,
                description=description,
                source="sqs"
            )
            
            # === LÓGICA DE SUCESSO ===
            if result.get("status") == ProcessingStatus.COMPLETED:
                logger.info(f"✅ Processamento concluído: {result.get('video_id')}")
                
                if email and self.email_service:
                    # Dispara a notificação usando o e-mail extraído do payload SQS
                    asyncio.create_task(
                        self.email_service.send_process_completion(
                            recipient_email=email,
                            video_title=title,
                            zip_filename=result.get('zip_filename', 'arquivo.zip')
                        )
                    )
                return True
            
            # === LÓGICA DE FALHA ===
            else:
                error_msg = result.get('error', 'Erro desconhecido')
                logger.error(f"❌ Falha no processamento: {error_msg}")
                
                if email and self.email_service:
                    asyncio.create_task(
                        self.email_service.send_process_error(
                            recipient_email=email,
                            video_title=title,
                            error_message=error_msg
                        )
                    )
                return False
            
        except Exception as e:
            logger.error(f"❌ Erro crítico ao processar mensagem SQS: {e}")
            return False
    
    async def process_video_from_s3(self, s3_key: str, title: str = "Unknown", 
                                    description: str = "", user_id: str = "system",
                                    source: str = "manual") -> dict:
        """Processa um vídeo específico do S3"""
        try:
            logger.info(f"🚀 Iniciando processamento: {s3_key}")
            
            if not self.s3_service.video_exists(s3_key):
                return {
                    "video_id": "not_found",
                    "status": ProcessingStatus.FAILED,
                    "error": f"Vídeo não encontrado no S3: {s3_key}",
                    "s3_key": s3_key
                }
            
            # Download do vídeo usando Task Role (sem chaves manuais)
            video_filename = f"{generate_unique_id()}_{Path(s3_key).name}"
            video_path = self.upload_dir / video_filename
            
            logger.info(f"⬇️ Baixando vídeo do S3...")
            self.s3_service.download_video(s3_key=s3_key, local_path=str(video_path))
            
            result = await self._process_video_internal(
                video_path=str(video_path),
                user_id=user_id,
                video_metadata={
                    's3_key': s3_key,
                    'title': title,
                    'bucket': self.s3_bucket,
                    'source': source
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
        """Lógica interna de extração de frames e zip com UPLOAD para S3"""
        video_id = None
        try:
            video_id = Path(video_path).stem.split('_')[0]
            temp_dir = self.output_dir / f"temp_{video_id}"
            temp_dir.mkdir(exist_ok=True)
            
            # Extração de Frames
            frame_paths = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                extract_frames_from_video,
                video_path,
                str(temp_dir),
                1
            )
            
            if not frame_paths:
                raise ValueError("Não foi possível extrair frames do vídeo")
            
            # Criação do ZIP local
            title_safe = re.sub(r'[^\w\.-]', '_', video_metadata.get('title', 'video'))
            zip_filename = f"{video_id}_{title_safe}_frames.zip"
            zip_path = self.output_dir / zip_filename
            
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                create_zip_from_images,
                frame_paths,
                str(zip_path)
            )

            # --- 🚀 CORREÇÃO: UPLOAD PARA S3 ---
            # Envia o arquivo ZIP gerado para a pasta 'processed/' no bucket
            s3_output_key = f"processed/{zip_filename}"
            logger.info(f"📤 Fazendo upload para S3: {s3_output_key}")
            
            self.s3_service.upload_video(
                local_path=str(zip_path), 
                s3_key=s3_output_key
            )
            logger.info(f"✅ Upload concluído com sucesso!")
            
            cleanup_temp_files(video_path, str(temp_dir))
            
            return {
                "video_id": video_id,
                "status": ProcessingStatus.COMPLETED,
                "zip_filename": zip_filename,
                "s3_output_key": s3_output_key,
                "zip_url": f"/download/{zip_filename}",
                "error": None,
                "metadata": video_metadata,
                "processing_time": time.time()
            }
            
        except Exception as e:
            if video_path and os.path.exists(video_path):
                cleanup_temp_files(video_path)
            return {
                "video_id": video_id or "unknown",
                "status": ProcessingStatus.FAILED,
                "error": str(e),
                "metadata": video_metadata
            }

    async def start_sqs_consumer(self):
        if not self.queue_url:
            return
        self.is_consuming = True
        logger.info(f"📫 Consumidor SQS iniciado...")
        while self.is_consuming:
            try:
                await self.consume_messages()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ Erro no loop SQS: {e}")
                await asyncio.sleep(30)
    
    def stop_sqs_consumer(self):
        self.is_consuming = False
        logger.info("🛑 Consumidor SQS parado")

    def get_processed_files(self) -> List[Dict]:
            """Lista os arquivos ZIP processados localmente no output_dir"""
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