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
        # Precisamos mockar o S3Service para evitar que ele tente conectar na AWS no __init__
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

@pytest.mark.asyncio
async def test_process_message_sqs_success_with_email():
    """Testa se o processamento via SQS dispara o e-mail corretamente para o destinatário"""
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_email_service = AsyncMock()
        # Mocking S3Service to avoid AWS connection
        with patch('app.video_processor.S3Service') as mock_s3_class:
            processor = VideoProcessor(
                upload_dir=temp_dir,
                output_dir=temp_dir,
                email_service=mock_email_service
            )
            
            message = {
                's3Key': 'videos/test.mp4',
                'title': 'Video do Hackathon',
                'email': 'instrutor@kungfu.com.br' # E-mail vindo do payload SQS
            }
            
            # Mockamos o processamento interno para focar na lógica da mensagem e e-mail
            with patch.object(processor, 'process_video_from_s3', new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {
                    "status": ProcessingStatus.COMPLETED, 
                    "zip_filename": "res_frames.zip",
                    "video_id": "123"
                }
                
                result = await processor.process_message(message)
                
                assert result is True
                # Pequena pausa para permitir que a task do asyncio.create_task rode no loop
                await asyncio.sleep(0.1)
                
                # VERIFICAÇÃO CRUCIAL: O e-mail foi enviado para o endereço certo?
                mock_email_service.send_process_completion.assert_called_once_with(
                    recipient_email='instrutor@kungfu.com.br',
                    video_title='Video do Hackathon',
                    zip_filename='res_frames.zip'
                )

@pytest.mark.asyncio
async def test_internal_processing_with_s3_upload():
    """Testa se a lógica interna realmente chama o upload para o S3 após gerar o ZIP"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service') as mock_s3_class:
            mock_s3_service = Mock()
            mock_s3_class.return_value = mock_s3_service
            
            processor = VideoProcessor(upload_dir=temp_dir, output_dir=temp_dir)
            
            # Criamos um arquivo de vídeo fake para o teste
            fake_video = Path(temp_dir) / "test_video.mp4"
            fake_video.write_text("fake video content")
            
            # Mocks para as funções de utilitários
            with patch('app.video_processor.extract_frames_from_video', return_value=["/tmp/f1.jpg"]), \
                 patch('app.video_processor.create_zip_from_images', return_value=True), \
                 patch('app.video_processor.cleanup_temp_files', return_value=True):
                
                result = await processor._process_video_internal(
                    video_path=str(fake_video),
                    user_id="user123",
                    video_metadata={'title': 'Test', 's3_key': 'v.mp4'}
                )
                
                assert result["status"] == ProcessingStatus.COMPLETED
                
                # VERIFICAÇÃO CRUCIAL: O método de upload para o S3 foi chamado?
                # Isso garante que o ZIP não ficou preso no container
                mock_s3_service.upload_video.assert_called_once()
                args, _ = mock_s3_service.upload_video.call_args
                assert "processed/" in args[1] # s3_key deve conter o prefixo processed/

@pytest.mark.asyncio
async def test_process_message_sqs_failure_notification():
    """Testa se o e-mail de erro é enviado em caso de falha no processamento"""
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_email_service = AsyncMock()
        with patch('app.video_processor.S3Service'):
            processor = VideoProcessor(upload_dir=temp_dir, output_dir=temp_dir, email_service=mock_email_service)
            
            message = {'s3Key': 'v.mp4', 'title': 'Erro', 'email': 'user@test.com'}
            
            with patch.object(processor, 'process_video_from_s3', new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {"status": ProcessingStatus.FAILED, "error": "Codec incompatível"}
                
                await processor.process_message(message)
                await asyncio.sleep(0.1)
                
                # Verifica se o e-mail de erro foi disparado
                mock_email_service.send_process_error.assert_called_once()

def test_get_processed_files_filtering():
    """Garante que a listagem de arquivos ignora lixo e foca em ZIPs"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.video_processor.S3Service'):
            processor = VideoProcessor(upload_dir=temp_dir, output_dir=temp_dir)
            
            # Cria um ZIP e um arquivo TXT
            (Path(temp_dir) / "result.zip").write_bytes(b"data")
            (Path(temp_dir) / "logs.txt").write_text("logs")
            
            files = processor.get_processed_files()
            assert len(files) == 1
            assert files[0]["filename"] == "result.zip"