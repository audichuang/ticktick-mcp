#!/bin/bash
set -e  # Exit on error

# Docker Hub configuration
DOCKER_USERNAME="audichuang880208"
IMAGE_NAME="ticktick-mcp"
TAG="latest"

# Full image name
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${TAG}"

echo "🚀 Building and pushing TickTick MCP to Docker Hub"
echo "Image: ${FULL_IMAGE_NAME}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    echo "❌ Dockerfile not found. Please run this script from the project root directory."
    exit 1
fi

PLATFORMS=${PLATFORMS:-"linux/amd64,linux/arm64"}

echo "🔐 假設已經透過 docker login 登入 Docker Hub (credsStore=${DOCKER_CONFIG:-$HOME/.docker}/config.json)"
echo "   若推送受到權限拒絕，請先執行： docker login --username ${DOCKER_USERNAME}"

# Step 1: Build and push multi-architecture image
VERSION="3.1.9"
VERSIONED_IMAGE="${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo "📦 Building and pushing Docker image for platforms: ${PLATFORMS}"

docker buildx build \
    --platform "${PLATFORMS}" \
    -t "${FULL_IMAGE_NAME}" \
    -t "${VERSIONED_IMAGE}" \
    . \
    --push

if [ $? -eq 0 ]; then
    echo "✅ Successfully pushed multi-arch images to Docker Hub!"
    echo ""
    echo "🎉 Images available at:"
    echo "   docker pull ${FULL_IMAGE_NAME}"
    echo "   docker pull ${VERSIONED_IMAGE}"
    echo ""
    echo "📝 To use with docker-compose, update your docker-compose.yml:"
    echo "   image: ${FULL_IMAGE_NAME}"
else
    echo "❌ docker buildx build failed!"
    exit 1
fi
