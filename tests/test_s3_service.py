import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import pytz

from app.s3_service import S3Service
from app.config import S3_BUCKET_NAME, AWS_REGION

def test_s3_service_initialization():
    """Testa inicialização do S3Service com a região correta"""
    with patch('app.s3_service.boto3.client') as mock_client:
        service = S3Service()
        assert service.bucket_name == S3_BUCKET_NAME
        # Ajustado para validar a chamada com region_name
        mock_client.assert_called_once_with('s3', region_name=AWS_REGION)

def test_s3_service_download_video():
    """Testa download de vídeo do S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        
        local_path = "/tmp/test_video.mp4"
        s3_key = "videos/test.mp4"
        
        result = service.download_video(s3_key, local_path)
        
        assert result == local_path
        mock_s3.download_file.assert_called_once_with(
            S3_BUCKET_NAME, s3_key, local_path
        )

# --- 🚀 NOVO TESTE: UPLOAD VIDEO ---
def test_s3_service_upload_video():
    """Testa o novo método de upload de vídeo/zip para o S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        
        local_path = "/tmp/processed_frames.zip"
        s3_key = "processed/test_frames.zip"
        
        # Simula o upload
        service.upload_video(local_path, s3_key)
        
        # Verifica se o boto3 foi chamado com os argumentos certos e o ContentType correto
        mock_s3.upload_file.assert_called_once_with(
            Filename=local_path,
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            ExtraArgs={'ContentType': 'application/zip'}
        )

def test_s3_service_upload_video_error():
    """Testa erro no upload para o S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_s3.upload_file.side_effect = Exception("Upload Failed")
        mock_client.return_value = mock_s3
        service = S3Service()
        
        with pytest.raises(Exception, match="Upload Failed"):
            service.upload_video("/tmp/test.zip", "processed/test.zip")

# Os métodos abaixo permanecem iguais, mas garantimos que usem o mock_client atualizado
def test_s3_service_list_videos():
    """Testa listagem de vídeos do S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        
        mock_response = {
            'Contents': [
                {'Key': 'videos/video1.mp4', 'Size': 1024, 'LastModified': datetime(2024, 1, 1, tzinfo=pytz.UTC)},
                {'Key': 'videos/video2.mp4', 'Size': 2048, 'LastModified': datetime(2024, 1, 2, tzinfo=pytz.UTC)}
            ]
        }
        mock_s3.list_objects_v2.return_value = mock_response
        
        videos = service.list_videos("videos/")
        
        assert len(videos) == 2
        assert videos[0]['key'] == 'videos/video1.mp4'
        mock_s3.list_objects_v2.assert_called_once_with(
            Bucket=S3_BUCKET_NAME, Prefix="videos/"
        )

def test_s3_service_video_exists():
    """Testa verificação de existência de vídeo no S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        
        mock_s3.head_object.return_value = {}
        
        exists = service.video_exists("videos/test.mp4")
        
        assert exists is True
        mock_s3.head_object.assert_called_once_with(
            Bucket=S3_BUCKET_NAME, Key="videos/test.mp4"
        )