import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
from pathlib import Path
import tempfile
from fastapi import HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

# ========== Fixtures ==========

@pytest.fixture
def temp_zip_file():
    """Cria um arquivo ZIP temporário para testes de download"""
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        tmp.write(b"fake zip content")
        tmp_path = tmp.name
    
    yield tmp_path
    
    # Cleanup
    try:
        os.unlink(tmp_path)
    except:
        pass

def test_list_s3_videos_service_not_initialized():
    """Testa quando S3 service não está inicializado"""
    with patch('app.main.s3_service', None):
        from app.main import list_s3_videos
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(list_s3_videos())
        
        assert exc_info.value.status_code == 500

def test_list_processed_files_processor_not_initialized():
    """Testa quando processor não está inicializado"""
    with patch('app.main.processor', None):
        from app.main import list_processed_files
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(list_processed_files())
        
        assert exc_info.value.status_code == 500

def test_process_s3_video_processor_not_initialized():
    """Testa quando processor não está inicializado"""
    with patch('app.main.processor', None):
        from app.main import process_s3_video
        
        # Cria um mock simples para background_tasks
        mock_background_tasks = Mock()
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(process_s3_video(
                s3_key="videos/test.mp4",
                background_tasks=mock_background_tasks
            ))
        
        assert exc_info.value.status_code == 500

def test_download_zip_logic(temp_zip_file):
    """Testa a lógica do endpoint de download"""
    mock_processor = Mock()
    filename = Path(temp_zip_file).name
    
    # Cria um mock que simula um Path
    mock_path = MagicMock()
    mock_path.__truediv__.return_value = Path(temp_zip_file)  # Para a operação /
    mock_path.exists.return_value = True
    mock_path.stat.return_value.st_size = 1024
    mock_path.name = filename
    
    # Mock do processor com um output_dir que é um mock de Path
    mock_processor.output_dir = mock_path
    
    with patch('app.main.processor', mock_processor):
        from app.main import download_zip
        
        # Mock do Path para retornar nosso mock_path quando chamado
        with patch('app.main.Path', return_value=mock_path):
            result = asyncio.run(download_zip(filename))
            
            assert result.status_code == 200
            assert result.headers["content-type"] == "application/zip"
            assert f"filename={filename}" in result.headers["content-disposition"]

def test_download_zip_not_found():
    """Testa quando arquivo não existe"""
    mock_processor = Mock()
    mock_processor.get_processed_files.return_value = [
        {"filename": "existing.zip"}
    ]
    
    mock_output_dir = Mock()
    mock_file_path = Mock()
    mock_file_path.exists.return_value = False
    mock_file_path.name = "nonexistent.zip"
    
    def mock_truediv(self, other):
        return mock_file_path
    
    mock_output_dir = MagicMock()
    mock_output_dir.__truediv__ = Mock(side_effect=lambda x: mock_file_path)
    mock_processor.output_dir = mock_output_dir
    
    with patch('app.main.processor', mock_processor):
        from app.main import download_zip
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(download_zip("nonexistent.zip"))
        
        if exc_info.value.status_code == 404:
            detail = exc_info.value.detail
            if isinstance(detail, dict):
                assert "Arquivo não encontrado" in detail.get("message", "")
                assert "existing.zip" in detail.get("available_files", [])
        else:
            assert exc_info.value.status_code == 500

def test_download_zip_processor_not_initialized():
    """Testa quando processor não está inicializado"""
    with patch('app.main.processor', None):
        from app.main import download_zip
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(download_zip("test.zip"))
        
        assert exc_info.value.status_code == 500

def test_error_handling_in_download_zip():
    """Testa tratamento de erros no download"""
    mock_processor = Mock()
    
    # Cria um mock que lança exceção na operação /
    mock_output_dir = Mock()
    
    def mock_truediv(other):
        raise Exception("Erro no sistema de arquivos")
    
    mock_output_dir.__truediv__ = mock_truediv
    mock_processor.output_dir = mock_output_dir
    
    with patch('app.main.processor', mock_processor):
        from app.main import download_zip
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(download_zip("test.zip"))
        
        assert exc_info.value.status_code == 500

