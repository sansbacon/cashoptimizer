#!/bin/bash
# Build script for local documentation development

set -e

echo "🔨 Building cash-optimizer documentation..."

# Check if mkdocs is installed
if ! command -v mkdocs &> /dev/null; then
    echo "❌ mkdocs not found. Installing dependencies..."
    pip install -r docs-requirements.txt
fi

# Build documentation
echo "📚 Building with MkDocs..."
mkdocs build -f zensical.yaml -d docs/build

echo ""
echo "✅ Build complete!"
echo ""
echo "📂 Output directory: docs/build"
echo "🌐 To serve locally:"
echo "   mkdocs serve -f zensical.yaml"
echo ""
echo "📖 Open in browser at: http://localhost:8000"
