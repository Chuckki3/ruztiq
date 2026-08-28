#!/bin/bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

TEMPLATE="$PROJECT_ROOT/infrastructure/template.yaml"
CONFIG="$PROJECT_ROOT/infrastructure/samconfig.toml"
BUILT_TEMPLATE="$PROJECT_ROOT/.aws-sam/build/template.yaml"

echo "========================================"
echo "Building application..."
echo "========================================"

sam build \
    --template-file "$TEMPLATE"

echo
echo "========================================"
echo "Deploying built SAM application..."
echo "========================================"

sam deploy \
    --template-file "$BUILT_TEMPLATE" \
    --config-file "$CONFIG"

echo
echo "========================================"
echo "Deployment completed."
echo "========================================"