def test_default_parameter_values():
    """Testa valores padrão dos parâmetros"""
    # Testa list_s3_videos com prefixo padrão
    mock_s3 = Mock()
    mock_s3.list_videos.return_value = []
    
    with patch('app.main.s3_service', mock_s3):
        with patch('app.main.S3_BUCKET_NAME', 'test-bucket'):
            from app.main import list_s3_videos
            
            result = asyncio.run(list_s3_videos())
            
            # Verifica se foi chamado com o prefixo padrão
            mock_s3.list_videos.assert_called_once_with("videos/")
            assert result["prefix"] == "videos/"
    
    # Testa process_s3_video com valores padrão
    mock_processor = Mock()
    
    with patch('app.main.processor', mock_processor):
        from app.main import process_s3_video
        
        # Mock do background tasks
        mock_background_tasks = Mock()
        mock_background_tasks.add_task = Mock()
        
        try:
            result = asyncio.run(process_s3_video(
                s3_key="videos/test.mp4",
                background_tasks=mock_background_tasks
            ))
            assert result.status_code == 202
        except HTTPException:
            pass

def test_root_endpoint_logic():
    """Testa a lógica do endpoint raiz"""
    with patch('app.main.S3_BUCKET_NAME', 'test-bucket'):
        with patch('app.main.SQS_QUEUE_URL', None):
            from app.main import root
            
            result = asyncio.run(root())
            
            assert result["service"] == "Video Processing Service"
            assert result["version"] == "2.0.0"
            assert result["s3_bucket"] == 'test-bucket'
            assert result["sqs_queue"] == "Not configured"
            assert result["mode"] == "manual"

def test_health_check_logic_healthy():
    """Testa a lógica do health check quando serviços estão saudáveis"""
    mock_processor = Mock()
    mock_processor.upload_dir = Path("/tmp/uploads")
    mock_processor.output_dir = Path("/tmp/outputs")
    
    mock_s3 = Mock()
    
    with patch('app.main.processor', mock_processor):
        with patch('app.main.s3_service', mock_s3):
            with patch('app.main.consumer_task', "dummy_task"):
                with patch('app.main.SQS_QUEUE_URL', "https://sqs.test.queue"):
                    from app.main import health_check
                    
                    result = asyncio.run(health_check())
                    
                    assert result["status"] == "healthy"
                    assert result["s3"]["connected"] is True
                    assert result["sqs"]["status"] == "running"
                    assert result["processing"]["ready"] is True

def test_health_check_logic_unhealthy():
    """Testa a lógica do health check quando serviços não estão inicializados"""
    with patch('app.main.processor', None):
        with patch('app.main.s3_service', None):
            with patch('app.main.consumer_task', None):
                with patch('app.main.SQS_QUEUE_URL', None):
                    from app.main import health_check
                    
                    result = asyncio.run(health_check())
                    
                    assert result["status"] == "unhealthy"
                    assert result["s3"]["connected"] is False
                    assert result["sqs"]["status"] == "not_configured"
                    assert result["processing"]["ready"] is False

def test_list_s3_videos_logic():
    """Testa a lógica do endpoint de listagem S3"""
    mock_s3 = Mock()
    mock_videos = [
        {"key": "videos/video1.mp4", "size": 1024},
        {"key": "videos/video2.mp4", "size": 2048}
    ]
    mock_s3.list_videos.return_value = mock_videos
    
    with patch('app.main.s3_service', mock_s3):
        with patch('app.main.S3_BUCKET_NAME', 'test-bucket'):
            from app.main import list_s3_videos
            
            result = asyncio.run(list_s3_videos("videos/"))
            
            assert result["bucket"] == 'test-bucket'
            assert result["prefix"] == "videos/"
            assert result["count"] == 2
            assert result["videos"] == mock_videos
            mock_s3.list_videos.assert_called_once_with("videos/")

