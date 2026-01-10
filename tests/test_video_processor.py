import pytest
import asyncio
from pathlib import Path
import tempfile
import cv2
import numpy as np
from app.video_processor import VideoProcessor
from app.utils import extract_frames_from_video, create_zip_from_images

def create_test_video(file_path: str, duration_seconds: int = 2):
    """Cria um vídeo de teste"""
    fps = 30
    width, height = 640, 480
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    
    for i in range(fps * duration_seconds):
        frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        out.write(frame)
    
    out.release()

@pytest.mark.asyncio
async def test_video_processing():
    """Testa o processamento de vídeo"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Criar vídeo de teste
        test_video = Path(temp_dir) / "test.mp4"
        create_test_video(str(test_video))
        
        # Testar extração de frames
        frames_dir = Path(temp_dir) / "frames"
        frames = extract_frames_from_video(str(test_video), str(frames_dir), fps=1)
        
        assert len(frames) > 0
        assert all(Path(f).exists() for f in frames)
        
        # Testar criação de ZIP
        zip_path = Path(temp_dir) / "test.zip"
        create_zip_from_images(frames, str(zip_path))
        
        assert zip_path.exists()
        assert zip_path.stat().st_size > 0

def test_generate_unique_id():
    """Testa geração de ID único"""
    from app.utils import generate_unique_id
    
    id1 = generate_unique_id()
    id2 = generate_unique_id()
    
    assert id1 != id2
    assert len(id1) == 36  # Tamanho de UUID