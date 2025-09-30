#!/bin/bash
set -e

# Docker Hub configuration
DOCKER_USERNAME="audichuang880208"
IMAGE_NAME="ticktick-mcp"
TAG="latest"
VERSION="3.1.8"  # Fixed ICS sync modifiedTime KeyError bug

# Full image names
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${TAG}"
VERSIONED_IMAGE="${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo "🚀 Pushing TickTick MCP to Docker Hub"
echo "Image: ${FULL_IMAGE_NAME}"
echo ""

# Check if already logged in to Docker Hub
if ! docker info 2>/dev/null | grep -q "Username: ${DOCKER_USERNAME}"; then
    echo "🔐 Please login to Docker Hub first:"
    echo "   docker login --username ${DOCKER_USERNAME}"
    echo ""
    echo "After logging in, run this script again."
    exit 1
fi

# Tag the images
echo "🏷️  Tagging images..."
docker tag ${IMAGE_NAME}:${TAG} ${FULL_IMAGE_NAME}
docker tag ${IMAGE_NAME}:${TAG} ${VERSIONED_IMAGE}

# Push latest tag
echo "📤 Pushing ${FULL_IMAGE_NAME}..."
docker push ${FULL_IMAGE_NAME}

# Push version tag
echo "📤 Pushing ${VERSIONED_IMAGE}..."
docker push ${VERSIONED_IMAGE}

echo ""
echo "✅ Successfully pushed to Docker Hub!"
echo ""
echo "🎉 Your images are now available at:"
echo "   docker pull ${FULL_IMAGE_NAME}"
echo "   docker pull ${VERSIONED_IMAGE}"
echo ""
echo "📝 Users can now use docker-compose with:"
echo "   image: ${FULL_IMAGE_NAME}"