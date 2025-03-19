import os
import sys
import pytest
from unittest.mock import patch

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Global mock for the Log function to avoid asyncio errors
@pytest.fixture(autouse=True)
def mock_log():
    """Mock the Log function to avoid asyncio errors in all tests."""
    with patch('utils.logger.Log') as mock:
        yield mock 