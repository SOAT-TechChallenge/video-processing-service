import os
import asyncio
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List
import aiofiles
from fastapi import UploadFile

from .utils import (
    extract_frames_from_video,
    create_zip_from_images,
    generate_unique_id,
    cleanup_temp_files
)
from .schemas import ProcessingStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, upload_dir: str = "uploads", output_dir: str = "outputs"):
        self.upload_dir = Path(upload_dir)
        self.output_dir = Path(output_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=5)
        logger.info(f"VideoProcessor inicializado. Upload dir: {upload_dir}, Output dir: {output_dir}")
    
    async def save_uploaded_file(self, file: UploadFile) -> str:
        """Salva o arquivo de vídeo enviado"""
        video_id = generate_unique_id()
        
        # Limpar nome do arquivo (remover espaços e caracteres especiais)
        original_filename = file.filename or "video"
        safe_filename = re.sub(r'[^\w\.-]', '_', original_filename)
        
        video_path = self.upload_dir / f"{video_id}_{safe_filename}"
        
        async with aiofiles.open(video_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        logger.info(f"Arquivo salvo: {video_path}")
        return str(video_path), video_id
    
    async def process_video(self, video_path: str, user_id: str) -> dict:
        """Processa um único vídeo: extrai frames e cria ZIP"""
        video_id = None
        try:
            logger.info(f"Iniciando processamento do vídeo: {video_path}")
            
            # Extrair video_id do nome do arquivo
            video_id = Path(video_path).stem.split('_')[0]
            
            # Criar diretório temporário
            temp_dir = self.output_dir / f"temp_{video_id}"
            temp_dir.mkdir(exist_ok=True)
            
            logger.info(f"Extraindo frames do vídeo: {video_path}")
            # Extrair frames do vídeo (1 frame por segundo)
            frame_paths = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                extract_frames_from_video,
                video_path,
                str(temp_dir),
                1  # 1 frame por segundo
            )
            
            logger.info(f"Frames extraídos: {len(frame_paths)}")
            
            if not frame_paths:
                raise ValueError("Não foi possível extrair frames do vídeo")
            
            # Criar arquivo ZIP (apenas nome do arquivo, não caminho completo)
            zip_filename = f"{video_id}_frames.zip"
            zip_path = self.output_dir / zip_filename
            
            logger.info(f"Criando arquivo ZIP: {zip_path}")
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                create_zip_from_images,
                frame_paths,
                str(zip_path)
            )
            
            # Limpar arquivos temporários
            cleanup_temp_files(video_path, str(temp_dir))
            
            logger.info(f"Processamento concluído para vídeo ID: {video_id}")
            
            # Retorna apenas o nome do arquivo ZIP, não o caminho completo
            return {
                "video_id": video_id,
                "status": ProcessingStatus.COMPLETED,
                "zip_path": zip_filename,  # Apenas nome do arquivo
                "frame_count": len(frame_paths),
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar vídeo {video_path}: {str(e)}")
            
            # Limpar em caso de erro
            if video_path and os.path.exists(video_path):
                cleanup_temp_files(video_path)
            
            return {
                "video_id": video_id or "unknown",
                "status": ProcessingStatus.FAILED,
                "zip_path": None,
                "frame_count": None,
                "error": str(e)
            }
    
    async def process_multiple_videos(self, files: List[UploadFile], user_id: str) -> dict:
        """Processa múltiplos vídeos simultaneamente"""
        logger.info(f"Iniciando processamento de {len(files)} vídeo(s) para usuário: {user_id}")
        
        tasks = []
        saved_files = []
        
        try:
            # Salvar todos os arquivos primeiro
            for file in files:
                logger.info(f"Salvando arquivo: {file.filename}")
                video_path, video_id = await self.save_uploaded_file(file)
                saved_files.append((video_path, video_id))
            
            # Processar todos os vídeos em paralelo
            for video_path, video_id in saved_files:
                task = self.process_video(video_path, user_id)
                tasks.append(task)
            
            # Aguardar todos os processamentos
            logger.info("Aguardando processamento dos vídeos...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Coletar resultados
            videos = []
            successful = 0
            failed = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Exceção no processamento do vídeo {i}: {str(result)}")
                    videos.append({
                        "video_id": f"error_{i}",
                        "status": ProcessingStatus.FAILED,
                        "zip_path": None,
                        "frame_count": None,
                        "error": str(result)
                    })
                    failed += 1
                else:
                    videos.append(result)
                    if result.get("status") == ProcessingStatus.COMPLETED:
                        successful += 1
                    else:
                        failed += 1
            
            logger.info(f"Processamento concluído: {successful} bem-sucedido(s), {failed} falha(s)")
            
            return {
                "batch_id": generate_unique_id(),
                "user_id": user_id,
                "total_videos": len(files),
                "videos": videos
            }
            
        except Exception as e:
            logger.error(f"Erro no processamento múltiplo: {str(e)}")
            
            # Limpar arquivos salvos em caso de erro geral
            for video_path, _ in saved_files:
                if os.path.exists(video_path):
                    cleanup_temp_files(video_path)
            
            # Retornar erro para todos os vídeos
            videos = []
            for i in range(len(files)):
                videos.append({
                    "video_id": f"error_{i}",
                    "status": ProcessingStatus.FAILED,
                    "zip_path": None,
                    "frame_count": None,
                    "error": f"Erro geral no processamento: {str(e)}"
                })
            
            return {
                "batch_id": generate_unique_id(),
                "user_id": user_id,
                "total_videos": len(files),
                "videos": videos
            }