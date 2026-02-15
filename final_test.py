#!/usr/bin/env python3
import json
import sys
sys.path.insert(0, 'src')

from tumblr_downloader.media_selector import extract_media_from_post

# Load data
with open('example-input.json') as f:
    data = json.loads(f.read().replace('var tumblr_api_read = ', '').rstrip(';'))

# Count by type
photo = regular = 0
for post in data['posts']:
    media = extract_media_from_post(post)
    if post['type'].lower() == 'photo':
        photo += len(media)
    elif post['type'].lower() == 'regular':
        regular += len(media)

print(f"✓ Photo posts: {photo} media items")
print(f"✓ Regular posts: {regular} media items")
print(f"✓ TOTAL:  {photo + regular} media items")
