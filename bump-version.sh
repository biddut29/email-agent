#!/bin/bash

# Version Bump Script for Email Agent
# Usage: ./bump-version.sh [major|minor|patch] [backend|frontend|both]

set -e

BACKEND_VERSION_FILE="Backend/__version__.py"
FRONTEND_VERSION_FILE="Frontend/lib/version.ts"

# Get current versions
get_backend_version() {
    if [ -f "$BACKEND_VERSION_FILE" ]; then
        grep '__version__ = "' "$BACKEND_VERSION_FILE" | sed 's/.*__version__ = "\([^"]*\)".*/\1/' || echo "0.0.0"
    else
        echo "0.0.0"
    fi
}

get_frontend_version() {
    if [ -f "$FRONTEND_VERSION_FILE" ]; then
        grep 'FRONTEND_VERSION = "' "$FRONTEND_VERSION_FILE" | sed 's/.*FRONTEND_VERSION = "\([^"]*\)".*/\1/' || echo "0.0.0"
    else
        echo "0.0.0"
    fi
}

# Bump version based on type (major, minor, patch)
bump_version() {
    local version=$1
    local type=$2
    
    IFS='.' read -ra VERSION_PARTS <<< "$version"
    MAJOR=${VERSION_PARTS[0]}
    MINOR=${VERSION_PARTS[1]}
    PATCH=${VERSION_PARTS[2]}
    
    case $type in
        major)
            MAJOR=$((MAJOR + 1))
            MINOR=0
            PATCH=0
            ;;
        minor)
            MINOR=$((MINOR + 1))
            PATCH=0
            ;;
        patch)
            PATCH=$((PATCH + 1))
            ;;
        *)
            echo "Error: Invalid version type. Use: major, minor, or patch"
            exit 1
            ;;
    esac
    
    echo "${MAJOR}.${MINOR}.${PATCH}"
}

# Update backend version
update_backend_version() {
    local new_version=$1
    sed -i.bak "s/__version__ = \".*\"/__version__ = \"$new_version\"/" "$BACKEND_VERSION_FILE"
    rm -f "${BACKEND_VERSION_FILE}.bak"
    echo "✓ Backend version updated to $new_version"
}

# Update frontend version
update_frontend_version() {
    local new_version=$1
    sed -i.bak "s/FRONTEND_VERSION = \".*\"/FRONTEND_VERSION = \"$new_version\"/" "$FRONTEND_VERSION_FILE"
    rm -f "${FRONTEND_VERSION_FILE}.bak"
    echo "✓ Frontend version updated to $new_version"
}

# Main script
VERSION_TYPE=${1:-patch}
TARGET=${2:-both}

if [[ ! "$VERSION_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo "Error: Invalid version type '$VERSION_TYPE'"
    echo "Usage: $0 [major|minor|patch] [backend|frontend|both]"
    exit 1
fi

if [[ ! "$TARGET" =~ ^(backend|frontend|both)$ ]]; then
    echo "Error: Invalid target '$TARGET'"
    echo "Usage: $0 [major|minor|patch] [backend|frontend|both]"
    exit 1
fi

echo "🔄 Bumping version ($VERSION_TYPE)..."

if [ "$TARGET" = "backend" ] || [ "$TARGET" = "both" ]; then
    CURRENT_BE=$(get_backend_version)
    NEW_BE=$(bump_version "$CURRENT_BE" "$VERSION_TYPE")
    update_backend_version "$NEW_BE"
fi

if [ "$TARGET" = "frontend" ] || [ "$TARGET" = "both" ]; then
    CURRENT_FE=$(get_frontend_version)
    NEW_FE=$(bump_version "$CURRENT_FE" "$VERSION_TYPE")
    update_frontend_version "$NEW_FE"
fi

echo ""
echo "✅ Version bump complete!"
echo ""
if [ "$TARGET" = "both" ]; then
    echo "New versions:"
    echo "  Backend:  $(get_backend_version)"
    echo "  Frontend: $(get_frontend_version)"
elif [ "$TARGET" = "backend" ]; then
    echo "New backend version: $(get_backend_version)"
elif [ "$TARGET" = "frontend" ]; then
    echo "New frontend version: $(get_frontend_version)"
fi

