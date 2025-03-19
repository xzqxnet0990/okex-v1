import pytest
import asyncio
from unittest.mock import Mock, patch
from utils.decorators import retry

def test_retry_sync_success():
    """Test retry decorator with a synchronous function that succeeds on first try"""
    mock_func = Mock(return_value="success")
    
    @retry(retries=3, delay=0.1)
    def test_func():
        return mock_func()
    
    result = test_func()
    
    assert result == "success"
    assert mock_func.call_count == 1  # Function should be called only once

def test_retry_sync_fail_then_succeed():
    """Test retry decorator with a synchronous function that fails first then succeeds"""
    # Create a fresh mock for Log
    with patch('utils.decorators.Log') as mock_log:
        mock_func = Mock(side_effect=[ValueError("First failure"), "success"])
        
        @retry(retries=3, delay=0.1)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        assert mock_func.call_count == 2  # Function should be called twice
        assert mock_log.call_count == 2  # Log should be called twice for each failure (error + retry message)

def test_retry_sync_all_fail():
    """Test retry decorator with a synchronous function that always fails"""
    # Create a fresh mock for Log
    with patch('utils.decorators.Log') as mock_log:
        error = ValueError("Persistent failure")
        mock_func = Mock(side_effect=[error, error, error])
        
        @retry(retries=3, delay=0.1)
        def test_func():
            return mock_func()
        
        with pytest.raises(ValueError) as excinfo:
            test_func()
        
        assert str(excinfo.value) == "Persistent failure"
        assert mock_func.call_count == 3  # Function should be called three times
        assert mock_log.call_count == 6  # Log should be called twice for each failure (2 * 3 = 6)

@pytest.mark.asyncio
async def test_retry_async_success():
    """Test retry decorator with an asynchronous function that succeeds on first try"""
    mock_func = Mock(return_value="success")
    
    @retry(retries=3, delay=0.1)
    async def test_func():
        return mock_func()
    
    result = await test_func()
    
    assert result == "success"
    assert mock_func.call_count == 1  # Function should be called only once

@pytest.mark.asyncio
async def test_retry_async_fail_then_succeed():
    """Test retry decorator with an asynchronous function that fails first then succeeds"""
    mock_func = Mock(side_effect=[ValueError("First failure"), "success"])
    
    @retry(retries=3, delay=0.1)
    async def test_func():
        return mock_func()
    
    result = await test_func()
    
    assert result == "success"
    assert mock_func.call_count == 2  # Function should be called twice

@pytest.mark.asyncio
async def test_retry_async_all_fail():
    """Test retry decorator with an asynchronous function that always fails"""
    error = ValueError("Persistent failure")
    mock_func = Mock(side_effect=[error, error, error])
    
    @retry(retries=3, delay=0.1)
    async def test_func():
        return mock_func()
    
    with pytest.raises(ValueError) as excinfo:
        await test_func()
    
    assert str(excinfo.value) == "Persistent failure"
    assert mock_func.call_count == 3  # Function should be called three times

@pytest.mark.asyncio
async def test_retry_async_with_real_delay():
    """Test retry decorator with an asynchronous function with actual delay"""
    # Create a function that fails the first two times and succeeds on the third try
    call_times = []
    
    @retry(retries=3, delay=0.2)
    async def test_func():
        call_times.append(asyncio.get_event_loop().time())
        if len(call_times) < 3:
            raise ValueError(f"Failure {len(call_times)}")
        return "success"
    
    start_time = asyncio.get_event_loop().time()
    result = await test_func()
    
    assert result == "success"
    assert len(call_times) == 3  # Function should be called three times
    
    # Check that delays between calls are approximately correct
    assert call_times[1] - call_times[0] >= 0.15  # Allow some tolerance
    assert call_times[2] - call_times[1] >= 0.15  # Allow some tolerance

def test_retry_with_custom_parameters():
    """Test retry decorator with custom parameters"""
    # Create a fresh mock for Log
    with patch('utils.decorators.Log') as mock_log:
        mock_func = Mock(side_effect=[ValueError("Failure 1"), 
                                     ValueError("Failure 2"), 
                                     ValueError("Failure 3"), 
                                     ValueError("Failure 4"), 
                                     "success"])
        
        @retry(retries=5, delay=0.1)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        assert mock_func.call_count == 5  # Function should be called five times
        assert mock_log.call_count == 8  # Log should be called twice for each failure (2 * 4 = 8)

def test_retry_preserves_function_metadata():
    """Test that retry decorator preserves function metadata"""
    @retry(retries=3, delay=0.1)
    def test_func(a, b):
        """Test function docstring"""
        return a + b
    
    assert test_func.__name__ == "test_func"
    assert test_func.__doc__ == "Test function docstring"
    
    result = test_func(1, 2)
    assert result == 3 