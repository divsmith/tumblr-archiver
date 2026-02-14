"""Tests for the Internet Archive Wayback Machine client."""

import re

import pytest
from aioresponses import aioresponses

from tumblr_archiver.archive import Snapshot, WaybackClient
from tumblr_archiver.constants import HTTP_NOT_FOUND, HTTP_OK, WAYBACK_CDX_API_URL
from tumblr_archiver.http_client import AsyncHTTPClient, HTTPError


class TestSnapshot:
    """Tests for the Snapshot dataclass."""
    
    def test_snapshot_datetime_conversion(self):
        """Test conversion of timestamp to datetime."""
        snapshot = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="image/jpeg",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        dt = snapshot.datetime
        assert dt.year == 2023
        assert dt.month == 6
        assert dt.day == 15
        assert dt.hour == 14
        assert dt.minute == 30
        assert dt.second == 22
    
    def test_snapshot_status_conversion(self):
        """Test conversion of statuscode to integer."""
        snapshot = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="image/jpeg",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        assert snapshot.status == 200
        assert isinstance(snapshot.status, int)
    
    def test_snapshot_status_invalid(self):
        """Test handling of invalid status codes."""
        snapshot = Snapshot(
            timestamp="20230615143022",
            statuscode="-",
            mimetype="image/jpeg",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        assert snapshot.status == 0
    
    def test_is_successful_200(self):
        """Test is_successful with 200 status."""
        snapshot = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="image/jpeg",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        assert snapshot.is_successful() is True
    
    def test_is_successful_404(self):
        """Test is_successful with 404 status."""
        snapshot = Snapshot(
            timestamp="20230615143022",
            statuscode="404",
            mimetype="text/html",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        assert snapshot.is_successful() is False
    
    def test_is_successful_302(self):
        """Test is_successful with redirect status."""
        snapshot = Snapshot(
            timestamp="20230615143022",
            statuscode="302",
            mimetype="text/html",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        assert snapshot.is_successful() is False


class TestWaybackClient:
    """Tests for WaybackClient."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test client initialization."""
        async with AsyncHTTPClient() as http_client:
            client = WaybackClient(http_client)
            assert client.http_client is http_client
    
    @pytest.mark.asyncio
    async def test_find_snapshots_success(self):
        """Test successful snapshot retrieval from CDX API."""
        with aioresponses() as m:
            # Mock CDX API response
            cdx_response = [
                ["timestamp", "statuscode", "mimetype", "original"],
                ["20230615143022", "200", "image/jpeg", "https://example.com/image.jpg"],
                ["20230501120000", "200", "image/jpeg", "https://example.com/image.jpg"],
                ["20230301090000", "404", "text/html", "https://example.com/image.jpg"],
            ]
            
            # Match URL with query parameters using regex
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_OK,
                payload=cdx_response
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                snapshots = await client.find_snapshots("https://example.com/image.jpg")
                
                assert len(snapshots) == 3
                
                # Check first snapshot
                assert snapshots[0].timestamp == "20230615143022"
                assert snapshots[0].statuscode == "200"
                assert snapshots[0].mimetype == "image/jpeg"
                assert snapshots[0].original_url == "https://example.com/image.jpg"
                assert "20230615143022id_" in snapshots[0].snapshot_url
                
                # Check last snapshot (404)
                assert snapshots[2].statuscode == "404"
                assert not snapshots[2].is_successful()
    
    @pytest.mark.asyncio
    async def test_find_snapshots_with_date_range(self):
        """Test snapshot search with date range parameters."""
        with aioresponses() as m:
            cdx_response = [
                ["timestamp", "statuscode", "mimetype", "original"],
                ["20230615143022", "200", "image/jpeg", "https://example.com/image.jpg"],
            ]
            
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_OK,
                payload=cdx_response
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                snapshots = await client.find_snapshots(
                    "https://example.com/image.jpg",
                    from_date="20230101",
                    to_date="20231231"
                )
                
                assert len(snapshots) == 1
                assert snapshots[0].timestamp == "20230615143022"
    
    @pytest.mark.asyncio
    async def test_find_snapshots_with_limit(self):
        """Test snapshot search with limit parameter."""
        with aioresponses() as m:
            cdx_response = [
                ["timestamp", "statuscode", "mimetype", "original"],
                ["20230615143022", "200", "image/jpeg", "https://example.com/image.jpg"],
                ["20230501120000", "200", "image/jpeg", "https://example.com/image.jpg"],
            ]
            
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_OK,
                payload=cdx_response
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                snapshots = await client.find_snapshots(
                    "https://example.com/image.jpg",
                    limit=10
                )
                
                assert len(snapshots) == 2
    
    @pytest.mark.asyncio
    async def test_find_snapshots_no_results(self):
        """Test handling when no snapshots are found."""
        with aioresponses() as m:
            # CDX API returns only headers when no results
            cdx_response = [
                ["timestamp", "statuscode", "mimetype", "original"]
            ]
            
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_OK,
                payload=cdx_response
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                snapshots = await client.find_snapshots("https://example.com/missing.jpg")
                
                assert snapshots == []
    
    @pytest.mark.asyncio
    async def test_find_snapshots_empty_response(self):
        """Test handling of empty CDX API response."""
        with aioresponses() as m:
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_OK,
                payload=[]
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                snapshots = await client.find_snapshots("https://example.com/image.jpg")
                
                assert snapshots == []
    
    @pytest.mark.asyncio
    async def test_find_snapshots_api_error(self):
        """Test handling of CDX API errors."""
        with aioresponses() as m:
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_NOT_FOUND
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                
                with pytest.raises(HTTPError):
                    await client.find_snapshots("https://example.com/image.jpg")
    
    @pytest.mark.asyncio
    async def test_find_snapshots_malformed_row(self):
        """Test handling of malformed CDX response rows."""
        with aioresponses() as m:
            cdx_response = [
                ["timestamp", "statuscode", "mimetype", "original"],
                ["20230615143022", "200", "image/jpeg", "https://example.com/image.jpg"],
                ["incomplete", "row"],  # Malformed row
                ["20230501120000", "200", "image/jpeg", "https://example.com/image.jpg"],
            ]
            
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_OK,
                payload=cdx_response
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                snapshots = await client.find_snapshots("https://example.com/image.jpg")
                
                # Should skip malformed row
                assert len(snapshots) == 2
                assert snapshots[0].timestamp == "20230615143022"
                assert snapshots[1].timestamp == "20230501120000"
    
    @pytest.mark.asyncio
    async def test_get_best_snapshot_success(self):
        """Test getting the best snapshot."""
        with aioresponses() as m:
            cdx_response = [
                ["timestamp", "statuscode", "mimetype", "original"],
                ["20230615143022", "200", "image/jpeg", "https://example.com/image_1280.jpg"],
                ["20230501120000", "200", "image/jpeg", "https://example.com/image_500.jpg"],
                ["20230301090000", "404", "text/html", "https://example.com/image.jpg"],
            ]
            
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_OK,
                payload=cdx_response
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                best = await client.get_best_snapshot("https://example.com/image.jpg")
                
                assert best is not None
                # Should prefer higher resolution (_1280 over _500)
                assert best.timestamp == "20230615143022"
                assert "1280" in best.original_url
    
    @pytest.mark.asyncio
    async def test_get_best_snapshot_no_results(self):
        """Test get_best_snapshot when no snapshots found."""
        with aioresponses() as m:
            cdx_response = [
                ["timestamp", "statuscode", "mimetype", "original"]
            ]
            
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_OK,
                payload=cdx_response
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                best = await client.get_best_snapshot("https://example.com/missing.jpg")
                
                assert best is None
    
    @pytest.mark.asyncio
    async def test_get_best_snapshot_all_errors(self):
        """Test get_best_snapshot when all snapshots are errors."""
        with aioresponses() as m:
            cdx_response = [
                ["timestamp", "statuscode", "mimetype", "original"],
                ["20230615143022", "404", "text/html", "https://example.com/image.jpg"],
                ["20230501120000", "500", "text/html", "https://example.com/image.jpg"],
            ]
            
            m.get(
                re.compile(r'https://web\.archive\.org/cdx/search/cdx\?.*'),
                status=HTTP_OK,
                payload=cdx_response
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                best = await client.get_best_snapshot("https://example.com/image.jpg")
                
                assert best is None
    
    @pytest.mark.asyncio
    async def test_download_from_snapshot_success(self):
        """Test successful download from snapshot."""
        with aioresponses() as m:
            snapshot_url = "https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
            image_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # JPEG header
            
            m.get(
                snapshot_url,
                status=HTTP_OK,
                body=image_data
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                content = await client.download_from_snapshot(snapshot_url)
                
                assert content == image_data
    
    @pytest.mark.asyncio
    async def test_download_from_snapshot_error(self):
        """Test download error handling."""
        with aioresponses() as m:
            snapshot_url = "https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
            
            m.get(
                snapshot_url,
                status=HTTP_NOT_FOUND
            )
            
            async with AsyncHTTPClient() as http_client:
                client = WaybackClient(http_client)
                
                with pytest.raises(HTTPError):
                    await client.download_from_snapshot(snapshot_url)
