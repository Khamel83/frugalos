#!/bin/bash

echo "🚀 Setting up FrugalOS from scratch..."

# Step 1: Install Python 3.11+
echo "📦 Installing Python 3.11..."
brew install python@3.11

# Step 2: Create virtual environment with Python 3.11
echo "🐍 Creating Python 3.11 virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Step 3: Upgrade pip and install FrugalOS
echo "⬆️  Upgrading pip and installing FrugalOS..."
pip install --upgrade pip
pip install -e .

# Step 4: Verify installation
echo "✅ Verifying FrugalOS installation..."
python -c "import frugalos; print('FrugalOS version:', frugalos.__version__)"

# Step 5: Pull required Ollama models
echo "🤖 Pulling required Ollama models..."

# Kill any existing ollama serve to avoid conflicts
pkill -f "ollama serve" 2>/dev/null || true
sleep 2

# Start ollama server in background
ollama serve &
OLLAMA_PID=$!
sleep 5

echo "📥 Pulling qwen2.5-coder:7b (if not already exists)..."
ollama pull qwen2.5-coder:7b

echo "📥 Pulling llama3.1:8b..."
ollama pull llama3.1:8b

# Step 6: Test FrugalOS CLI
echo "🧪 Testing FrugalOS CLI..."
frugal --help

echo "🎯 Testing sample receipt extraction..."
frugal run --project demo --goal "Extract vendor and total from receipts" --context samples/receipt.txt --schema frugalos/schemas/invoice.json --budget-cents 0

# Cleanup
echo "🧹 Cleaning up..."
kill $OLLAMA_PID 2>/dev/null || true

echo "✨ FrugalOS setup complete!"
echo "📝 To use FrugalOS in the future:"
echo "   1. Activate venv: source venv/bin/activate"
echo "   2. Start Ollama: ollama serve &"
echo "   3. Run FrugalOS: frugal --help"