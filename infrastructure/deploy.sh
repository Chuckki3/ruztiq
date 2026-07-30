#!/bin/bash

set -e

echo "Building application..."

sam build --template-file infrastructure/template.yaml

echo "Deploying..."

sam deploy