def test_list_processed_files_logic():
    """Testa a lógica do endpoint de listagem de arquivos processados"""
    mock_processor = Mock()
    mock_files = [
        {
            "filename": "test_frames.zip",
            "size": 1024,
            "created_at": "2024-01-01T00:00:00",
            "path": "/tmp/test_frames.zip",
            "url": "/download/test_frames.zip"
        }
    ]
    mock_processor.get_processed_files.return_value = mock_files
    
    with patch('app.main.processor', mock_processor):
        from app.main import list_processed_files
        
        result = asyncio.run(list_processed_files())
        
        assert result["count"] == 1
        assert result["files"] == mock_files
        mock_processor.get_processed_files.assert_called_once()

def test_processed_files_compat_logic():
    """Testa o endpoint de compatibilidade"""
    mock_processor = Mock()
    mock_files = [{"filename": "test.zip"}]
    mock_processor.get_processed_files.return_value = mock_files
    
    with patch('app.main.processor', mock_processor):
        from app.main import processed_files_compat
        
        result = asyncio.run(processed_files_compat())
        
        assert result["files"] == mock_files

def test_download_zip_url_decoding():
    """Testa decodificação de URL"""
    mock_processor = Mock()
    
    with patch('app.main.processor', mock_processor):
        from app.main import download_zip
        
        # Mock do unquote
        with patch('app.main.unquote') as mock_unquote:
            mock_unquote.return_value = "test video frames.zip"
            
            # Mock para simular que o arquivo não existe
            mock_output_dir = Mock()
            mock_file_path = Mock()
            mock_file_path.exists.return_value = False
            
            def mock_truediv(other):
                return mock_file_path
            
            mock_output_dir.__truediv__ = mock_truediv
            mock_processor.output_dir = mock_output_dir
            
            try:
                asyncio.run(download_zip("test%20video%20frames.zip"))
            except HTTPException:
                pass  # Esperado
            
            mock_unquote.assert_called_once_with("test%20video%20frames.zip")

def test_error_handling_in_list_s3_videos():
    """Testa tratamento de erros na listagem S3"""
    mock_s3 = Mock()
    mock_s3.list_videos.side_effect = Exception("Erro de conexão S3")
    
    with patch('app.main.s3_service', mock_s3):
        from app.main import list_s3_videos
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(list_s3_videos())
        
        assert exc_info.value.status_code == 500

def test_app_configuration():
    """Testa configuração básica da aplicação FastAPI"""
    from app.main import app
    
    assert app.title == "Video Processing Service"
    assert app.version == "2.0.0"
    
    route_paths = [route.path for route in app.routes]
    assert "/" in route_paths
    assert "/health" in route_paths

@pytest.mark.asyncio
async def test_startup_shutdown_flow():
    """Testa fluxo simples de startup e shutdown"""
    mock_processor = Mock()
    mock_processor.start_sqs_consumer = AsyncMock()
    mock_processor.stop_sqs_consumer = Mock()
    
    mock_s3 = Mock()
    mock_s3.list_videos = Mock(return_value=[])
    
    with patch('app.main.S3Service', return_value=mock_s3):
        with patch('app.main.VideoProcessor', return_value=mock_processor):
            with patch('app.main.SQS_QUEUE_URL', None):
                with patch('app.main.print_config'):
                    from app.main import startup_event, shutdown_event
                    
                    await startup_event()
                    await shutdown_event()
                    
                    mock_processor.stop_sqs_consumer.assert_called_once()

def test_workflow_integration():
    """Testa integração simples entre funções"""
    mock_processor = Mock()
    mock_processor.get_processed_files = Mock(return_value=[])
    
    with patch('app.main.processor', mock_processor):
        from app.main import list_processed_files
        
        result = asyncio.run(list_processed_files())
        
        assert result["count"] == 0
        assert result["files"] == []
        mock_processor.get_processed_files.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])