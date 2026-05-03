#!/bin/bash
#
# bump-version.sh — semver bump + release-commit + annotated git tag.
#
# Reads the current version from the top-level VERSION file, computes the new
# version from the requested subcommand, writes it back to VERSION, keeps
# pyproject.toml's [project].version in sync, then creates a release commit
# and an annotated git tag `vX.Y.Z`.
#
# Does NOT push — you run `git push origin HEAD && git push --tags` yourself
# after verifying the tag.
#
# Usage:
#   scripts/bump-version.sh major
#   scripts/bump-version.sh minor
#   scripts/bump-version.sh patch
#   scripts/bump-version.sh set 1.2.3
#   scripts/bump-version.sh patch --no-tag
#   scripts/bump-version.sh patch --no-commit --no-tag   # files only

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
VERSION_FILE="$REPO_ROOT/VERSION"
PYPROJECT="$REPO_ROOT/pyproject.toml"

print_help() {
    cat <<EOF
Usage: $0 <major|minor|patch|set X.Y.Z> [--no-commit] [--no-tag] [--help]

Bumps the nexus-ai-engine version. Reads the current version from:
    $VERSION_FILE

Writes the new version to VERSION and updates the [project].version line in:
    $PYPROJECT

Then (unless skipped): git add + commit both files, and create an annotated
tag vX.Y.Z. Never pushes.

Subcommands:
  major        X.Y.Z -> (X+1).0.0
  minor        X.Y.Z -> X.(Y+1).0
  patch        X.Y.Z -> X.Y.(Z+1)
  set X.Y.Z    Bump to the explicit version X.Y.Z

Flags:
  --no-commit   Update the files only; do not git-add, commit, or tag.
  --no-tag      Commit the changes but do not create the annotated tag.
  --help, -h    Show this help and exit.

Safety:
  - Refuses to run if the working tree has uncommitted changes (so the
    release commit contains only VERSION + pyproject.toml).
  - Refuses to bump to the same version as the current one.
  - Refuses to create a tag that already exists.
EOF
}

# ── Parse args ──────────────────────────────────────────────────────────
SUBCMD=""
EXPLICIT_VERSION=""
NO_COMMIT=false
NO_TAG=false

while [ $# -gt 0 ]; do
    case "$1" in
        major|minor|patch)
            if [ -n "$SUBCMD" ]; then echo "❌ Multiple subcommands given."; exit 1; fi
            SUBCMD="$1"; shift ;;
        set)
            if [ -n "$SUBCMD" ]; then echo "❌ Multiple subcommands given."; exit 1; fi
            SUBCMD="set"
            if [ $# -lt 2 ]; then
                echo "❌ 'set' requires an explicit version (e.g. 'set 1.2.3')."
                exit 1
            fi
            EXPLICIT_VERSION="$2"
            shift 2 ;;
        --no-commit) NO_COMMIT=true; shift ;;
        --no-tag)    NO_TAG=true; shift ;;
        --help|-h)   print_help; exit 0 ;;
        *) echo "❌ Unknown argument: $1"; echo ""; print_help; exit 1 ;;
    esac
done

if [ -z "$SUBCMD" ]; then
    echo "❌ No subcommand given."
    echo ""
    print_help
    exit 1
fi

# ── Read + validate current version ──────────────────────────────────────
if [ ! -f "$VERSION_FILE" ]; then
    echo "❌ VERSION file not found at $VERSION_FILE"
    exit 1
fi

CURRENT="$(tr -d '[:space:]' < "$VERSION_FILE")"
SEMVER_RE='^[0-9]+\.[0-9]+\.[0-9]+$'

if ! [[ "$CURRENT" =~ $SEMVER_RE ]]; then
    echo "❌ Current version '$CURRENT' in $VERSION_FILE is not strict semver X.Y.Z."
    echo "   Fix the VERSION file by hand and re-run."
    exit 1
fi

IFS='.' read -r MAJ MIN PAT <<< "$CURRENT"

# ── Compute new version ──────────────────────────────────────────────────
case "$SUBCMD" in
    major) NEW_MAJ=$((MAJ + 1)); NEW_MIN=0;             NEW_PAT=0 ;;
    minor) NEW_MAJ=$MAJ;         NEW_MIN=$((MIN + 1));  NEW_PAT=0 ;;
    patch) NEW_MAJ=$MAJ;         NEW_MIN=$MIN;          NEW_PAT=$((PAT + 1)) ;;
    set)
        if ! [[ "$EXPLICIT_VERSION" =~ $SEMVER_RE ]]; then
            echo "❌ 'set' argument '$EXPLICIT_VERSION' is not strict semver X.Y.Z."
            exit 1
        fi
        IFS='.' read -r NEW_MAJ NEW_MIN NEW_PAT <<< "$EXPLICIT_VERSION"
        ;;
