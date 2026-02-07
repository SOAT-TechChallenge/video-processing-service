from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional
from contextlib import asynccontextmanager
import logging
from urllib.parse import unquote
from pathlib import Path
import asyncio

from .video_processor import VideoProcessor
from .s3_service import S3Service
from .email_service import EmailService
from .config import S3_BUCKET_NAME, SQS_QUEUE_URL, print_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dicionário global para manter as instâncias dos serviços
services = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerenciador de ciclo de vida da aplicação.
    Inicializa conexões e injeção de dependência antes da app começar.
    """
    try:
        print_config()
        
        # 1. Instanciar Serviços Base
        s3_service = S3Service()
        email_service = EmailService() # Agora é o cliente HTTP
        
        # 2. Instanciar Processador injetando o EmailService
        processor = VideoProcessor(email_service=email_service)
        
        # 3. Guardar no dicionário global de serviços
        services["s3"] = s3_service
        services["email"] = email_service
        services["processor"] = processor
        
        logger.info("✅ Serviços inicializados e dependências injetadas")
        
        # 4. Iniciar Consumidor SQS em Background (se configurado)
        if SQS_QUEUE_URL:
            logger.info(f"📫 Iniciando tarefa do consumidor SQS...")
            consumer_task = asyncio.create_task(processor.start_sqs_consumer())
            services["consumer_task"] = consumer_task
        else:
            logger.info("ℹ️ Modo manual: Sem SQS configurada.")
            
        yield # A aplicação roda aqui
        
    except Exception as e:
        logger.error(f"❌ Erro fatal na inicialização: {e}")
        raise e
        
    finally:
        # Shutdown: Parar consumidor e limpar recursos
        if "processor" in services:
            services["processor"].stop_sqs_consumer()
        
        # Aguardar tarefa cancelar se necessário
        if "consumer_task" in services:
            services["consumer_task"].cancel()
            
        logger.info("🛑 Aplicação finalizada")

app = FastAPI(
    title="Video Processing Service",
    version="2.2.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {
        "service": "Video Processing Service",
        "version": "2.2.0",
        "status": "running",
        "email_service": "configured" if services.get("email") else "error",
        "mode": "auto" if SQS_QUEUE_URL else "manual",
        "endpoints": {
            "POST /process/s3/{s3_key}": "Processa vídeo específico do S3",
            "GET /s3/videos": "Lista vídeos disponíveis no bucket",
            "GET /processed": "Lista vídeos já processados",
            "GET /download/{filename}": "Download do ZIP processado",
            "GET /health": "Status do serviço",
            "GET /": "Esta página"
        }
    }

@app.get("/health")
async def health_check():
    processor = services.get("processor")
    return {
        "status": "healthy" if processor else "unhealthy",
        "sqs_connected": SQS_QUEUE_URL is not None
    }

@app.get("/s3/videos")
async def list_s3_videos(prefix: str = "videos/"):
    try:
        s3_svc = services.get("s3")
        if not s3_svc:
            raise HTTPException(500, "Serviço S3 indisponível")
            
        videos = s3_svc.list_videos(prefix)
        return {"count": len(videos), "videos": videos}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/process/s3/{s3_key:path}")
async def process_s3_video(
    s3_key: str,
    background_tasks: BackgroundTasks,
    title: Optional[str] = "Unknown",
    description: Optional[str] = "",
    email: Optional[str] = None
):
    """Endpoint para testes manuais que também dispara emails"""
    processor = services.get("processor")
    email_svc = services.get("email")
    
    if not processor:
        raise HTTPException(500, "Processor indisponível")

    logger.info(f"🎬 Pedido manual recebido: {s3_key}")

    async def process_async():
        # Processa
        result = await processor.process_video_from_s3(
            s3_key=s3_key,
            title=title,
            description=description,
            source="manual_api"
        )
        
        # Notifica se tiver email
        if email and email_svc:
            if result.get("status") == "completed":
                await email_svc.send_process_completion(
                    email, title, result.get('zip_filename')
                )
            else:
                await email_svc.send_process_error(
                    email, title, result.get('error')
                )
    
    background_tasks.add_task(process_async)
    
    return JSONResponse(
        content={"message": "Processamento iniciado", "s3_key": s3_key},
        status_code=202
    )

@app.get("/processed")
async def list_processed_files():
    processor = services.get("processor")
    if not processor:
        raise HTTPException(500, "Processor indisponível")
    return {"files": processor.get_processed_files()}

@app.get("/download/{filename:path}")
async def download_zip(filename: str):
    processor = services.get("processor")
    if not processor:
        raise HTTPException(500, "Processor indisponível")
        
    filename = unquote(filename)
    filename = Path(filename).name
    file_path = processor.output_dir / filename
    
    if not file_path.exists():
        raise HTTPException(404, "Arquivo não encontrado")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/zip'
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)