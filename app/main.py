from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import List
import os
from .video_processor import VideoProcessor
from .schemas import BatchProcessingResponse
from urllib.parse import unquote

app = FastAPI(title="Video Processing Microservice", version="1.0.0")

processor = VideoProcessor()

@app.post("/upload", response_model=BatchProcessingResponse)
async def upload_videos(
    files: List[UploadFile] = File(...),
    user_id: str = "default_user"
):
    """Endpoint para upload e processamento de múltiplos vídeos"""
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado")
    
    # Validar tipos de arquivo
    for file in files:
        if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            raise HTTPException(
                status_code=400, 
                detail=f"Formato não suportado: {file.filename}"
            )
    
    # Processar vídeos
    result = await processor.process_multiple_videos(files, user_id)
    
    return result

@app.get("/download/{zip_path:path}")
async def download_zip(zip_path: str):
    """Endpoint para download do arquivo ZIP - aceita com ou sem 'outputs/'"""
    # Decodificar URL
    zip_path = unquote(zip_path)
    
    # Extrair apenas o nome do arquivo (última parte após /)
    filename = zip_path.split("/")[-1]
    
    # Construir caminho completo
    file_path = processor.output_dir / filename
    
    if not file_path.exists():
        # Listar arquivos disponíveis para debug
        available_files = list(processor.output_dir.glob("*.zip"))
        available_names = [f.name for f in available_files]
        
        raise HTTPException(
            status_code=404, 
            detail={
                "message": f"Arquivo não encontrado",
                "requested": filename,
                "available_files": available_names
            }
        )
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/zip'
    )

@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    return {
        "status": "healthy",
        "service": "video-processor",
        "upload_dir": str(processor.upload_dir),
        "output_dir": str(processor.output_dir)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)