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

# Step 1: Build the image
echo "📦 Building Docker image..."
docker build -t ${IMAGE_NAME}:${TAG} .

if [ $? -ne 0 ]; then
    echo "❌ Docker build failed!"
    exit 1
fi

# Step 2: Tag the image for Docker Hub
echo "🏷️  Tagging image for Docker Hub..."
docker tag ${IMAGE_NAME}:${TAG} ${FULL_IMAGE_NAME}

# Step 3: Login to Docker Hub
echo "🔐 Please login to Docker Hub:"
docker login --username ${DOCKER_USERNAME}

if [ $? -ne 0 ]; then
    echo "❌ Docker login failed!"
    exit 1
fi

# Step 4: Push to Docker Hub
echo "📤 Pushing image to Docker Hub..."
docker push ${FULL_IMAGE_NAME}

if [ $? -eq 0 ]; then
    echo "✅ Successfully pushed to Docker Hub!"
    echo ""
    echo "🎉 Your image is now available at:"
    echo "   docker pull ${FULL_IMAGE_NAME}"
    echo ""
    echo "📝 To use with docker-compose, update your docker-compose.yml:"
    echo "   image: ${FULL_IMAGE_NAME}"
else
    echo "❌ Docker push failed!"
    exit 1
fi

# Optional: Also create and push a versioned tag
VERSION="1.0.0"
VERSIONED_IMAGE="${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo ""
echo "📦 Creating versioned tag ${VERSION}..."
docker tag ${IMAGE_NAME}:${TAG} ${VERSIONED_IMAGE}
docker push ${VERSIONED_IMAGE}

echo "✅ Also pushed version tag: ${VERSIONED_IMAGE}"