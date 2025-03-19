import pytest
import time
from utils.depth_cache import DepthCache
from unittest.mock import patch

def test_depth_cache_initialization():
    """Test DepthCache initialization"""
    # Test with default cache time
    cache = DepthCache()
    assert cache.cache_time == 100.0
    assert cache.cache == {}
    
    # Test with custom cache time
    custom_cache = DepthCache(cache_time=50.0)
    assert custom_cache.cache_time == 50.0
    assert custom_cache.cache == {}

def test_depth_cache_set_and_get():
    """Test setting and getting values from the cache"""
    cache = DepthCache(cache_time=10.0)
    
    # Test data
    exchange = "MEXC"
    coin = "BTC"
    depth_data = {
        "asks": [(50000, 1.0), (50100, 2.0)],
        "bids": [(49900, 1.0), (49800, 2.0)]
    }
    
    # Set data in cache
    cache.set(exchange, coin, depth_data)
    
    # Get data from cache
    cached_data = cache.get(exchange, coin)
    
    # Verify data
    assert cached_data is not None
    assert cached_data == depth_data
    assert cached_data["asks"] == depth_data["asks"]
    assert cached_data["bids"] == depth_data["bids"]

def test_depth_cache_expiration():
    """Test cache expiration"""
    # Create cache with very short expiration time
    cache = DepthCache(cache_time=0.1)  # 100ms
    
    # Set data in cache
    exchange = "MEXC"
    coin = "BTC"
    depth_data = {
        "asks": [(50000, 1.0)],
        "bids": [(49900, 1.0)]
    }
    cache.set(exchange, coin, depth_data)
    
    # Verify data is in cache
    assert cache.get(exchange, coin) == depth_data
    
    # Wait for cache to expire
    time.sleep(0.2)  # 200ms
    
    # Verify data is no longer in cache
    assert cache.get(exchange, coin) is None
    
    # Verify key is removed from cache dictionary
    assert (exchange, coin) not in cache.cache

def test_depth_cache_update():
    """Test updating cache values"""
    cache = DepthCache(cache_time=10.0)
    
    # Test data
    exchange = "MEXC"
    coin = "BTC"
    depth_data1 = {
        "asks": [(50000, 1.0)],
        "bids": [(49900, 1.0)]
    }
    depth_data2 = {
        "asks": [(50100, 2.0)],
        "bids": [(49800, 2.0)]
    }
    
    # Set initial data
    cache.set(exchange, coin, depth_data1)
    assert cache.get(exchange, coin) == depth_data1
    
    # Update data
    cache.set(exchange, coin, depth_data2)
    assert cache.get(exchange, coin) == depth_data2

def test_depth_cache_multiple_entries():
    """Test cache with multiple entries"""
    cache = DepthCache(cache_time=10.0)
    
    # Set multiple entries
    entries = [
        ("MEXC", "BTC", {"asks": [(50000, 1.0)], "bids": [(49900, 1.0)]}),
        ("MEXC", "ETH", {"asks": [(3000, 1.0)], "bids": [(2900, 1.0)]}),
        ("HTX", "BTC", {"asks": [(50100, 1.0)], "bids": [(49800, 1.0)]}),
        ("HTX", "ETH", {"asks": [(3100, 1.0)], "bids": [(2800, 1.0)]})
    ]
    
    for exchange, coin, data in entries:
        cache.set(exchange, coin, data)
    
    # Verify all entries
    for exchange, coin, data in entries:
        assert cache.get(exchange, coin) == data
    
    # Verify cache size
    assert len(cache.cache) == len(entries)

def test_depth_cache_clear():
    """Test clearing the cache"""
    cache = DepthCache(cache_time=10.0)
    
    # Set multiple entries
    entries = [
        ("MEXC", "BTC", {"asks": [(50000, 1.0)], "bids": [(49900, 1.0)]}),
        ("HTX", "ETH", {"asks": [(3100, 1.0)], "bids": [(2800, 1.0)]})
    ]
    
    for exchange, coin, data in entries:
        cache.set(exchange, coin, data)
    
    # Verify entries are in cache
    assert len(cache.cache) == len(entries)
    
    # Clear cache
    cache.clear()
    
    # Verify cache is empty
    assert len(cache.cache) == 0
    
    # Verify all entries are gone
    for exchange, coin, _ in entries:
        assert cache.get(exchange, coin) is None

def test_depth_cache_nonexistent_key():
    """Test getting a nonexistent key from the cache"""
    cache = DepthCache(cache_time=10.0)
    
    # Try to get data for a key that doesn't exist
    data = cache.get("NONEXISTENT", "COIN")
    
    # Verify result is None
    assert data is None

def test_depth_cache_with_different_cache_times():
    """Test cache with different cache times"""
    # Test with very long cache time
    long_cache = DepthCache(cache_time=3600.0)  # 1 hour
    long_cache.set("MEXC", "BTC", {"asks": [(50000, 1.0)], "bids": [(49900, 1.0)]})
    assert long_cache.get("MEXC", "BTC") is not None
    
    # Test with zero cache time (should expire immediately)
    # We need to patch the time.time() function to make this test reliable
    with patch('time.time') as mock_time:
        # Set up the mock to return increasing timestamps
        mock_time.side_effect = [100.0, 100.1]  # First call for set, second for get
        
        zero_cache = DepthCache(cache_time=0.0)
        zero_cache.set("MEXC", "BTC", {"asks": [(50000, 1.0)], "bids": [(49900, 1.0)]})
        assert zero_cache.get("MEXC", "BTC") is None
    
    # Test with negative cache time (should be treated as zero)
    with patch('time.time') as mock_time:
        # Set up the mock to return increasing timestamps
        mock_time.side_effect = [100.0, 100.1]  # First call for set, second for get
        
        neg_cache = DepthCache(cache_time=-10.0)
        neg_cache.set("MEXC", "BTC", {"asks": [(50000, 1.0)], "bids": [(49900, 1.0)]})
        assert neg_cache.get("MEXC", "BTC") is None 