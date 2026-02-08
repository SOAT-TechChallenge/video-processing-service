from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
import logging
from urllib.parse import unquote
from pathlib import Path
import asyncio

from .video_processor import VideoProcessor
from .s3_service import S3Service
from .email_service import EmailService
from .config import S3_BUCKET_NAME, SQS_QUEUE_URL, print_config
from .schemas import ProcessingStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

services = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        print_config()
        
        s3_service = S3Service()
        email_service = EmailService()
        processor = VideoProcessor(email_service=email_service)
        
        services["s3"] = s3_service
        services["email"] = email_service
        services["processor"] = processor
        
        logger.info("✅ Serviços inicializados e dependências injetadas")
                   
        yield
        
    except Exception as e:
        logger.error(f"❌ Erro fatal na inicialização: {e}")
        raise e
    finally:
        if "processor" in services:
            services["processor"].stop_sqs_consumer()
        if "consumer_task" in services:
            services["consumer_task"].cancel()
        logger.info("🛑 Aplicação finalizada")

app = FastAPI(
    title="Video Processing Service",
    version="2.2.0",
    lifespan=lifespan
)

# --- Endpoints ---

@app.get("/")
async def root():
    return {
        "service": "Video Processing Service",
        "version": "2.2.0",
        "status": "running",
        "email_service": "configured" if services.get("email") else "error",
        "mode": "auto" if SQS_QUEUE_URL else "manual"
    }

@app.get("/health")
async def health_check():
    processor = services.get("processor")
    return {
        "status": "healthy" if processor else "unhealthy",
        "sqs_connected": SQS_QUEUE_URL is not None
    }

# 🚀 RESTAURADO: Listagem de vídeos no S3
@app.get("/s3/videos")
async def list_s3_videos(prefix: str = "videos/"):
    try:
        s3_svc = services.get("s3")
        if not s3_svc:
            raise HTTPException(500, "Serviço S3 indisponível")
            
        videos = s3_svc.list_videos(prefix)
        return {"count": len(videos), "videos": videos}
    except Exception as e:
        logger.error(f"❌ Erro ao listar S3: {e}")
        raise HTTPException(500, str(e))

@app.post("/process/s3/{s3_key:path}")
async def process_s3_video(
    s3_key: str,
    background_tasks: BackgroundTasks,
    title: Optional[str] = "Manual_Upload",
    description: Optional[str] = "",
    email: Optional[str] = None
):
    processor = services.get("processor")
    if not processor:
        raise HTTPException(500, "Processor indisponível")

    logger.info(f"🎬 Pedido manual recebido para: {s3_key} (Email: {email})")

    # A CORREÇÃO ESTÁ AQUI: mudar 'email' para 'userEmail'
    mock_sqs_message = {
        's3Key': s3_key,
        'title': title,
        'description': description,
        'userEmail': email
    }

    background_tasks.add_task(processor.process_message, mock_sqs_message)
    
    return JSONResponse(
        content={
            "message": "Processamento iniciado (Modo API Manual)", 
            "s3_key": s3_key,
            "info": f"Notificação será enviada para: {email}" if email else "Sem e-mail informado."
        },
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