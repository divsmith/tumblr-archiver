#!/usr/bin/env python3
"""Quick test of media extraction with sample data."""

import json
import sys
import logging
sys.path.insert(0, 'src')

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

from tumblr_downloader.media_selector import extract_media_from_post

# Load the sample JSON data
with open('example-input.json', 'r') as f:
    content = f.read()
    # Strip the JSONP wrapper
    json_str = content.replace('var tumblr_api_read = ', '').rstrip(';')
    data = json.loads(json_str)

posts = data.get('posts', [])

print(f"Testing media extraction on {len(posts)} posts\n")
print("=" * 80)

total_media = 0
for i, post in enumerate(posts, 1):  # Test ALL posts now
    post_id = post.get('id', 'unknown')
    post_type = post.get('type', 'unknown')
    
    print(f"\nPost {i}: ID={post_id}, Type={post_type}")
    
    media = extract_media_from_post(post)
    total_media += len(media)
    
    if media:
        print(f"  ✓ Found {len(media)} media item(s):")
        for item in media:
            url_preview = item['url'][:80] + '...' if len(item['url']) > 80 else item['url']
            print(f"    - {item['type']}: {url_preview}")
            print(f"      Dimensions: {item['width']}x{item['height']}")
    else:
        print(f"  ✗ No media found")

print("\n" + "=" * 80)
print(f"\nTotal media extracted: {total_media}")
