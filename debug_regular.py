import json
import sys
sys.path.insert(0, 'src')

# Load data  
with open('example-input.json', 'r') as f:
    data = json.loads(f.read().replace('var tumblr_api_read = ', '').rstrip(';'))

# Find a regular post
regular_post = None
for post in data['posts']:
    if post.get('type') == 'regular':
        regular_post = post
        break

if regular_post:
    print(f"Testing regular post {regular_post.get('id')}")
    print(f"Type: {regular_post.get('type')}")
    print(f"Has 'regular-body': {'regular-body' in regular_post}")
    body = regular_post.get('regular-body', '')
    print(f"Body length: {len(body)}")
    print(f"Body preview: {body[:200]}")
    print()
    
    from tumblr_downloader.media_selector import _extract_regular
    media = _extract_regular(regular_post, str(regular_post.get('id')))
    print(f"\nExtracted {len(media)} media items")
    for m in media:
        print(f"  URL: {m['url']}")
        print(f"  Size: {m['width']}x{m['height']}")
        print(f"  Type: {m['type']}")
else:
    print("No regular post found")
