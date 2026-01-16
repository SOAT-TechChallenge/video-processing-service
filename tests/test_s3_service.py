import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import pytz

from app.s3_service import S3Service
from app.config import S3_BUCKET_NAME

def test_s3_service_initialization():
    """Testa inicialização do S3Service"""
    with patch('app.s3_service.boto3.client') as mock_client:
        service = S3Service()
        assert service.bucket_name == S3_BUCKET_NAME
        mock_client.assert_called_once_with('s3')

def test_s3_service_download_video():
    """Testa download de vídeo do S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        service.s3_client = mock_s3
        
        local_path = "/tmp/test_video.mp4"
        s3_key = "videos/test.mp4"
        
        result = service.download_video(s3_key, local_path)
        
        assert result == local_path
        mock_s3.download_file.assert_called_once_with(
            S3_BUCKET_NAME, s3_key, local_path
        )

def test_s3_service_download_video_error():
    """Testa erro no download de vídeo do S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_s3.download_file.side_effect = Exception("S3 Error")
        mock_client.return_value = mock_s3
        service = S3Service()
        service.s3_client = mock_s3
        
        with pytest.raises(Exception, match="S3 Error"):
            service.download_video("videos/test.mp4", "/tmp/test.mp4")

def test_s3_service_list_videos():
    """Testa listagem de vídeos do S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        service.s3_client = mock_s3
        
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
        assert videos[0]['size'] == 1024
        assert '2024-01-01' in videos[0]['last_modified']
        mock_s3.list_objects_v2.assert_called_once_with(
            Bucket=S3_BUCKET_NAME, Prefix="videos/"
        )

def test_s3_service_list_videos_empty():
    """Testa listagem de vídeos quando bucket está vazio"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        service.s3_client = mock_s3
        
        mock_s3.list_objects_v2.return_value = {}
        
        videos = service.list_videos()
        
        assert videos == []
        mock_s3.list_objects_v2.assert_called_once()

def test_s3_service_video_exists():
    """Testa verificação de existência de vídeo no S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        service.s3_client = mock_s3
        
        mock_s3.head_object.return_value = {}
        
        exists = service.video_exists("videos/test.mp4")
        
        assert exists is True
        mock_s3.head_object.assert_called_once_with(
            Bucket=S3_BUCKET_NAME, Key="videos/test.mp4"
        )

def test_s3_service_video_not_exists():
    """Testa verificação quando vídeo não existe no S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        service.s3_client = mock_s3
        
        mock_s3.head_object.side_effect = Exception("Not Found")
        
        exists = service.video_exists("videos/nonexistent.mp4")
        
        assert exists is False

def test_s3_service_get_video_info():
    """Testa obtenção de informações do vídeo no S3"""
    with patch('app.s3_service.boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        service = S3Service()
        service.s3_client = mock_s3
        
        mock_response = {
            'ContentLength': 1024,
            'LastModified': datetime(2024, 1, 1, tzinfo=pytz.UTC),
            'ContentType': 'video/mp4'
        }
        mock_s3.head_object.return_value = mock_response
        
        info = service.get_video_info("videos/test.mp4")
        
        assert info['key'] == "videos/test.mp4"
        assert info['size'] == 1024
        assert info['content_type'] == 'video/mp4'
        assert '2024-01-01' in info['last_modified']