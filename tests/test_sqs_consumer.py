import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import aioboto3
from botocore.exceptions import ClientError

from app.sqs_consumer import SQSConsumer

# ========== Fixtures ==========

@pytest.fixture
def mock_aws_credentials():
    """Mock das credenciais AWS"""
    with patch.dict(os.environ, {
        'AWS_ACCESS_KEY_ID': 'test-access-key',
        'AWS_SECRET_ACCESS_KEY': 'test-secret-key'
    }):
        yield

@pytest.fixture
def mock_aws_credentials_with_token():
    """Mock das credenciais AWS com session token"""
    with patch.dict(os.environ, {
        'AWS_ACCESS_KEY_ID': 'test-access-key',
        'AWS_SECRET_ACCESS_KEY': 'test-secret-key',
        'AWS_SESSION_TOKEN': 'test-session-token'
    }):
        yield

@pytest.fixture
def sqs_consumer():
    """SQSConsumer com mocks corrigidos"""
    with patch('boto3.client') as mock_boto_client:
        with patch('aioboto3.Session') as mock_session_class:
            # Mock do cliente SQS síncrono
            mock_sqs_client = Mock()
            mock_boto_client.return_value = mock_sqs_client
            
            # Cria um mock assíncrono para o cliente SQS
            mock_async_sqs_client = AsyncMock()
            
            # Configura o mock para simular o context manager assíncrono
            async def async_context_manager():
                return mock_async_sqs_client
            
            # Cria um mock para a sessão
            mock_session = Mock()
            # Configura client() para retornar um objeto que suporta async with
            mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_async_sqs_client)
            mock_session.client.return_value.__aexit__ = AsyncMock()
            
            mock_session_class.return_value = mock_session
            
            consumer = SQSConsumer(
                queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
            )
            
            consumer.sqs_client = mock_sqs_client
            consumer.session = mock_session
            consumer._mock_async_client = mock_async_sqs_client  # Adiciona para acesso nos testes
            
            yield consumer

@pytest.fixture
def mock_sqs_message():
    """Cria uma mensagem SQS mockada"""
    return {
        'Body': json.dumps({
            's3Key': 'videos/test-video.mp4',
            'title': 'Test Video',
            'description': 'Test Description',
            'uploadedAt': '2024-01-01T00:00:00Z'
        }),
        'ReceiptHandle': 'test-receipt-handle',
        'MessageId': 'test-message-id'
    }

# ========== Testes de Inicialização ==========

def test_sqs_consumer_initialization_with_env_credentials():
    """Testa inicialização do SQSConsumer com credenciais de ambiente"""
    with patch.dict(os.environ, {
        'AWS_ACCESS_KEY_ID': 'env-access-key',
        'AWS_SECRET_ACCESS_KEY': 'env-secret-key'
    }):
        with patch('boto3.client') as mock_boto_client:
            with patch('aioboto3.Session') as mock_session_class:
                mock_boto_client.return_value = Mock()
                mock_session_class.return_value = Mock()
                
                consumer = SQSConsumer(
                    queue_url="https://sqs.test.queue"
                )
                
                assert consumer.queue_url == "https://sqs.test.queue"
                assert consumer.aws_access_key_id == "env-access-key"
                assert consumer.aws_secret_access_key == "env-secret-key"
                assert consumer.aws_session_token is None
                assert consumer.region_name == "us-east-1"
                mock_boto_client.assert_called_once()

# ========== Testes de Consumo de Mensagens ==========

@pytest.mark.asyncio
async def test_consume_messages_success(sqs_consumer, mock_sqs_message):
    """Testa consumo bem-sucedido de mensagens"""
    # Configura o mock do cliente assíncrono
    mock_async_client = sqs_consumer._mock_async_client
    
    # Configura os métodos do cliente
    mock_async_client.receive_message = AsyncMock(return_value={
        'Messages': [mock_sqs_message]
    })
    mock_async_client.delete_message = AsyncMock()
    
    # Mock do process_message
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = True
        
        results = await sqs_consumer.consume_messages(max_messages=5, wait_time=10)
        
        assert len(results) == 1
        assert results[0]['processed'] is True
        assert results[0]['message']['s3Key'] == 'videos/test-video.mp4'
        
        mock_async_client.receive_message.assert_called_once_with(
            QueueUrl=sqs_consumer.queue_url,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=10,
            MessageAttributeNames=['All']
        )
        mock_async_client.delete_message.assert_called_once_with(
            QueueUrl=sqs_consumer.queue_url,
            ReceiptHandle='test-receipt-handle'
        )
        mock_process.assert_called_once()

@pytest.mark.asyncio
async def test_consume_messages_empty_queue(sqs_consumer):
    """Testa consumo quando a fila está vazia"""
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(return_value={})  # Sem 'Messages'
    
    results = await sqs_consumer.consume_messages()
    
    assert results == []
    mock_async_client.receive_message.assert_called_once()

@pytest.mark.asyncio
async def test_consume_messages_multiple_messages(sqs_consumer):
    """Testa consumo de múltiplas mensagens"""
    mock_messages = [
        {
            'Body': json.dumps({'s3Key': f'video{i}.mp4', 'title': f'Video {i}'}),
            'ReceiptHandle': f'receipt{i}',
            'MessageId': f'msg{i}'
        }
        for i in range(3)
    ]
    
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(return_value={'Messages': mock_messages})
    mock_async_client.delete_message = AsyncMock()
    
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = True
        
        results = await sqs_consumer.consume_messages(max_messages=3)
        
        assert len(results) == 3
        assert mock_async_client.delete_message.call_count == 3
        assert mock_process.call_count == 3

