#!/bin/bash
# Run this on Windows (Git Bash) to create the deployment package
set -e

echo "Building frontend..."
cd frontend
npm run build
cd ..

echo "Creating package..."
mkdir -p dist/mediavault
cp -r backend/* dist/mediavault/backend/
cp -r frontend/dist/* dist/mediavault/frontend/
cp deploy/install.sh dist/mediavault/
chmod +x dist/mediavault/install.sh

echo "Packaging..."
cd dist
tar -czf ../mediavault-linux-x64.tar.gz mediavault/
cd ..
rm -rf dist

echo "Done! Package: mediavault-linux-x64.tar.gz"
echo ""
echo "Deploy to Linux server:"
echo "  1. Upload mediavault-linux-x64.tar.gz to server"
echo "  2. tar -xzf mediavault-linux-x64.tar.gz"
echo "  3. cd mediavault && bash install.sh"
