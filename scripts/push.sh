#!/usr/bin/env bash
set -euo pipefail

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-us-east-1}
REPO=ck-agent-dev
TAG=${1:-$(git rev-parse --short HEAD)}
URI="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com" >&2

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --output type=image,oci-mediatypes=false,push=true \
  -t "$URI:$TAG" . >&2

echo "$TAG"