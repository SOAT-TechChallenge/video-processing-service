import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from app.video_processor import VideoProcessor
from app.schemas import ProcessingStatus
from app.config import S3_BUCKET_NAME

# ========== Testes para VideoProcessor ==========

@pytest.mark.asyncio
async def test_video_processor_initialization():
    """Testa inicialização do VideoProcessor com EmailService injetado"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            mock_email_service = Mock() 
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir,
                email_service=mock_email_service
            )
            
            assert processor.upload_dir == Path(temp_dir)
            assert processor.output_dir == Path(temp_dir)
            assert processor.email_service == mock_email_service
            assert processor.s3_bucket == S3_BUCKET_NAME
            mock_s3_class.assert_called_once()

@pytest.mark.asyncio
async def test_process_video_from_s3_success():
    """Testa processamento de vídeo do S3 com sucesso e disparo de email"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            mock_email_service = AsyncMock() 
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir,
                email_service=mock_email_service
            )
            processor.s3_service = mock_s3_service
            
            mock_s3_service.video_exists = Mock(return_value=True)
            mock_s3_service.download_video = Mock()
            
            expected_result = {
                "video_id": "test-id",
                "status": ProcessingStatus.COMPLETED,
                "zip_filename": "test_frames.zip",
                "zip_path": "/tmp/test_frames.zip",
                "frame_count": 5,
                "error": None
            }
            
            with patch.object(processor, '_process_video_internal', 
                            new_callable=AsyncMock) as mock_process:
                mock_process.return_value = expected_result
                
                result = await processor.process_video_from_s3(
                    s3_key="videos/test.mp4",
                    title="Test Video"
                )
                
                assert result == expected_result
                # Verifica se o serviço de email foi acionado após o sucesso
                mock_email_service.send_process_completion.assert_called_once_with(
                    "test@user.com", "Test Video", "test_frames.zip"
                )

@pytest.mark.asyncio
async def test_process_video_from_s3_not_found():
    """Testa processamento quando vídeo não existe no S3 e envia aviso de erro"""
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_email_service = AsyncMock()
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir,
                email_service=mock_email_service
            )
            processor.s3_service = mock_s3_service
            mock_s3_service.video_exists = Mock(return_value=False)
            
            result = await processor.process_video_from_s3(
                s3_key="videos/nonexistent.mp4",
                title="Test Video"
            )
            
            assert result["status"] == ProcessingStatus.FAILED
            # Valida que o usuário foi notificado sobre a falha
            mock_email_service.send_process_error.assert_called_once()
            assert "não encontrado" in result["error"].lower()

@pytest.mark.asyncio
async def test_process_message_sqs_success():
    """Testa fluxo vindo do SQS injetando dependências"""
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_email_service = AsyncMock()
        processor = VideoProcessor(
            upload_dir=temp_dir,
            output_dir=temp_dir,
            email_service=mock_email_service
        )
        
        message = {
            's3Key': 'videos/test.mp4',
            'title': 'Video SQS',
            'email': 'sqs@user.com'
        }
        
        with patch.object(processor, 'process_video_from_s3', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"status": ProcessingStatus.COMPLETED, "zip_filename": "res.zip"}
            
            result = await processor.process_message(message)
            
            assert result is True
            mock_process.assert_called_once()

def test_get_processed_files():
    """Testa listagem de arquivos garantindo que apenas ZIPs apareçam"""
    with tempfile.TemporaryDirectory() as temp_dir:
        processor = VideoProcessor(
            upload_dir=temp_dir,
            output_dir=temp_dir,
            email_service=Mock()
        )
        
        # Cria arquivos de teste
        (Path(temp_dir) / "test1_frames.zip").write_bytes(b"zip1")
        (Path(temp_dir) / "other.txt").write_text("not a zip")
        
        files = processor.get_processed_files()
        assert len(files) == 1
        assert files[0]["filename"] == "test1_frames.zip"

@pytest.mark.asyncio
async def test_stop_sqs_consumer():
    """Testa parada segura do consumidor evitando erros de permissão em /app"""
    with tempfile.TemporaryDirectory() as temp_dir:
        processor = VideoProcessor(
            upload_dir=temp_dir,
            output_dir=temp_dir,
            email_service=Mock()
        )
        processor.is_consuming = True
        processor.stop_sqs_consumer()
        assert processor.is_consuming is False