"""
Manifest generator module for tracking downloaded Tumblr media.

This module provides functionality to create and maintain a JSON manifest
of all downloaded posts and their associated media files.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class ManifestWriter:
    """
    Manages the creation and updating of a JSON manifest file.
    
    The manifest tracks all downloaded posts, their metadata, and media files,
    enabling incremental downloads and verification of existing content.
    """
    
    def __init__(self, output_dir: str):
        """
        Initialize the ManifestWriter.
        
        Args:
            output_dir: Directory where manifest.json will be stored
        """
        self.output_dir = Path(output_dir)
        self.manifest_path = self.output_dir / "manifest.json"
        self.posts: Dict[str, Dict[str, Any]] = {}
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing manifest if present
        self.load_existing()
    
    def load_existing(self) -> Dict[str, Dict[str, Any]]:
        """
        Load existing manifest from disk if present.
        
        Returns:
            Dictionary of posts keyed by post_id, empty dict if no manifest exists
            
        Raises:
            IOError: If manifest exists but cannot be read
            json.JSONDecodeError: If manifest contains invalid JSON
        """
        if not self.manifest_path.exists():
            return {}
        
        try:
            with open(self.manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Convert list format to dict keyed by post_id for easier updates
            if isinstance(data, list):
                self.posts = {post['post_id']: post for post in data}
            elif isinstance(data, dict):
                self.posts = data
            else:
                raise ValueError(f"Unexpected manifest format: {type(data)}")
                
            return self.posts
            
        except (IOError, OSError) as e:
            raise IOError(f"Failed to read manifest from {self.manifest_path}: {e}")
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in manifest {self.manifest_path}: {e.msg}",
                e.doc,
                e.pos
            )
    
    def add_post(self, post_data: dict, media_results: List[dict]) -> None:
        """
        Add or update a post entry in the manifest.
        
        Args:
            post_data: Dictionary containing post metadata with keys:
                - post_id: Unique post identifier
                - post_url: URL to the post
                - timestamp: ISO format timestamp
                - tags: List of tags
            media_results: List of dictionaries containing media download results:
                - media_sources: List of all available URLs for this media
                - chosen_url: URL that was actually downloaded
                - downloaded_filename: Name of the saved file
                - width: Image/video width in pixels
                - height: Image/video height in pixels
                - bytes: File size in bytes
                - type: Media type (photo, video, etc.)
                - status: Download status (success, failed, skipped)
        """
        post_id = str(post_data.get('post_id', ''))
        
        if not post_id:
            raise ValueError("post_data must contain a valid 'post_id'")
        
        # Create post entry
        post_entry = {
            'post_id': post_id,
            'post_url': post_data.get('post_url', ''),
            'timestamp': post_data.get('timestamp', datetime.utcnow().isoformat()),
            'tags': post_data.get('tags', []),
            'media': []
        }
        
        # Add media entries
        for media in media_results:
            media_entry = {
                'media_sources': media.get('media_sources', []),
                'chosen_url': media.get('chosen_url', ''),
                'downloaded_filename': media.get('downloaded_filename', ''),
                'width': media.get('width'),
                'height': media.get('height'),
                'bytes': media.get('bytes'),
                'type': media.get('type', 'photo'),
                'status': media.get('status', 'unknown')
            }
            post_entry['media'].append(media_entry)
        
        # Add or update post in manifest
        self.posts[post_id] = post_entry
    
    def save(self) -> None:
        """
        Write manifest to disk using atomic write operation.
        
        Uses a temporary file and rename to ensure atomicity and prevent
        corruption if the write operation is interrupted.
        
        Raises:
            IOError: If the manifest cannot be written to disk
        """
        try:
            # Convert dict to sorted list for consistent output
            posts_list = [self.posts[post_id] for post_id in sorted(self.posts.keys())]
            
            # Create temporary file in the same directory for atomic rename
            fd, temp_path = tempfile.mkstemp(
                dir=self.output_dir,
                prefix='.manifest_',
                suffix='.tmp'
            )
            
            try:
                # Write pretty-printed JSON to temp file
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(
                        posts_list,
                        f,
                        indent=2,
                        ensure_ascii=False,
                        sort_keys=True
                    )
                    f.write('\n')  # Add trailing newline
                
                # Atomic rename
                os.replace(temp_path, self.manifest_path)
                
            except Exception as e:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise IOError(f"Failed to write manifest: {e}")
                
        except Exception as e:
            raise IOError(f"Failed to save manifest to {self.manifest_path}: {e}")
    
    def get_post(self, post_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific post entry from the manifest.
        
        Args:
            post_id: The post ID to retrieve
            
        Returns:
            Post dictionary if found, None otherwise
        """
        return self.posts.get(str(post_id))
    
    def has_post(self, post_id: str) -> bool:
        """
        Check if a post exists in the manifest.
        
        Args:
            post_id: The post ID to check
            
        Returns:
            True if post exists in manifest, False otherwise
        """
        return str(post_id) in self.posts
    
    def get_all_posts(self) -> List[Dict[str, Any]]:
        """
        Get all posts from the manifest.
        
        Returns:
            List of all post dictionaries, sorted by post_id
        """
        return [self.posts[post_id] for post_id in sorted(self.posts.keys())]
    
    def __len__(self) -> int:
        """Return the number of posts in the manifest."""
        return len(self.posts)
    
    def __repr__(self) -> str:
        """Return string representation of the ManifestWriter."""
        return f"ManifestWriter(output_dir='{self.output_dir}', posts={len(self.posts)})"
