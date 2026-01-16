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
    """Testa inicialização do VideoProcessor"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            
            assert processor.upload_dir == Path(temp_dir)
            assert processor.output_dir == Path(temp_dir)
            assert processor.s3_bucket == S3_BUCKET_NAME
            mock_s3_class.assert_called_once()

@pytest.mark.asyncio
async def test_process_video_from_s3_success():
    """Testa processamento de vídeo do S3 com sucesso"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            processor.s3_service = mock_s3_service
            
            # Mock dos métodos
            mock_s3_service.video_exists = Mock(return_value=True)
            mock_s3_service.download_video = Mock()
            
            # Mock do processamento interno
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
                    title="Test Video",
                    description="Test Description",
                    source="test"
                )
                
                assert result == expected_result
                mock_s3_service.video_exists.assert_called_once_with("videos/test.mp4")
                mock_s3_service.download_video.assert_called_once()

@pytest.mark.asyncio
async def test_process_video_from_s3_not_found():
    """Testa processamento quando vídeo não existe no S3"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            processor.s3_service = mock_s3_service
            
            # Mock do video_exists retornando False
            mock_s3_service.video_exists = Mock(return_value=False)
            
            result = await processor.process_video_from_s3(
                s3_key="videos/nonexistent.mp4",
                title="Test"
            )
            
            assert result["status"] == ProcessingStatus.FAILED
            assert "não encontrado" in result["error"].lower()
            mock_s3_service.video_exists.assert_called_once_with("videos/nonexistent.mp4")
            mock_s3_service.download_video.assert_not_called()

@pytest.mark.asyncio
async def test_process_video_from_s3_download_error():
    """Testa processamento quando download do S3 falha"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            processor.s3_service = mock_s3_service
            
            # Mock dos métodos
            mock_s3_service.video_exists = Mock(return_value=True)
            mock_s3_service.download_video = Mock(side_effect=Exception("Download failed"))
            
            result = await processor.process_video_from_s3(
                s3_key="videos/test.mp4",
                title="Test"
            )
            
            assert result["status"] == ProcessingStatus.FAILED
            assert "download" in result["error"].lower()
            mock_s3_service.video_exists.assert_called_once()

@pytest.mark.asyncio
async def test_process_video_internal_no_frames():
    """Testa processamento quando não é possível extrair frames"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            
            # Cria arquivo vazio
            empty_file = Path(temp_dir) / "empty.mp4"
            empty_file.write_bytes(b"invalid video content")
            
            result = await processor._process_video_internal(
                video_path=str(empty_file),
                user_id="test-user",
                video_metadata={'title': 'Test'}
            )
            
            assert result["status"] == ProcessingStatus.FAILED
            assert any(word in result["error"].lower() 
                      for word in ['extrair', 'frames', 'process', 'error'])

@pytest.mark.asyncio
async def test_process_message_sqs_no_s3key():
    """Testa processamento de mensagem SQS sem s3Key"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            
            message = {
                'title': 'Test Video',
                'description': 'Test Description'
            }
            
            result = await processor.process_message(message)
            
            assert result is False

@pytest.mark.asyncio
async def test_process_message_sqs_failed():
    """Testa processamento de mensagem SQS quando falha"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            processor.s3_service = mock_s3_service
            
            message = {
                's3Key': 'videos/test.mp4',
                'title': 'Test Video'
            }
            
            with patch.object(processor, 'process_video_from_s3', 
                            new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {
                    "status": ProcessingStatus.FAILED,
                    "error": "Processing failed"
                }
                
                result = await processor.process_message(message)
                
                assert result is False

def test_list_available_videos():
    """Testa listagem de vídeos disponíveis no S3"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            processor.s3_service = mock_s3_service
            
            mock_videos = [
                {'key': 'videos/video1.mp4', 'size': 1024},
                {'key': 'videos/video2.mp4', 'size': 2048}
            ]
            mock_s3_service.list_videos = Mock(return_value=mock_videos)
            
            videos = processor.list_available_videos("videos/")
            
            assert videos == mock_videos
            mock_s3_service.list_videos.assert_called_once_with("videos/")

def test_get_processed_files():
    """Testa listagem de arquivos processados"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            
            # Cria alguns arquivos ZIP de teste
            zip1 = processor.output_dir / "test1_frames.zip"
            zip1.write_bytes(b"zip content 1")
            
            zip2 = processor.output_dir / "test2_frames.zip"
            zip2.write_bytes(b"zip content 2")
            
            # Arquivo que não é ZIP (não deve aparecer)
            other_file = processor.output_dir / "other.txt"
            other_file.write_text("not a zip")
            
            files = processor.get_processed_files()
            
            assert len(files) == 2
            filenames = {f["filename"] for f in files}
            assert "test1_frames.zip" in filenames
            assert "test2_frames.zip" in filenames
            assert "other.txt" not in filenames
            
            # Verifica estrutura dos dados
            for file_info in files:
                assert "filename" in file_info
                assert "size" in file_info
                assert "created_at" in file_info
                assert "path" in file_info
                assert "url" in file_info
                assert file_info["url"].startswith("/download/")

def test_get_processed_files_empty_dir():
    """Testa listagem quando diretório de outputs está vazio"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            files = processor.get_processed_files()
            assert files == []

@pytest.mark.asyncio
async def test_start_sqs_consumer_no_queue():
    """Testa início do consumidor SQS quando não há fila configurada"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            processor.queue_url = None
            await processor.start_sqs_consumer()
            # Não deve lançar exceção

def test_stop_sqs_consumer():
    """Testa parada do consumidor SQS"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir
            )
            processor.is_consuming = True
            processor.stop_sqs_consumer()
            assert processor.is_consuming is False