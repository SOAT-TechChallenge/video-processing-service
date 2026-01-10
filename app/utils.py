import os
import zipfile
from pathlib import Path
import cv2
import uuid
from typing import List

def extract_frames_from_video(video_path: str, output_dir: str, frames_per_second: int = 1) -> List[str]:
    """
    Extrai frames de um vídeo e salva como imagens
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    video = cv2.VideoCapture(video_path)
    fps = video.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps / frames_per_second)
    
    frame_count = 0
    saved_frames = []
    
    while True:
        success, frame = video.read()
        if not success:
            break
            
        if frame_count % frame_interval == 0:
            frame_filename = f"frame_{frame_count:06d}.jpg"
            frame_path = os.path.join(output_dir, frame_filename)
            cv2.imwrite(frame_path, frame)
            saved_frames.append(frame_path)
        
        frame_count += 1
    
    video.release()
    return saved_frames

def create_zip_from_images(image_paths: List[str], zip_path: str) -> str:
    """
    Cria um arquivo ZIP contendo as imagens
    """
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for image_path in image_paths:
            zipf.write(image_path, os.path.basename(image_path))
    
    return zip_path

def generate_unique_id() -> str:
    """Gera um ID único para processamento"""
    return str(uuid.uuid4())

def cleanup_temp_files(*paths):
    """Remove arquivos temporários"""
    for path in paths:
        if os.path.exists(path):
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)