"""
Data models for Tumblr archiver.

This module defines Pydantic models for type-safe handling of Tumblr posts,
media items, and archival manifests.
"""

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class MediaItem(BaseModel):
    """
    Represents a single media file (image, GIF, or video) from a Tumblr post.
    
    Tracks download status, provenance, and integrity information for each
    media file retrieved from Tumblr or Internet Archive.
    """
    
    post_id: str = Field(
        ...,
        description="Unique identifier for the parent Tumblr post"
    )
    post_url: str = Field(
        ...,
        description="URL to the original Tumblr post"
    )
    timestamp: datetime = Field(
        ...,
        description="When the post was originally published on Tumblr"
    )
    media_type: Literal["image", "gif", "video"] = Field(
        ...,
        description="Type of media file"
    )
    filename: str = Field(
        ...,
        description="Local filename where media is saved"
    )
    byte_size: Optional[int] = Field(
        None,
        description="Size of the downloaded file in bytes",
        ge=0
    )
    checksum: Optional[str] = Field(
        None,
        description="SHA256 hash of the file for integrity verification",
        pattern=r"^[a-f0-9]{64}$"
    )
    original_url: str = Field(
        ...,
        description="Original URL where the media was hosted"
    )
    retrieved_from: Literal["tumblr", "internet_archive"] = Field(
        ...,
        description="Source from which the media was successfully retrieved"
    )
    archive_snapshot_url: Optional[str] = Field(
        None,
        description="Internet Archive snapshot URL if retrieved from archive"
    )
    status: Literal["downloaded", "archived", "missing", "error"] = Field(
        ...,
        description="Current download/retrieval status of the media"
    )
    notes: Optional[str] = Field(
        None,
        description="Additional notes about retrieval issues or special circumstances"
    )
    
    @field_validator("archive_snapshot_url")
    @classmethod
    def validate_archive_url(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure archive_snapshot_url is provided when retrieved from Internet Archive."""
        if info.data.get("retrieved_from") == "internet_archive" and not v:
            raise ValueError(
                "archive_snapshot_url is required when retrieved_from is 'internet_archive'"
            )
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "post_id": "123456789",
                    "post_url": "https://example.tumblr.com/post/123456789",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "media_type": "image",
                    "filename": "123456789_001.jpg",
                    "byte_size": 524288,
                    "checksum": "a" * 64,
                    "original_url": "https://64.media.tumblr.com/abc123/tumblr_xyz.jpg",
                    "retrieved_from": "tumblr",
                    "archive_snapshot_url": None,
                    "status": "downloaded",
                    "notes": None
                }
            ]
        }
    }


class Post(BaseModel):
    """
    Represents a complete Tumblr post with all associated media.
    
    Contains metadata about the post and a collection of all media items
    that were part of the post.
    """
    
    post_id: str = Field(
        ...,
        description="Unique identifier for the Tumblr post"
    )
    post_url: str = Field(
        ...,
        description="URL to the original Tumblr post"
    )
    timestamp: datetime = Field(
        ...,
        description="When the post was originally published"
    )
    is_reblog: bool = Field(
        ...,
        description="Whether this post is a reblog of another post"
    )
    media_items: List[MediaItem] = Field(
        default_factory=list,
        description="List of all media items contained in this post"
    )
    
    @field_validator("media_items")
    @classmethod
    def validate_media_post_ids(cls, v: List[MediaItem], info) -> List[MediaItem]:
        """Ensure all media items reference the correct post_id."""
        post_id = info.data.get("post_id")
        if post_id:
            for item in v:
                if item.post_id != post_id:
                    raise ValueError(
                        f"MediaItem post_id '{item.post_id}' does not match Post post_id '{post_id}'"
                    )
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "post_id": "123456789",
                    "post_url": "https://example.tumblr.com/post/123456789",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "is_reblog": False,
                    "media_items": []
                }
            ]
        }
    }


class Manifest(BaseModel):
    """
    Master manifest tracking all posts and media for a Tumblr blog archive.
    
    Provides a comprehensive record of all archival activity, including
    statistics and methods for managing the archive.
    """
    
    blog_name: str = Field(
        ...,
        description="Name of the Tumblr blog being archived"
    )
    blog_url: str = Field(
        ...,
        description="URL of the Tumblr blog"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this manifest was first created"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this manifest was last modified"
    )
    total_posts: int = Field(
        default=0,
        description="Total number of posts in the archive",
        ge=0
    )
    total_media: int = Field(
        default=0,
        description="Total number of media items in the archive",
        ge=0
    )
    posts: List[Post] = Field(
        default_factory=list,
        description="List of all archived posts"
    )
    
    @model_validator(mode="after")
    def sync_totals(self) -> "Manifest":
        """Automatically sync total_posts and total_media with actual counts."""
        self.total_posts = len(self.posts)
        self.total_media = sum(len(post.media_items) for post in self.posts)
        return self
    
    def to_dict(self) -> Dict:
        """
        Convert manifest to a dictionary for JSON serialization.
        
        Returns:
            Dictionary representation with ISO format timestamps
        """
        return self.model_dump(mode="json")
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Manifest":
        """
        Create a Manifest instance from a dictionary.
        
        Args:
            data: Dictionary containing manifest data
            
        Returns:
            New Manifest instance
            
        Raises:
            ValidationError: If data doesn't match schema
        """
        return cls.model_validate(data)
    
    def add_post(self, post: Post) -> None:
        """
        Add a post to the manifest and update statistics.
        
        Args:
            post: Post instance to add
            
        Raises:
            ValueError: If post with same post_id already exists
        """
        # Check for duplicate post_id
        if any(p.post_id == post.post_id for p in self.posts):
            raise ValueError(f"Post with id '{post.post_id}' already exists in manifest")
        
        self.posts.append(post)
        self.last_updated = datetime.now(timezone.utc)
        
        # Trigger validation to sync totals
        self.__class__.model_validate(self.model_dump())
        self.total_posts = len(self.posts)
        self.total_media = sum(len(p.media_items) for p in self.posts)
    
    def get_media_by_status(
        self,
        status: Literal["downloaded", "archived", "missing", "error"]
    ) -> List[MediaItem]:
        """
        Retrieve all media items with a specific status.
        
        Args:
            status: The status to filter by
            
        Returns:
            List of MediaItem instances matching the status
        """
        media_list = []
        for post in self.posts:
            media_list.extend(
                item for item in post.media_items if item.status == status
            )
        return media_list
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get comprehensive statistics about the archive.
        
        Returns:
            Dictionary with various statistical metrics
        """
        stats = {
            "total_posts": self.total_posts,
            "total_media": self.total_media,
            "reblogs": sum(1 for post in self.posts if post.is_reblog),
            "original_posts": sum(1 for post in self.posts if not post.is_reblog),
        }
        
        # Count by status
        for status in ["downloaded", "archived", "missing", "error"]:
            stats[f"media_{status}"] = len(self.get_media_by_status(status))  # type: ignore
        
        # Count by type
        all_media = [item for post in self.posts for item in post.media_items]
        for media_type in ["image", "gif", "video"]:
            stats[f"{media_type}s"] = sum(
                1 for item in all_media if item.media_type == media_type
            )
        
        # Count by source
        stats["from_tumblr"] = sum(
            1 for item in all_media if item.retrieved_from == "tumblr"
        )
        stats["from_internet_archive"] = sum(
            1 for item in all_media if item.retrieved_from == "internet_archive"
        )
        
        return stats
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "blog_name": "example",
                    "blog_url": "https://example.tumblr.com",
                    "created_at": "2024-01-15T10:00:00Z",
                    "last_updated": "2024-01-15T10:30:00Z",
                    "total_posts": 0,
                    "total_media": 0,
                    "posts": []
                }
            ]
        }
    }
