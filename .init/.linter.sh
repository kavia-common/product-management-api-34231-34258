#!/bin/bash
cd /home/kavia/workspace/code-generation/product-management-api-34231-34258/products_api_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

