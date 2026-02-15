#!/usr/bin/env python3
"""Check the manifest file created during testing."""

import json
from pathlib import Path

manifest_path = Path("/tmp/tumblr-test-output/manifest.json")

if manifest_path.exists():
    with open(manifest_path) as f:
        data = json.load(f)
    
    print(f"✅ Manifest created successfully")
    print(f"Total posts: {len(data)}")
    
    if data:
        sample_id = list(data.keys())[0]
        sample_post = data[sample_id]
        print(f"\nSample post structure:")
        print(f"  Post ID: {sample_id}")
        print(f"  Keys: {list(sample_post.keys())}")
        print(f"  Media count: {len(sample_post.get('media', []))}")
        print(f"  Post type: {sample_post.get('post_type')}")
else:
    print("❌ Manifest not found")
