import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile
from fastapi import HTTPException, BackgroundTasks
from app.main import app, services
from app.schemas import ProcessingStatus

@pytest.fixture
def temp_zip_file():
    """Cria um arquivo ZIP temporário para testes de download"""
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        tmp.write(b"fake zip content")
        tmp_path = tmp.name
    yield tmp_path
    try:
        os.unlink(tmp_path)
    except:
        pass

# --- Testes de Endpoints ---

@pytest.mark.asyncio
async def test_process_s3_video_manual_logic():
    """
    🚀 NOVO: Testa se o endpoint manual agenda a tarefa corretamente 
    usando a lógica centralizada de process_message.
    """
    mock_processor = Mock()
    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    
    with patch.dict(services, {"processor": mock_processor}):
        from app.main import process_s3_video
        
        s3_key = "videos/aula_kungfu.mp4"
        email = "instrutor@teste.com"
        
        response = await process_s3_video(
            s3_key=s3_key,
            background_tasks=mock_background_tasks,
            title="Aula Manual",
            email=email
        )

        # Verifica se retornou 202 Accepted
        assert response.status_code == 202
        
        # Verifica se o process_message foi agendado em background com o dicionário correto
        mock_background_tasks.add_task.assert_called_once()
        called_func, called_msg = mock_background_tasks.add_task.call_args[0]
        
        assert called_func == mock_processor.process_message
        assert called_msg['s3Key'] == s3_key
        assert called_msg['email'] == email
        assert called_msg['title'] == "Aula Manual"

def test_list_s3_videos_service_not_initialized():
    """Testa erro 500 quando S3 service não está no dicionário global"""
    with patch.dict(services, {}, clear=True):
        from app.main import list_s3_videos
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(list_s3_videos())
        assert exc_info.value.status_code == 500

def test_download_zip_logic(temp_zip_file):
    """Testa a lógica do endpoint de download e tratamento de path"""
    mock_processor = Mock()
    filename = Path(temp_zip_file).name
    mock_processor.output_dir = Path(temp_zip_file).parent
    
    with patch.dict(services, {"processor": mock_processor}):
        from app.main import download_zip
        with patch('app.main.unquote', return_value=filename):
            result = asyncio.run(download_zip(filename))
            assert result.status_code == 200
            assert result.media_type == "application/zip"

def test_root_endpoint_logic():
    """Testa a lógica do endpoint raiz e valida a versão 2.2.0"""
    with patch('app.main.SQS_QUEUE_URL', 'http://test-queue'):
        with patch.dict(services, {"email": Mock()}):
            from app.main import root
            result = asyncio.run(root())
            assert result["version"] == "2.2.0"
            assert result["mode"] == "auto"

def test_health_check_logic_healthy():
    """Testa health check status"""
    mock_processor = Mock()
    with patch.dict(services, {"processor": mock_processor}):
        from app.main import health_check
        result = asyncio.run(health_check())
        assert result["status"] == "healthy"

@pytest.mark.asyncio
async def test_lifespan_flow():
    """Testa o ciclo de vida completo (Startup -> Shutdown)"""
    from app.main import lifespan
    
    mock_processor = Mock()
    mock_processor.start_sqs_consumer = AsyncMock()
    
    # Patch das classes para evitar IO real
    with patch('app.main.S3Service', return_value=Mock()), \
         patch('app.main.EmailService', return_value=Mock()), \
         patch('app.main.VideoProcessor', return_value=mock_processor), \
         patch('app.main.print_config'):
        
        async with lifespan(app):
            assert "processor" in services
            assert "s3" in services
            assert "email" in services
        
        # Garante que o shutdown cancelou/parou o consumidor
        mock_processor.stop_sqs_consumer.assert_called()

def test_list_processed_files_logic():
    """Testa listagem de arquivos processados"""
    mock_processor = Mock()
    mock_files = [{"filename": "resultado.zip"}]
    mock_processor.get_processed_files.return_value = mock_files
    
    with patch.dict(services, {"processor": mock_processor}):
        from app.main import list_processed_files
        result = asyncio.run(list_processed_files())
        assert result["files"] == mock_files

def test_app_metadata():
    """Valida metadados da instância FastAPI"""
    assert app.title == "Video Processing Service"
    assert app.version == "2.2.0"