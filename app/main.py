from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional
import os
import asyncio
import logging
from urllib.parse import unquote
from pathlib import Path

from .video_processor import VideoProcessor
from .s3_service import S3Service
from .config import S3_BUCKET_NAME, SQS_QUEUE_URL, print_config
from .schemas import BatchProcessingResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Video Processing Service",
    version="2.0.0",
)

# Inicializar serviços
processor = None
s3_service = None
consumer_task = None

@app.on_event("startup")
async def startup_event():
    """Inicializa serviços na startup"""
    global processor, s3_service, consumer_task
    
    try:
        # Mostrar configurações
        print_config()
        
        # Inicializar serviços
        s3_service = S3Service()
        processor = VideoProcessor()
        
        logger.info("✅ Serviços inicializados com sucesso")
        
        # Testar conexão com S3
        try:
            videos_count = len(s3_service.list_videos())
            logger.info(f"📊 Conexão S3 OK. {videos_count} vídeos disponíveis")
        except Exception as e:
            logger.warning(f"⚠️ Aviso ao conectar com S3: {e}")
            logger.info("💡 Configure credenciais AWS via AWS CLI ou IAM Role")
        
        # Iniciar consumidor SQS em background (se configurado)
        if SQS_QUEUE_URL:
            logger.info(f"📫 Iniciando consumidor SQS em background...")
            consumer_task = asyncio.create_task(processor.start_sqs_consumer())
        else:
            logger.info("ℹ️  Modo manual: Sem SQS configurada. Use endpoints manuais.")
            
    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Para serviços no shutdown"""
    if processor:
        processor.stop_sqs_consumer()
    logger.info("🛑 Serviços finalizados")

@app.get("/")
async def root():
    """Página inicial com informações do serviço"""
    return {
        "service": "Video Processing Service",
        "version": "2.0.0",
        "status": "running",
        "s3_bucket": S3_BUCKET_NAME,
        "sqs_queue": SQS_QUEUE_URL or "Not configured",
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
    """Health check endpoint"""
    status = "healthy" if processor and s3_service else "unhealthy"
    sqs_status = "running" if SQS_QUEUE_URL and consumer_task else "not_configured"
    
    return {
        "status": status,
        "service": "video-processor",
        "version": "2.0.0",
        "mode": "auto" if SQS_QUEUE_URL else "manual",
        "s3": {
            "bucket": S3_BUCKET_NAME,
            "connected": s3_service is not None
        },
        "sqs": {
            "queue": SQS_QUEUE_URL or "not_configured",
            "status": sqs_status
        },
        "processing": {
            "ready": processor is not None,
            "upload_dir": str(processor.upload_dir) if processor else None,
            "output_dir": str(processor.output_dir) if processor else None
        }
    }

@app.get("/s3/videos")
async def list_s3_videos(prefix: str = "videos/"):
    """Lista vídeos disponíveis no S3 (para testes manuais)"""
    try:
        if not s3_service:
            raise HTTPException(status_code=500, detail="S3 Service não inicializado")
        
        videos = s3_service.list_videos(prefix)
        
        return {
            "bucket": S3_BUCKET_NAME,
            "prefix": prefix,
            "count": len(videos),
            "videos": videos,
            "note": "Use POST /process/s3/{s3_key} para processar um vídeo"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar vídeos S3: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process/s3/{s3_key:path}")
async def process_s3_video(
    s3_key: str,
    background_tasks: BackgroundTasks,
    title: Optional[str] = "Unknown",
    description: Optional[str] = "",
    user_id: Optional[str] = "manual_user"
):
    """
    Processa um vídeo específico do S3
    
    Exemplo: POST /process/s3/videos/meu_video.mp4?title=Meu%20Video
    """
    try:
        if not processor:
            raise HTTPException(status_code=500, detail="Processor não inicializado")
        
        logger.info(f"🎬 Recebido pedido manual para processar: {s3_key}")
        
        # Processar em background para não bloquear a resposta
        async def process_async():
            result = await processor.process_video_from_s3(
                s3_key=s3_key,
                title=title,
                description=description,
                user_id=user_id,
                source="manual_api"
            )
            
            logger.info(f"📊 Resultado do processamento manual: {result.get('status')}")
            
            if result.get("status") == "completed":
                logger.info(f"✅ ZIP criado: {result.get('zip_filename')}")
            else:
                logger.error(f"❌ Falha: {result.get('error')}")
        
        # Adicionar à fila de tarefas em background
        background_tasks.add_task(process_async)
        
        return JSONResponse(
            content={
                "message": "Processamento iniciado em background",
                "s3_key": s3_key,
                "bucket": S3_BUCKET_NAME,
                "title": title,
                "status": "processing",
                "tracking": {
                    "check_status": f"GET /processed para ver arquivos processados",
                    "download": f"GET /download/{{filename}} quando pronto"
                }
            },
            status_code=202  # Accepted
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar processamento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/processed")
async def list_processed_files():
    """Lista todos os arquivos processados disponíveis"""
    try:
        if not processor:
            raise HTTPException(status_code=500, detail="Processor não inicializado")
        
        files = processor.get_processed_files()
        
        return {
            "count": len(files),
            "files": files,
            "note": "Use GET /download/{filename} para baixar"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar arquivos processados: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename:path}")
async def download_zip(filename: str):
    """Endpoint para download do arquivo ZIP processado"""
    try:
        # Decodificar URL
        filename = unquote(filename)
        
        # Extrair apenas o nome do arquivo
        filename = Path(filename).name
        
        # Construir caminho completo
        if not processor:
            raise HTTPException(status_code=500, detail="Processor não inicializado")
        
        file_path = processor.output_dir / filename
        
        if not file_path.exists():
            available_files = processor.get_processed_files()
            available_names = [f["filename"] for f in available_files]
            
            raise HTTPException(
                status_code=404, 
                detail={
                    "message": f"Arquivo não encontrado: {filename}",
                    "available_files": available_names
                }
            )
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/zip',
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-File-Size": str(file_path.stat().st_size)
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no download: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/processed-files")
async def processed_files_compat():
    """Endpoint de compatibilidade (seus testes existentes)"""
    return await list_processed_files()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)