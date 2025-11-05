#!/bin/bash

# Oread Startup Script
# Starts both inference service and backend server

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"

# Store PIDs
INFERENCE_PID=""
BACKEND_PID=""

# Cleanup function
cleanup() {
    echo ""
    print_status "Shutting down Oread..."
    
    if [ ! -z "$BACKEND_PID" ]; then
        print_status "Stopping backend..."
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$INFERENCE_PID" ]; then
        print_status "Stopping inference service..."
        kill $INFERENCE_PID 2>/dev/null || true
    fi
    
    print_success "Oread stopped"
    exit 0
}

# Set trap for Ctrl+C
trap cleanup INT TERM

# Check if already running
if lsof -Pi :9001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_error "Inference service is already running on port 9001"
    print_error "Run ./stop-oread.sh first, or use a different port"
    exit 1
fi

if lsof -Pi :9000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_error "Backend server is already running on port 9000"
    print_error "Run ./stop-oread.sh first, or use a different port"
    exit 1
fi

clear
echo "========================================="
echo "🚀 Starting Oread"
echo "========================================="
echo ""

# Check if model exists
if [ ! -f "models"/*.gguf ] 2>/dev/null; then
    print_error "No AI model found in models/ directory"
    print_error "Please download a model first:"
    print_error "  Visit: https://huggingface.co/MaziyarPanahi/MN-Violet-Lotus-12B-v1.1-GGUF"
    print_error "  Download a .gguf file and place it in the models/ directory"
    exit 1
fi

# Step 1: Start Inference Service
print_status "Starting inference service..."

cd "$SCRIPT_DIR/inference"

# Check if virtual environment exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Determine which Python to use
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=python
else
    print_error "Python not found. Please install Python 3.8 or higher."
    exit 1
fi

# Start inference in background
$PYTHON_CMD main.py > ../logs/inference.log 2>&1 &
INFERENCE_PID=$!

# Wait for inference to be ready
print_status "Waiting for inference service to initialize..."
RETRIES=0
MAX_RETRIES=60

while [ $RETRIES -lt $MAX_RETRIES ]; do
    if curl -s http://127.0.0.1:9001/health >/dev/null 2>&1; then
        print_success "Inference service ready"
        break
    fi
    
    # Check if process died
    if ! kill -0 $INFERENCE_PID 2>/dev/null; then
        print_error "Inference service failed to start"
        print_error "Check logs/inference.log for details"
        exit 1
    fi
    
    sleep 1
    RETRIES=$((RETRIES + 1))
    
    # Print progress
    if [ $((RETRIES % 5)) -eq 0 ]; then
        print_status "Still waiting... ($RETRIES seconds)"
    fi
done

if [ $RETRIES -eq $MAX_RETRIES ]; then
    print_error "Inference service failed to start within 60 seconds"
    print_error "Check logs/inference.log for details"
    kill $INFERENCE_PID 2>/dev/null || true
    exit 1
fi

# Step 2: Start Backend
print_status "Starting backend server..."

cd "$SCRIPT_DIR/backend"

# Start backend in background
npm start > ../logs/backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to be ready
print_status "Waiting for backend server to initialize..."
RETRIES=0

while [ $RETRIES -lt 30 ]; do
    if curl -k -s https://127.0.0.1:9000 >/dev/null 2>&1; then
        print_success "Backend server ready"
        break
    fi
    
    # Check if process died
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        print_error "Backend server failed to start"
        print_error "Check logs/backend.log for details"
        kill $INFERENCE_PID 2>/dev/null || true
        exit 1
    fi
    
    sleep 1
    RETRIES=$((RETRIES + 1))
done

if [ $RETRIES -eq 30 ]; then
    print_error "Backend server failed to start within 30 seconds"
    print_error "Check logs/backend.log for details"
    kill $INFERENCE_PID 2>/dev/null || true
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Success
echo ""
echo "========================================="
print_success "✅ Oread is now running!"
echo "========================================="
echo ""
echo "🌐 Open your browser to:"
echo "   https://localhost:9000"
echo ""
echo "🔐 Default password: oread"
echo "   (Change it immediately in Settings!)"
echo ""
echo "📝 Logs:"
echo "   Backend:   logs/backend.log"
echo "   Inference: logs/inference.log"
echo ""
echo "⏹️  To stop: Press Ctrl+C or run ./stop-oread.sh"
echo ""

# Try to open browser (platform-specific)
if command -v xdg-open > /dev/null 2>&1; then
    xdg-open https://localhost:9000 >/dev/null 2>&1 &
elif command -v open > /dev/null 2>&1; then
    open https://localhost:9000 >/dev/null 2>&1 &
fi

# Wait indefinitely (until Ctrl+C)
wait