esac

NEW="$NEW_MAJ.$NEW_MIN.$NEW_PAT"
TAG="v$NEW"

if [ "$NEW" = "$CURRENT" ]; then
    echo "❌ New version ($NEW) is the same as current ($CURRENT). Nothing to do."
    exit 1
fi

# ── Safety gates ─────────────────────────────────────────────────────────
if [ "$NO_COMMIT" != "true" ]; then
    if ! git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
        echo "❌ $REPO_ROOT is not a git repository."
        exit 1
    fi
    # Refuse to run when the tree is dirty, so the release commit only
    # contains VERSION + pyproject.toml.
    if ! git -C "$REPO_ROOT" diff-index --quiet HEAD -- 2>/dev/null; then
        echo "❌ Working tree has uncommitted changes. Commit or stash them first,"
        echo "   or pass --no-commit to update the files only."
        git -C "$REPO_ROOT" status --short
        exit 1
    fi
fi

if [ "$NO_TAG" != "true" ] && [ "$NO_COMMIT" != "true" ]; then
    if git -C "$REPO_ROOT" rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
        echo "❌ Git tag $TAG already exists. Pick a different version."
        exit 1
    fi
fi

echo "🔖 Bumping version: $CURRENT -> $NEW"

# ── Update VERSION ───────────────────────────────────────────────────────
printf '%s\n' "$NEW" > "$VERSION_FILE"
echo "   ✅ Wrote $VERSION_FILE"

# ── Update pyproject.toml's [project].version ────────────────────────────
# Scope the replacement to the [project] section to avoid clobbering a
# 'version = "..."' line in some other table (e.g. [tool.foo]).
if [ -f "$PYPROJECT" ]; then
    tmp="$PYPROJECT.bump.tmp"
    awk -v new="$NEW" '
        BEGIN { in_project = 0; replaced = 0 }
        /^\[/ {
            in_project = ($0 == "[project]")
        }
        in_project && !replaced && /^version[[:space:]]*=[[:space:]]*".*"[[:space:]]*$/ {
            sub(/=[[:space:]]*".*"/, "= \"" new "\"")
            replaced = 1
        }
        { print }
        END {
            if (!replaced) {
                # Report via stderr; caller decides whether to abort.
                print "WARN: no [project].version line found" > "/dev/stderr"
                exit 2
            }
        }
    ' "$PYPROJECT" > "$tmp"
    awk_rc=$?
    if [ "$awk_rc" -eq 0 ]; then
        mv "$tmp" "$PYPROJECT"
        echo "   ✅ Updated [project].version in $PYPROJECT"
    else
        rm -f "$tmp"
        echo "   ⚠️  Skipped $PYPROJECT (no [project].version line found)."
    fi
else
    echo "   ⚠️  $PYPROJECT not found; skipping pyproject sync."
fi

# ── git commit + tag ─────────────────────────────────────────────────────
if [ "$NO_COMMIT" = "true" ]; then
    echo "⏭️   Skipping git commit + tag (--no-commit)"
    echo ""
    echo "🎯 Files updated. Current VERSION: $NEW"
    exit 0
fi

# Only add pyproject.toml if it actually changed (it might have been
# skipped above). `git diff --quiet` returns 1 when there's a diff.
ADD_ARGS=( "$VERSION_FILE" )
if git -C "$REPO_ROOT" diff --quiet -- "$PYPROJECT" 2>/dev/null; then
    :
else
    ADD_ARGS+=( "$PYPROJECT" )
fi

git -C "$REPO_ROOT" add -- "${ADD_ARGS[@]}"
git -C "$REPO_ROOT" commit -m "chore(release): bump version to $NEW"
echo "   ✅ Committed release bump"

if [ "$NO_TAG" = "true" ]; then
    echo "⏭️   Skipping git tag (--no-tag)"
else
    git -C "$REPO_ROOT" tag -a "$TAG" -m "Release $TAG"
    echo "   ✅ Tagged $TAG"
fi

echo ""
echo "🎯 Release bump complete."
echo ""
echo "   Current version: $NEW"
echo ""
echo "   Next steps (push manually when ready):"
echo "     git push origin HEAD"
if [ "$NO_TAG" != "true" ]; then
    echo "     git push origin $TAG"
fi
