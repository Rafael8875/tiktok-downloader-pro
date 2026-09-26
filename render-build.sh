#!/usr/bin/env bash
# render-build.sh — Build script for Render deployment
set -o errexit

echo "=== TikTok Downloader Pro - Build ==="

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install FFmpeg
echo "Installing FFmpeg..."
apt-get update && apt-get install -y ffmpeg || true

# If apt doesn't work (Render uses a different approach), download static build
if ! command -v ffmpeg &> /dev/null; then
    echo "FFmpeg not found via apt, downloading static build..."
    curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz
    tar xf ffmpeg.tar.xz
    mkdir -p bin
    mv ffmpeg-*-amd64-static/ffmpeg bin/
    mv ffmpeg-*-amd64-static/ffprobe bin/
    chmod +x bin/ffmpeg bin/ffprobe
    rm -rf ffmpeg.tar.xz ffmpeg-*-amd64-static
    echo "FFmpeg installed to bin/"
fi

echo "FFmpeg version:"
ffmpeg -version || bin/ffmpeg -version

# Create required directories
mkdir -p downloads
mkdir -p downloads/temp

echo "=== Build complete ==="
