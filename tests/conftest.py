import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest.mock as mock

aioboto3_mock = mock.MagicMock()
aioboto3_mock.Session = mock.MagicMock()

sys.modules['aioboto3'] = aioboto3_mock
aiobotocore_mock = mock.MagicMock()
sys.modules['aiobotocore'] = aiobotocore_mock

import pytest
import time
from pathlib import Path
import tempfile
import cv2
import numpy as np
from datetime import datetime
import pytz
from unittest.mock import Mock, patch, AsyncMock

from app.s3_service import S3Service
from app.sqs_consumer import SQSConsumer
from app.video_processor import VideoProcessor

# ========== Fixtures Compartilhadas ==========

@pytest.fixture
def temp_video_file():
    """Cria um vídeo de teste temporário com cleanup seguro para Windows"""
    import tempfile
    from pathlib import Path
    
    # Cria diretório temporário
    temp_dir = tempfile.mkdtemp()
    file_path = Path(temp_dir) / "test_video.mp4"
    
    # Cria o vídeo de teste
    create_test_video(str(file_path), duration_seconds=2)
    
    yield str(file_path)
    
    # Cleanup seguro para Windows
    try:
        # Tenta várias vezes se o arquivo estiver em uso
        for _ in range(5):
            try:
                if file_path.exists():
                    file_path.unlink()
                break
            except PermissionError:
                time.sleep(0.1)
        
        # Remove o diretório
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass  # Ignora erros no cleanup

def create_test_video(file_path: str, duration_seconds: int = 2):
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

@pytest.fixture
def mock_s3_service():
    """Mock do S3Service corrigido"""
    with patch('app.s3_service.boto3.client') as mock_client:
        # Cria mock do cliente S3
        mock_s3_client = Mock()
        mock_client.return_value = mock_s3_client
        
        # Cria o service
        service = S3Service()
        service.s3_client = mock_s3_client
        
        # Configura os métodos mockados com valores padrão
        service.s3_client.download_file = Mock()
        service.s3_client.list_objects_v2 = Mock(return_value={'Contents': []})
        service.s3_client.head_object = Mock()
        
        # Mock dos métodos da classe
        service.video_exists = Mock(return_value=True)
        service.download_video = Mock()
        service.list_videos = Mock(return_value=[])
        service.get_video_info = Mock(return_value={})
        
        yield service

@pytest.fixture
def mock_sqs_consumer():
    """Mock do SQSConsumer"""
    with patch('app.sqs_consumer.boto3.client') as mock_client:
        consumer = SQSConsumer("https://sqs.test.queue")
        consumer.sqs_client = Mock()
        consumer.session = AsyncMock()
        yield consumer

@pytest.fixture
def video_processor(mock_s3_service):
    """VideoProcessor com mocks corrigidos"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service', return_value=mock_s3_service):
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            processor.s3_service = mock_s3_service
            yield processor