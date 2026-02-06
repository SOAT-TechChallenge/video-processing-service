import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from app.sqs_consumer import SQSConsumer

# ========== Fixtures ==========

@pytest.fixture
def mock_aws_credentials():
    """Mock das credenciais AWS para evitar leitura de arquivos locais"""
    with patch.dict(os.environ, {
        'AWS_ACCESS_KEY_ID': 'test-access-key',
        'AWS_SECRET_ACCESS_KEY': 'test-secret-key',
        'AWS_REGION': 'us-east-1'
    }):
        yield

@pytest.fixture
def sqs_consumer(mock_aws_credentials):
    """Instancia o SQSConsumer com mocks de sessão assíncrona"""
    with patch('boto3.client') as mock_boto_client:
        with patch('aioboto3.Session') as mock_session_class:
            mock_sqs_client = Mock()
            mock_boto_client.return_value = mock_sqs_client
            
            mock_async_sqs_client = AsyncMock()
            
            # Simulação do context manager: async with session.client('sqs')
            mock_session = Mock()
            mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_async_sqs_client)
            mock_session.client.return_value.__aexit__ = AsyncMock()
            
            mock_session_class.return_value = mock_session
            
            consumer = SQSConsumer(
                queue_url="https://sqs.us-east-1.amazonaws.com/12345678/test-queue"
            )
            
            # Injeta o mock para facilitar o acesso nos asserts
            consumer._mock_async_client = mock_async_sqs_client
            yield consumer

@pytest.fixture
def mock_sqs_message():
    """Payload padrão de uma mensagem SQS simulada"""
    return {
        'Body': json.dumps({
            's3Key': 'videos/test-video.mp4',
            'title': 'Test Video',
            'email': 'user@example.com'
        }),
        'ReceiptHandle': 'test-receipt-handle',
        'MessageId': 'test-message-id'
    }

# ========== Testes de Fluxo ==========

@pytest.mark.asyncio
async def test_consume_messages_success(sqs_consumer, mock_sqs_message):
    """Garante que a mensagem é processada e DELETADA da fila após o sucesso"""
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message.return_value = {'Messages': [mock_sqs_message]}
    
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = True
        
        results = await sqs_consumer.consume_messages(max_messages=1)
        
        assert len(results) == 1
        assert results[0]['processed'] is True
        # PONTO CRÍTICO: Deletou a mensagem?
        mock_async_client.delete_message.assert_called_once_with(
            QueueUrl=sqs_consumer.queue_url,
            ReceiptHandle='test-receipt-handle'
        )

@pytest.mark.asyncio
async def test_consume_messages_processing_failure(sqs_consumer, mock_sqs_message):
    """Garante que a mensagem NÃO é deletada em caso de erro (DLQ/Retry)"""
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message.return_value = {'Messages': [mock_sqs_message]}
    
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = False # Simula falha no processamento
        
        await sqs_consumer.consume_messages()
        
        # A mensagem deve permanecer na fila para nova tentativa
        mock_async_client.delete_message.assert_not_called()

@pytest.mark.asyncio
async def test_consume_messages_empty_queue(sqs_consumer):
    """Valida comportamento de fila vazia"""
    sqs_consumer._mock_async_client.receive_message.return_value = {}
    results = await sqs_consumer.consume_messages()
    assert results == []

@pytest.mark.asyncio
async def test_consume_messages_json_error(sqs_consumer):
    """Valida tratamento de mensagens com corpo inválido"""
    sqs_consumer._mock_async_client.receive_message.return_value = {
        'Messages': [{'Body': 'invalid-json', 'ReceiptHandle': 'abc'}]
    }
    # Não deve quebrar o loop do consumidor
    results = await sqs_consumer.consume_messages()
    assert results == []

@pytest.mark.asyncio
async def test_concurrent_message_processing(sqs_consumer):
    """Valida se o processamento é feito de forma concorrente (Performance)"""
    mock_messages = [
        {'Body': json.dumps({'s3Key': f'v{i}.mp4'}), 'ReceiptHandle': f'r{i}'}
        for i in range(5)
    ]
    sqs_consumer._mock_async_client.receive_message.return_value = {'Messages': mock_messages}
    
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = True
        await sqs_consumer.consume_messages()
        assert mock_process.call_count == 5

if __name__ == "__main__":
    pytest.main([__file__, "-v"])