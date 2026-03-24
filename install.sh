#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "🚀 Installing JK-AI Workspace Tools..."

# 1. Sync workspace dependencies
echo "📦 Syncing workspace dependencies..."
uv sync --all-packages

# # 2. Fix potential permission issues in the uv tools directory
# # This addresses the 'Permission denied' error you encountered earlier
# if [ -d "$HOME/.local/share/uv/tools" ]; then
#     echo "🔐 Ensuring correct permissions for uv tools..."
#     sudo chown -R $(whoami) "$HOME/.local/share/uv/tools"
# fi

# 3. Install the main package (includes chat, init, and edit entry points)
echo "🛠 Installing jk-ai-tools package in editable mode..."
uv tool install ./apps/jk-ai-chat --force --editable

# 4. Refresh shell hash to make new commands visible for Tab-completion
hash -r 2>/dev/null || rehash 2>/dev/null

echo "✅ All tools installed successfully!"
echo "💡 You can now run 'jk-ai-chat', 'jk-ai-init', and 'jk-ai-edit' from anywhere."

