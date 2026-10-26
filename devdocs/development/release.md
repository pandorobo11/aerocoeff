# Release

Releases are published as GitHub Releases with the wheel and sdist attached.
PyPI release is out of scope.

## Steps

1. Open a pull request that sets `[project] version` in `pyproject.toml` to the
   new version, and merge it after `CI gate` passes.
2. Tag the merged commit on `main` and push the tag:

   ```bash
   git fetch origin main
   git tag v0.1.0 origin/main
   git push origin v0.1.0
   ```

3. The `Release` workflow then:
   - rejects the tag unless it equals `v` + the project version and points to a
     commit on `main`;
   - runs `scripts/check.py` (standard) and installs the built wheel into a
     clean environment;
   - creates the GitHub Release with generated notes and the `dist/` files.
     Versions ending in `aN`, `bN`, `rcN`, or `devN` are marked as prereleases.

If validation fails, no release is created. Fix the cause on `main` through a
pull request, delete the tag, and tag again.

## Installing a release

```bash
uv add "aerocoeff @ git+https://github.com/pandorobo11/aerocoeff@v0.1.0"
```

The wheel attached to the release can also be installed directly with
`uv pip install <wheel URL>`.
