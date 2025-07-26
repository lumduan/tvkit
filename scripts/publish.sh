#!/bin/bash
set -e

# Load environment variables from .env file
if [ -f .env ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 TVKit Publishing${NC}"
echo "====================="

# Check if we're using uv environment
if command -v uv &> /dev/null; then
    echo "Using uv for Python package management..."
else
    echo "uv not found, using standard Python..."
    # Activate virtual environment if it exists
    if [ -d .venv ]; then
        source .venv/bin/activate
    fi
fi

# Get package info
package_version=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
package_name=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['name'])")

echo -e "${BLUE}📦 Package: ${package_name} v${package_version}${NC}"
echo -e "${YELLOW}⚠️  This will publish to PRODUCTION PyPI!${NC}"
echo -e "${YELLOW}⚠️  The package will be publicly available to everyone!${NC}"
echo ""

# Build the package first
echo -e "${BLUE}🔨 Building package...${NC}"
if command -v uv &> /dev/null; then
    uv pip install build twine
    python3 -m build
else
    python3 -m pip install build twine
    python3 -m build
fi

if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
    echo -e "${RED}❌ Build failed! No files in dist/ directory.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Package built successfully!${NC}"
echo ""
read -p "Are you sure you want to continue? (y/N): " confirm

if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Publishing cancelled.${NC}"
    exit 0
fi

# Upload to Production PyPI
echo -e "${GREEN}📤 Uploading to Production PyPI...${NC}"
if [ -n "$PYPI_TOKEN" ]; then
    echo "Using PYPI_TOKEN from .env file..."
    if command -v uv &> /dev/null; then
        python3 -m twine upload dist/* --username __token__ --password "$PYPI_TOKEN" --verbose
    else
        python3 -m twine upload dist/* --username __token__ --password "$PYPI_TOKEN" --verbose
    fi
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Successfully uploaded to Production PyPI!${NC}"
        echo ""
        echo -e "${BLUE}🎉 Your package is now live!${NC}"
        echo "Package URL: https://pypi.org/project/${package_name}/"
        echo ""
        echo "Users can install it with:"
        echo -e "${GREEN}pip install ${package_name}${NC}"
        echo ""
        echo "Documentation: https://github.com/lumduan/tvkit"
    else
        echo -e "${RED}❌ Upload failed!${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ PYPI_TOKEN not found in .env file!${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 Done!${NC}"
