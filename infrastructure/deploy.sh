#!/bin/bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$PROJECT_ROOT/infrastructure/template.yaml"
CONFIG="$PROJECT_ROOT/infrastructure/samconfig.toml"

echo "Building application..."

sam build \
    --template-file "$TEMPLATE"

echo "Deploying..."

sam deploy \
    --template-file "$TEMPLATE" \
    --config-file "$CONFIG"
