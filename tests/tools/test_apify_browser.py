import pytest
from unittest.mock import patch, MagicMock
from app.tools.apify_browser import apify_browser_tool


def test_successful_crawl(mock_settings, mocker):
    """Test successful Apify crawl using mocker"""
    # Mock requests
    mock_post = mocker.patch('app.tools.apify_browser.requests.post')
    mock_get = mocker.patch('app.tools.apify_browser.requests.get')
    
    # Mock the API responses
    mock_post.return_value.json.return_value = {"data": {"id": "run-123"}}
    
    # First call: check run status (SUCCEEDED)
    # Second call: get dataset items
    mock_get.side_effect = [
        MagicMock(json=MagicMock(return_value={
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-123"}
        })),
        MagicMock(json=MagicMock(return_value=[
            {"html": "<html><body>Test content</body></html>"}
        ]))
    ]
    
    result = apify_browser_tool("https://example.com")  # Remove .func
    
    assert "Test content" in result
    assert result == "Test content\n\n"  # html2text conversion


def test_apify_run_failed(mock_settings, mocker):
    """Test when Apify run fails"""
    mock_post = mocker.patch('app.tools.apify_browser.requests.post')
    mock_get = mocker.patch('app.tools.apify_browser.requests.get')
    
    mock_post.return_value.json.return_value = {"data": {"id": "run-123"}}
    mock_get.return_value.json.return_value = {
        "data": {"status": "FAILED"}
    }
    
    result = apify_browser_tool("https://example.com")  # Remove .func
    
    assert "Apify run failed: FAILED" in result


def test_missing_api_token():
    """Test when APIFY_API_TOKEN is not set"""
    with patch('app.tools.apify_browser.settings') as mock_settings:
        mock_settings.APIFY_API_TOKEN = None
        
        with pytest.raises(ValueError, match="APIFY_API_TOKEN is not set"):
            apify_browser_tool("https://example.com")  # Remove .func


def test_no_content_extracted(mock_settings, mocker):
    """Test when no content is extracted from Apify"""
    mock_post = mocker.patch('app.tools.apify_browser.requests.post')
    mock_get = mocker.patch('app.tools.apify_browser.requests.get')
    
    mock_post.return_value.json.return_value = {"data": {"id": "run-123"}}
    
    mock_get.side_effect = [
        MagicMock(json=MagicMock(return_value={
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-123"}
        })),
        MagicMock(json=MagicMock(return_value=[]))  # Empty items
    ]
    
    result = apify_browser_tool("https://example.com")  # Remove .func
    
    assert result == "No content extracted from Apify."


def test_apify_api_error(mock_settings, mocker):
    """Test when Apify API returns an error"""
    mock_post = mocker.patch('app.tools.apify_browser.requests.post')
    mock_post.side_effect = Exception("API Error")
    
    result = apify_browser_tool("https://example.com")  # Remove .func
    
    assert "Apify error: API Error" in result


def test_url_validation(mock_settings, mocker):
    """Test that the tool accepts valid URLs"""
    mock_post = mocker.patch('app.tools.apify_browser.requests.post')
    mock_get = mocker.patch('app.tools.apify_browser.requests.get')
    
    mock_post.return_value.json.return_value = {"data": {"id": "run-123"}}
    mock_get.side_effect = [
        MagicMock(json=MagicMock(return_value={
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-123"}
        })),
        MagicMock(json=MagicMock(return_value=[
            {"html": "<html>test</html>"}
        ]))
    ]
    
    # Test different URL formats
    test_urls = [
        "https://www.kayak.com/flights/ADD-DXB/2025-11-21",
        "http://example.com",
        "https://sub.domain.com/path?query=param"
    ]
    
    for url in test_urls:
        result = apify_browser_tool(url)  # Remove .func
        assert result is not None


def test_large_content_handling(mock_settings, mocker):
    """Test handling of large HTML content"""
    mock_post = mocker.patch('app.tools.apify_browser.requests.post')
    mock_get = mocker.patch('app.tools.apify_browser.requests.get')
    
    # Mock large HTML content
    large_html = "<html><body>" + "x" * 10000 + "</body></html>"
    
    mock_post.return_value.json.return_value = {"data": {"id": "run-123"}}
    mock_get.side_effect = [
        MagicMock(json=MagicMock(return_value={
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-123"}
        })),
        MagicMock(json=MagicMock(return_value=[
            {"html": large_html}
        ]))
    ]
    
    result = apify_browser_tool("https://example.com")  # Remove .func
    
    # Should handle large content without crashing
    assert len(result) > 0
    assert isinstance(result, str)


def test_html_to_text_conversion(mock_settings, mocker):
    """Test that HTML is properly converted to text"""
    mock_post = mocker.patch('app.tools.apify_browser.requests.post')
    mock_get = mocker.patch('app.tools.apify_browser.requests.get')
    
    mock_post.return_value.json.return_value = {"data": {"id": "run-123"}}
    mock_get.side_effect = [
        MagicMock(json=MagicMock(return_value={
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-123"}
        })),
        MagicMock(json=MagicMock(return_value=[
            {"html": "<html><body><h1>Title</h1><p>Paragraph text</p></body></html>"}
        ]))
    ]
    
    result = apify_browser_tool("https://example.com")  # Remove .func
    
    # Check that HTML tags are removed and text is clean
    assert "<html>" not in result
    assert "<body>" not in result
    assert "<h1>" not in result
    assert "<p>" not in result
    assert "Title" in result
    assert "Paragraph text" in result