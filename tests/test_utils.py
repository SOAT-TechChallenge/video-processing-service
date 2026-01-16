import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import cv2
import numpy as np
from pathlib import Path
import tempfile
from app.utils import (
    extract_frames_from_video, 
    create_zip_from_images,
    generate_unique_id,
    cleanup_temp_files
)

# ========== Testes para Utils ==========

def test_extract_frames_from_video(temp_video_file):
    """Testa extração de frames de vídeo"""
    with tempfile.TemporaryDirectory() as temp_dir:
        frames = extract_frames_from_video(temp_video_file, temp_dir, frames_per_second=1)
        
        # Em Windows, pode ser 2 ou 3 frames dependendo do timing
        assert len(frames) >= 2  # 2 segundos de vídeo, 1 frame por segundo
        assert all(Path(f).exists() for f in frames)
        
        # Verifica que os frames são imagens válidas
        for frame_path in frames:
            img = cv2.imread(frame_path)
            assert img is not None
            assert img.shape == (480, 640, 3)

def test_extract_frames_empty_video():
    """Testa extração de frames de vídeo vazio/inválido"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Cria um arquivo vazio (não é vídeo)
        empty_file = Path(temp_dir) / "empty.mp4"
        empty_file.write_bytes(b"")
        
        frames = extract_frames_from_video(str(empty_file), temp_dir)
        assert len(frames) == 0

def test_create_zip_from_images(temp_video_file):
    """Testa criação de arquivo ZIP a partir de imagens"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Primeiro extrai frames
        frames = extract_frames_from_video(temp_video_file, temp_dir, frames_per_second=1)
        
        # Cria ZIP
        zip_path = Path(temp_dir) / "test.zip"
        result = create_zip_from_images(frames, str(zip_path))
        
        assert result == str(zip_path)
        assert zip_path.exists()
        assert zip_path.stat().st_size > 0
        
        # Verifica que o ZIP contém os arquivos
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zip_contents = zipf.namelist()
            assert len(zip_contents) == len(frames)
            for frame in frames:
                assert Path(frame).name in zip_contents

def test_generate_unique_id():
    """Testa geração de ID único"""
    id1 = generate_unique_id()
    id2 = generate_unique_id()
    
    assert id1 != id2
    assert len(id1) == 36  # Tamanho padrão de UUID
    # Verifica formato UUID
    parts = id1.split('-')
    assert len(parts) == 5
    assert len(parts[0]) == 8
    assert len(parts[1]) == 4
    assert len(parts[2]) == 4
    assert len(parts[3]) == 4
    assert len(parts[4]) == 12

def test_cleanup_temp_files():
    """Testa limpeza de arquivos temporários"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Cria arquivos e diretórios de teste
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content")
        
        test_dir = Path(temp_dir) / "test_dir"
        test_dir.mkdir()
        (test_dir / "nested.txt").write_text("nested content")
        
        # Verifica que existem antes da limpeza
        assert test_file.exists()
        assert test_dir.exists()
        
        # Limpa
        cleanup_temp_files(str(test_file), str(test_dir))
        
        # Verifica que foram removidos
        assert not test_file.exists()
        assert not test_dir.exists()

def test_cleanup_nonexistent_files():
    """Testa limpeza de arquivos que não existem"""
    # Não deve lançar exceção
    cleanup_temp_files("/path/that/does/not/exist")

# ========== Teste de Integração ==========

def test_full_processing_flow():
    """Teste de integração do fluxo completo"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Cria vídeo de teste usando a mesma lógica da fixture
        def create_test_video(file_path: str, duration_seconds: int = 3):
            """Cria um vídeo de teste com frames coloridos"""
            fps = 30
            width, height = 640, 480
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
            
            for i in range(fps * duration_seconds):
                # Cria frames com cores diferentes
                color = (i * 10) % 255
                frame = np.full((height, width, 3), color, dtype=np.uint8)
                # Adiciona algum padrão para ser único
                cv2.putText(frame, f'Frame {i}', (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                out.write(frame)
            
            out.release()
        
        # Cria vídeo de teste
        test_video = Path(temp_dir) / "test.mp4"
        create_test_video(str(test_video), duration_seconds=3)
        
        # Processa vídeo
        frames_dir = Path(temp_dir) / "frames"
        frames = extract_frames_from_video(str(test_video), str(frames_dir), frames_per_second=2)
        
        assert len(frames) >= 6  # 3 segundos * 2 fps = 6 frames
        
        # Cria ZIP
        zip_path = Path(temp_dir) / "output.zip"
        create_zip_from_images(frames, str(zip_path))
        
        assert zip_path.exists()
        
        # Verifica conteúdo do ZIP
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            assert len(zipf.namelist()) == len(frames)
            
        # Limpa
        cleanup_temp_files(str(test_video), str(frames_dir), str(zip_path))
        
        assert not test_video.exists()
        assert not frames_dir.exists()
        assert not zip_path.exists()