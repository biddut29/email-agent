# Version Management Guide

## How Version System Works

The Email Agent application uses a simple versioning system to track deployments and ensure changes are reflected after deployment.

### Version Files

1. **Backend Version**: `Backend/__version__.py`
   ```python
   __version__ = "1.0.0"
   ```

2. **Frontend Version**: `Frontend/lib/version.ts`
   ```typescript
   export const FRONTEND_VERSION = "1.0.0";
   ```

### How Versions Are Displayed

- **Frontend version** is always visible in the dashboard header (fetched from `Frontend/lib/version.ts`)
- **Backend version** is fetched from the `/api/health` endpoint and displayed next to the frontend version
- Both versions appear as badges: `FE: v1.0.0` and `BE: v1.0.0`

## How to Update Versions

### Option 1: Manual Update (Simple)

1. **Update Backend Version**:
   ```bash
   # Edit Backend/__version__.py
   __version__ = "1.0.1"  # or "1.1.0" or "2.0.0"
   ```

2. **Update Frontend Version**:
   ```bash
   # Edit Frontend/lib/version.ts
   export const FRONTEND_VERSION = "1.0.1";  # or "1.1.0" or "2.0.0"
   ```

### Option 2: Using the Bump Script (Recommended)

Use the `bump-version.sh` script to automatically increment versions:

```bash
# Bump patch version (1.0.0 -> 1.0.1) for both
./bump-version.sh patch

# Bump minor version (1.0.0 -> 1.1.0) for both
./bump-version.sh minor

# Bump major version (1.0.0 -> 2.0.0) for both
./bump-version.sh major

# Bump only backend
./bump-version.sh patch backend

# Bump only frontend
./bump-version.sh patch frontend
```

## Semantic Versioning

Follow [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):

- **MAJOR** (2.0.0): Breaking changes, incompatible API changes
- **MINOR** (1.1.0): New features, backward compatible
- **PATCH** (1.0.1): Bug fixes, backward compatible

### Examples

- `1.0.0` → `1.0.1` (patch): Fixed a bug
- `1.0.0` → `1.1.0` (minor): Added new feature
- `1.0.0` → `2.0.0` (major): Breaking change

## Workflow for Deployment

1. **Make your code changes**
2. **Bump version**:
   ```bash
   ./bump-version.sh patch  # or minor/major
   ```
3. **Commit and push**:
   ```bash
   git add Backend/__version__.py Frontend/lib/version.ts
   git commit -m "Bump version to 1.0.1"
   git push origin dev
   ```
4. **Deploy** (via GitHub Actions or manually)
5. **Verify** in the dashboard - you should see the new version numbers

## Verifying Versions After Deployment

After deployment, check the dashboard header:
- Frontend version should match `Frontend/lib/version.ts`
- Backend version should match `Backend/__version__.py`

If versions don't match, it means:
- The deployment didn't complete successfully
- The code wasn't updated on the server
- There's a caching issue

## Best Practices

1. **Always bump version before deployment** - This ensures you can verify the deployment worked
2. **Use semantic versioning** - Makes it clear what type of changes were made
3. **Keep versions in sync** - If both frontend and backend change, bump both
4. **Commit version changes separately** - Makes it easier to track version history
5. **Document major changes** - When bumping major version, document breaking changes

## Troubleshooting

### Version not updating in UI?

1. **Check if backend is running**: The backend version comes from the health endpoint
2. **Clear browser cache**: Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
3. **Check deployment logs**: Ensure the new code was deployed
4. **Verify files on server**: Check that version files were updated on the VM

### Versions out of sync?

- Backend and frontend can have different versions
- This is normal if only one part was updated
- Use `./bump-version.sh patch backend` or `./bump-version.sh patch frontend` to update individually