@pytest.mark.asyncio
async def test_consume_messages_processing_failure(sqs_consumer, mock_sqs_message):
    """Testa quando o processamento de uma mensagem falha"""
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(return_value={
        'Messages': [mock_sqs_message]
    })
    mock_async_client.delete_message = AsyncMock()
    
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = False  # Processamento falhou
        
        results = await sqs_consumer.consume_messages()
        
        assert len(results) == 1
        assert results[0]['processed'] is False
        mock_async_client.delete_message.assert_not_called()  # Não deleta se falhou

@pytest.mark.asyncio
async def test_consume_messages_json_error(sqs_consumer):
    """Testa quando o corpo da mensagem não é JSON válido"""
    mock_message = {
        'Body': 'invalid-json',
        'ReceiptHandle': 'test-receipt',
        'MessageId': 'test-msg'
    }
    
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(return_value={'Messages': [mock_message]})
    
    results = await sqs_consumer.consume_messages()
    
    assert results == []
    # Não deve lançar exceção, apenas logar erro

@pytest.mark.asyncio
async def test_consume_messages_exception_handling(sqs_consumer):
    """Testa tratamento de exceções durante consumo"""
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(side_effect=Exception("SQS Error"))
    
    results = await sqs_consumer.consume_messages()

    assert results == [] or results is None

# ========== Testes de Processamento de Mensagens ==========

@pytest.mark.asyncio
async def test_process_message_default_implementation(sqs_consumer):
    """Testa a implementação padrão de process_message"""
    message = {
        's3Key': 'videos/test.mp4',
        'title': 'Test Video'
    }
    
    result = await sqs_consumer.process_message(message)
    
    assert result is True  # Implementação padrão sempre retorna True

# ========== Testes de Parâmetros Customizados ==========

@pytest.mark.asyncio
async def test_consume_messages_with_custom_parameters(sqs_consumer, mock_sqs_message):
    """Testa consumo com parâmetros customizados"""
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(return_value={
        'Messages': [mock_sqs_message]
    })
    mock_async_client.delete_message = AsyncMock()
    
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock):
        await sqs_consumer.consume_messages(
            max_messages=1,  # Valor diferente do padrão (10)
            wait_time=5     # Valor diferente do padrão (20)
        )
        
        mock_async_client.receive_message.assert_called_with(
            QueueUrl=sqs_consumer.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5,
            MessageAttributeNames=['All']
        )

# ========== Testes de Deleção de Mensagens ==========

@pytest.mark.asyncio
async def test_message_deletion_on_success(sqs_consumer, mock_sqs_message):
    """Testa se mensagem é deletada após processamento bem-sucedido"""
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(return_value={
        'Messages': [mock_sqs_message]
    })
    mock_async_client.delete_message = AsyncMock()
    
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = True
        
        await sqs_consumer.consume_messages()
        
        # Verifica se delete_message foi chamado com o handle correto
        mock_async_client.delete_message.assert_called_once_with(
            QueueUrl=sqs_consumer.queue_url,
            ReceiptHandle='test-receipt-handle'
        )

@pytest.mark.asyncio
async def test_message_not_deleted_on_failure(sqs_consumer, mock_sqs_message):
    """Testa se mensagem NÃO é deletada após processamento falho"""
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(return_value={
        'Messages': [mock_sqs_message]
    })
    mock_async_client.delete_message = AsyncMock()
    
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = False  # Processamento falhou
        
        await sqs_consumer.consume_messages()
        
        # Não deve chamar delete_message
        mock_async_client.delete_message.assert_not_called()

# ========== Testes de Concorrência ==========

@pytest.mark.asyncio
async def test_concurrent_message_processing(sqs_consumer):
    """Testa processamento concorrente de mensagens"""
    mock_messages = [
        {
            'Body': json.dumps({'s3Key': f'video{i}.mp4'}),
            'ReceiptHandle': f'receipt{i}',
            'MessageId': f'msg{i}'
        }
        for i in range(5)
    ]
    
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(return_value={'Messages': mock_messages})
    mock_async_client.delete_message = AsyncMock()
    
    # Usa um AsyncMock que registra a ordem das chamadas
    call_order = []
    
    async def mock_process_ordered(message):
        call_order.append(message.get('s3Key'))
        await asyncio.sleep(0.01)  # Simula processamento
        return True
    
    with patch.object(sqs_consumer, 'process_message', side_effect=mock_process_ordered):
        await sqs_consumer.consume_messages()
        
        # Verifica se todas as mensagens foram processadas
        assert len(call_order) == 5

@pytest.mark.asyncio
async def test_consume_messages_with_message_attributes(sqs_consumer):
    """Testa consumo com atributos de mensagem"""
    mock_message_with_attrs = {
        'Body': json.dumps({'s3Key': 'video.mp4'}),
        'ReceiptHandle': 'receipt',
        'MessageId': 'msg1',
        'MessageAttributes': {
            'CustomAttribute': {
                'StringValue': 'CustomValue',
                'DataType': 'String'
            }
        }
    }
    
    mock_async_client = sqs_consumer._mock_async_client
    mock_async_client.receive_message = AsyncMock(return_value={
        'Messages': [mock_message_with_attrs]
    })
    mock_async_client.delete_message = AsyncMock()
    
    with patch.object(sqs_consumer, 'process_message', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = True
        
        await sqs_consumer.consume_messages()
        
        # Verifica se MessageAttributeNames=['All'] foi passado
        call_kwargs = mock_async_client.receive_message.call_args[1]
        assert 'MessageAttributeNames' in call_kwargs
        assert call_kwargs['MessageAttributeNames'] == ['All']

if __name__ == "__main__":
    pytest.main([__file__, "-v"])