"""导出 FastAPI OpenAPI Schema 到 JSON 文件，供 openapi-typescript 使用。

Usage:
    cd apps/api
    PYTHONPATH=src uv run python scripts/generate_openapi.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.main import app

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "packages", "api-types"
)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "openapi.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

openapi_schema = app.openapi()

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(openapi_schema, f, ensure_ascii=False, indent=2)

print(f"✅ OpenAPI schema 已导出到: {OUTPUT_FILE}")
print(f"   接口数量: {len(openapi_schema.get('paths', {}))} 个路径")