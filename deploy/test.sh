#!/bin/bash

# nexus-ai-engine — in-pod test runner + report publisher.
#
# Runs every configured test tier inside the already-deployed nexus-ai-engine
# pod via `kubectl exec`. When UPLOAD_TO_S3=true (from deploy/.env.local):
#   - pulls per-tier JSON reports off the pod,
#   - renders enhanced HTML reports on the host using
#     tests/report_generators/, and
#   - uploads each report plus a dashboard index.html to S3 and invalidates
#     CloudFront so the latest results are visible at the configured domain.
#
# Does NOT provision resources, build the image, push to ECR, or apply K8s
# manifests — run ./deploy.sh first (or use the ./deploy-and-test.sh wrapper).
#
# Prerequisites (same as deploy.sh):
#   - aws CLI logged in
#   - kubectl context pointing at the right cluster
#   - ./deploy.sh must have already rolled out a pod matching
#     label app.kubernetes.io/name=nexus-ai-engine

set -euo pipefail

# ── Directory dance ─────────────────────────────────────────────────────
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ORIGINAL_DIR="$(pwd)"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
TMP_DIR="$(mktemp -d -t ai-engine-test-XXXXXX)"

cleanup_tmp() {
    rm -rf "$TMP_DIR"
    cd "$ORIGINAL_DIR"
}
trap cleanup_tmp EXIT

# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

load_env_files
set_defaults

DEFAULT_TIERS="unit integration contract property e2e journeys bdd endurance"
TIERS=""

# ── Argument parsing ────────────────────────────────────────────────────
print_help() {
    cat <<EOF
Usage: $0 [OPTIONS]

Run in-pod tests against an already-deployed nexus-ai-engine pod, generate
enhanced HTML reports, and (when UPLOAD_TO_S3=true in deploy/.env.local)
upload them to S3 + invalidate CloudFront.

Options:
  --env ENV                Target environment (default: dev)
  --region REGION          AWS region (default: \$AWS_REGION or us-east-1)
  --profile NAME           AWS CLI profile (default: \$AWS_PROFILE from .env.local or 'default')
  --cluster NAME           EKS cluster (default: from kubectl current-context)
  --namespace NS           K8s namespace (default: ai-engine)
  --ecr-registry URI       ECR registry URI (shown in summary only)
  --image-tag TAG          Image tag (shown in summary only)
  --tests LIST             Comma- or space-separated test tiers
                           (default: $DEFAULT_TIERS)
                           Use 'none' to skip the in-pod test phase entirely.
  --skip-tests             Same as --tests=none
  --dry-run                Print what would be done; make no changes
  --help

Examples:
  $0 --env dev
  $0 --env stage --tests unit,e2e
  $0 --env dev --skip-tests         # upload path is also skipped
EOF
}

# test.sh silently accepts (and discards) the deploy-only flags so the
# deploy-and-test.sh wrapper can pass a shared argv through both scripts
# without each complaining about the other's options.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)            ENV="$2"; shift 2 ;;
        --region)         REGION="$2"; shift 2 ;;
        --profile)        AWS_PROFILE="$2"; shift 2 ;;
        --cluster)        CLUSTER_NAME="$2"; shift 2 ;;
        --namespace)      NAMESPACE="$2"; shift 2 ;;
        --ecr-registry)   ECR_REGISTRY="$2"; shift 2 ;;
        --image-tag)      IMAGE_TAG="$2"; shift 2 ;;
        --tests)          TIERS="$2"; shift 2 ;;
        --skip-tests)     TIERS="none"; shift ;;
        --dry-run)        DRY_RUN=true; shift ;;
        --help|-h)        print_help; exit 0 ;;
        # Deploy-only flags (ignored here; deploy.sh handles them).
        --skip-provision) shift ;;
        --skip-build)     shift ;;
        --skip-push)      shift ;;
        --skip-apply)     shift ;;
        --cleanup)        shift ;;
        --cleanup-aws)    shift ;;
        *) echo "Unknown parameter: $1"; echo "Run '$0 --help' for usage."; exit 1 ;;
    esac
done

# Normalize TIERS (support comma- or space-separated)
if [ -z "$TIERS" ]; then
    TIERS="$DEFAULT_TIERS"
fi
TIERS="${TIERS//,/ }"

# ── Prereq checks ───────────────────────────────────────────────────────
echo "🔍 Verifying prerequisites ..."
require_cmd aws
require_cmd kubectl

setup_aws_context
derive_vars
print_common_banner
echo "   Test tiers:     $TIERS"
print_dry_run_note

# ────────────────────────────────────────────────────────────────────────
# 1. In-pod tests
# ────────────────────────────────────────────────────────────────────────
declare -A RESULTS
declare -A DURATIONS
TESTS_FAILED=0
TESTS_TOTAL=0
TESTS_NOTESTS=0

if [ "$TIERS" = "none" ]; then
    echo "⏭️   Skipping in-pod tests (--skip-tests / --tests=none)"
else
    echo "🧪 Running in-pod tests"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    POD=""
    if [ "$DRY_RUN" != "true" ]; then
        POD=$(kubectl -n "$NAMESPACE" get pod -l app.kubernetes.io/name=nexus-ai-engine \
              -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
        if [ -z "$POD" ]; then
            echo "❌ No nexus-ai-engine pod found in namespace $NAMESPACE."
            echo "   Run ./deploy.sh first."
            exit 1
        fi
        echo "   Target pod: $POD"
    fi
    echo ""

    mkdir -p "$REPO_ROOT/reports"

    # When UPLOAD_TO_S3=true we need per-tier JSON reports to feed the
    # report generators on the host. In that mode we bypass `make test-<tier>`
    # and invoke pytest / behave directly inside the pod with the right
    # --json-report / --format json.pretty flags. Pass/fail semantics remain
    # identical: we rely on the tool's exit code. When UPLOAD_TO_S3 is not
    # enabled we keep the original `make test-<tier>` path unchanged.
    UPLOAD_ON="${UPLOAD_TO_S3:-false}"

    # Map tier -> in-pod command. All commands write JSON (and, for pytest
    # tiers, also self-contained HTML) under /app/reports/ so we can
    # kubectl cp them out regardless of outcome.
    pod_test_cmd() {
        local tier="$1"
        case "$tier" in
            bdd)
                # Keep the behave-html-formatter output (for the existing
                # `kubectl cp bdd.html` step), AND emit json.pretty so the
                # BDD report generator can consume it.
                #
                # IMPORTANT: behave pairs -f and -o POSITIONALLY — the Nth
                # -f writes to the Nth -o, or to stdout if no matching -o
                # exists. We therefore provide exactly 2 -f and 2 -o (no
                # `-f pretty` — it would consume /app/reports/bdd.html and
                # push HTMLFormatter into bdd.json / json.pretty into
                # stdout, which broke the enhanced report generator).
                echo "mkdir -p /app/reports && \
behave tests/bdd/features \
    -f behave_html_formatter:HTMLFormatter -o /app/reports/bdd.html \
    -f json.pretty -o /app/reports/bdd.json"
                ;;
            endurance)
                echo "mkdir -p /app/reports && \
pytest tests/${tier} -q -m 'not heavy' \
    --json-report --json-report-file=/app/reports/${tier}.json \
    --html=/app/reports/${tier}.html --self-contained-html"
                ;;
            property)
                echo "mkdir -p /app/reports && \
pytest tests/${tier} -q --hypothesis-show-statistics \
    --json-report --json-report-file=/app/reports/${tier}.json \
    --html=/app/reports/${tier}.html --self-contained-html"
                ;;
            unit|integration|contract|e2e|journeys)
                echo "mkdir -p /app/reports && \
pytest tests/${tier} -q \
    --json-report --json-report-file=/app/reports/${tier}.json \
    --html=/app/reports/${tier}.html --self-contained-html"
                ;;
            *)
                echo "make test-${tier}"
                ;;
        esac
    }

    for TIER in $TIERS; do
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        echo "▶️   tier: ${TIER}"
        START=$(date +%s)
        STATUS="PASS"

        if [ "$UPLOAD_ON" = "true" ]; then
            IN_POD_CMD="$(pod_test_cmd "$TIER")"
        else
            IN_POD_CMD="make test-${TIER}"
        fi

        if [ "$DRY_RUN" = "true" ]; then
            echo "    DRY-RUN: kubectl -n $NAMESPACE exec -i \$POD -- sh -c \"$IN_POD_CMD\""
            EC=0
        else
            # Capture the exit code rather than only branching on success so
            # we can distinguish pytest's "no tests collected" (exit 5) from
            # actual test failures. `set -e` is temporarily disabled so the
            # failing exec doesn't kill the script.
            set +e
            kubectl -n "$NAMESPACE" exec -i "$POD" -- sh -c "$IN_POD_CMD"
            EC=$?
            set -e
        fi

        case "$EC" in
            0)
                STATUS="PASS"
                ;;
            5)
                # pytest exit code 5 = "no tests collected". Treated as a
                # non-failure: tier directory is empty (expected for placeholder
                # tiers). Do not publish a report, do not count against totals.
                STATUS="NOTESTS"
                TESTS_NOTESTS=$((TESTS_NOTESTS + 1))
                ;;
            *)
                STATUS="FAIL"
                TESTS_FAILED=$((TESTS_FAILED + 1))
                ;;
        esac
        END=$(date +%s)
        RESULTS[$TIER]=$STATUS
        DURATIONS[$TIER]=$((END - START))
        echo "    [$STATUS] ${TIER}  (${DURATIONS[$TIER]}s)"
        echo ""

        # Pull BDD HTML report off the pod (original behavior, unchanged).
        if [ "$TIER" = "bdd" ] && [ "$DRY_RUN" != "true" ] && [ "$STATUS" = "PASS" ]; then
            kubectl -n "$NAMESPACE" cp "${POD}:/app/reports/bdd.html" \
                "$REPO_ROOT/reports/bdd-${ENV}.html" 2>/dev/null || true
        fi

        # When uploading, also pull the per-tier JSON (and the pytest HTML)
        # off the pod so the report generators on the host can consume them.
        # We copy regardless of STATUS so failing runs still get reported.
        if [ "$UPLOAD_ON" = "true" ] && [ "$DRY_RUN" != "true" ]; then
            kubectl -n "$NAMESPACE" cp "${POD}:/app/reports/${TIER}.json" \
                "$REPO_ROOT/reports/${TIER}.json" 2>/dev/null || true
            if [ "$TIER" != "bdd" ]; then
                kubectl -n "$NAMESPACE" cp "${POD}:/app/reports/${TIER}.html" \
                    "$REPO_ROOT/reports/${TIER}.html" 2>/dev/null || true
            fi
        fi
    done

    echo "🧪 In-pod test results"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    for TIER in $TIERS; do
        printf "   %-13s %-7s %4ss\n" "$TIER" "${RESULTS[$TIER]:-?}" "${DURATIONS[$TIER]:-0}"
    done
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    # Exclude NOTESTS tiers from the denominator: they had no tests to run,
    # so counting them as "X/Y passed" would be misleading.
    RUN_TOTAL=$((TESTS_TOTAL - TESTS_NOTESTS))
    PASSED=$((RUN_TOTAL - TESTS_FAILED))
    if [ "$TESTS_NOTESTS" -gt 0 ]; then
        echo "   Total: ${PASSED}/${RUN_TOTAL} passed (${TESTS_NOTESTS} tier(s) had no tests)"
    else
        echo "   Total: ${PASSED}/${RUN_TOTAL} passed"
    fi
    echo ""
fi

# ────────────────────────────────────────────────────────────────────────
# 2. Publish test reports to S3 + invalidate CloudFront (optional)
# ────────────────────────────────────────────────────────────────────────
# Driven by deploy/.env.local. When UPLOAD_TO_S3=true we:
#   1. Generate enhanced per-tier HTML reports on the host using the
#      generators at tests/report_generators/ (same layout + drilldown as
#      nexus-backend).
#   2. Upload each enhanced HTML to
#      s3://$S3_BUCKET_NAME/$S3_REPORTS_PREFIX/<tier>/$TIMESTAMP/report.html
#   3. Build a consolidated dashboard index.html (2x2 grid of tier cards,
#      matching nexus-backend's landing page) and upload to
#      s3://$S3_BUCKET_NAME/$S3_REPORTS_PREFIX/index.html
#   4. Create a CloudFront invalidation for "/*" and wait for it to finish
#      so the next page-load shows the fresh reports.
# Nothing happens when UPLOAD_TO_S3 is unset/false (preserves existing flow).
if [ "${UPLOAD_TO_S3:-false}" = "true" ] && [ "$DRY_RUN" != "true" ] && [ "$TIERS" != "none" ]; then
    echo "📤 Publishing reports to S3 + invalidating CloudFront"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Validate upload config (fail loud; do not silently skip).
    missing=""
    [ -z "${S3_BUCKET_NAME:-}" ]           && missing="$missing S3_BUCKET_NAME"
    [ -z "${CLOUDFRONT_DISTRIBUTION_ID:-}" ] && missing="$missing CLOUDFRONT_DISTRIBUTION_ID"
    [ -z "${CLOUDFRONT_DOMAIN:-}" ]        && missing="$missing CLOUDFRONT_DOMAIN"
    if [ -n "$missing" ]; then
        echo "❌ UPLOAD_TO_S3=true but these variables are not set:$missing"
        echo "   Populate them in $SCRIPT_DIR/.env.local and retry."
        exit 1
    fi

    S3_REPORTS_PREFIX="${S3_REPORTS_PREFIX:-test-reports}"
    S3_REPORTS_REGION="${S3_REPORTS_REGION:-us-east-1}"
    REPORTS_DIR="$REPO_ROOT/reports"
    TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
    PY="$(command -v python3 || command -v python)"
    if [ -z "$PY" ]; then
        echo "❌ python3 not found on PATH (needed to render enhanced reports)."
        exit 1
    fi
    GENERATORS_DIR="$REPO_ROOT/tests/report_generators"

    echo "   Bucket:          s3://$S3_BUCKET_NAME/$S3_REPORTS_PREFIX/"
    echo "   Region:          $S3_REPORTS_REGION"
    echo "   CloudFront dist: $CLOUDFRONT_DISTRIBUTION_ID"
    echo "   CloudFront host: $CLOUDFRONT_DOMAIN"
    echo "   Timestamp:       $TIMESTAMP"
    echo ""

    # Track which tiers actually produced a usable enhanced HTML, and what
    # their per-tier CloudFront URL is. Used to build the dashboard card
    # set and the final user-facing summary.
    declare -A ENHANCED_HTML
    declare -A REMOTE_URL

    render_enhanced() {
        local tier="$1"
        local json="$REPORTS_DIR/${tier}.json"
        local out="$REPORTS_DIR/${tier}_enhanced.html"

        if [ ! -f "$json" ]; then
            echo "   ⏭️   $tier: no JSON report at $json (skipping)"
            return 1
        fi

        case "$tier" in
            unit)
                "$PY" "$GENERATORS_DIR/generate_unit_report.py" \
                    --input "$json" --output "$out" --title "Unit Test Report" || return 1
                ;;
            integration|contract|e2e|journeys|property)
                # Reuse the integration generator (hierarchical pytest view)
                # for all pytest-based tiers other than unit/endurance.
                local title="$(echo "$tier" | awk '{print toupper(substr($0,1,1)) substr($0,2)}') Test Report"
                "$PY" "$GENERATORS_DIR/generate_integration_report.py" \
                    --input "$json" --output "$out" --title "$title" || return 1
                ;;
            bdd)
                "$PY" "$GENERATORS_DIR/generate_bdd_report.py" \
                    --input "$json" --output "$out" --title "BDD Test Report" || return 1
                ;;
            endurance)
                local adapted="$REPORTS_DIR/${tier}_endurance.json"
                "$PY" "$GENERATORS_DIR/pytest_to_endurance_json.py" \
                    --input "$json" --output "$adapted" || return 1
                "$PY" "$GENERATORS_DIR/generate_endurance_report.py" \
                    --input "$adapted" --output "$out" --title "Endurance Test Report" || return 1
                ;;
            *)
                echo "   ⏭️   $tier: no generator mapping (skipping)"
                return 1
                ;;
        esac

        if [ -f "$out" ]; then
            ENHANCED_HTML[$tier]="$out"
            return 0
        fi
        return 1
    }

    for TIER in $TIERS; do
        # Skip tiers that had no tests to collect — there's nothing useful
        # to render, and uploading an empty report would dilute the dashboard.
        if [ "${RESULTS[$TIER]:-}" = "NOTESTS" ]; then
            echo "   ⏭️   $TIER: no tests collected (skipping report)"
            continue
        fi
        echo "   🧱 Rendering $TIER ..."
        render_enhanced "$TIER" || true
    done
    echo ""

    # Upload each rendered HTML to a timestamped key under the prefix.
    for TIER in "${!ENHANCED_HTML[@]}"; do
        local_html="${ENHANCED_HTML[$TIER]}"
        s3_key="$S3_REPORTS_PREFIX/$TIER/$TIMESTAMP/report.html"
        echo "   📤 $TIER -> s3://$S3_BUCKET_NAME/$s3_key"
        aws s3 cp "$local_html" "s3://$S3_BUCKET_NAME/$s3_key" \
            --content-type "text/html; charset=utf-8" \
            --region "$S3_REPORTS_REGION" \
            >/dev/null
        REMOTE_URL[$TIER]="https://$CLOUDFRONT_DOMAIN/$TIER/$TIMESTAMP/report.html"
    done
    echo ""

    # Build the dashboard index.html (2x2 grid of tier cards, matching the
    # nexus-backend landing page look). We do this in an inline Python
    # script because the card set + stats come straight from the JSONs,
    # and Python keeps the HTML templating readable.
    INDEX_HTML="$REPORTS_DIR/index.html"
    # Export per-tier URLs for the index builder to pick up.
    for TIER in "${!REMOTE_URL[@]}"; do
        export "URL_${TIER}=${REMOTE_URL[$TIER]}"
    done

    "$PY" - "$INDEX_HTML" "$TIMESTAMP" "$REPORTS_DIR" $TIERS <<'PYINDEX'
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

out_path = Path(sys.argv[1])
timestamp = sys.argv[2]
reports_dir = Path(sys.argv[3])
tiers = sys.argv[4:]

# Per-tier display config: label, subtitle, icon, accent color,
# and a "primary-metric label" for the stat cards.
TIER_UI = {
    "unit":        ("Unit Tests",        "Component-level test coverage",    "🧪", "#10b981", "Total"),
    "integration": ("Integration Tests", "End-to-end API & service tests",   "🔗", "#3b82f6", "Total"),
    "contract":    ("Contract Tests",    "Cross-adapter contract tests",     "🔌", "#0ea5e9", "Total"),
    "property":    ("Property Tests",    "Hypothesis property tests",        "🎲", "#8b5cf6", "Total"),
    "e2e":         ("E2E Tests",         "In-process reference-server tests","🚦", "#14b8a6", "Total"),
    "journeys":    ("Journey Tests",     "Plugin journey YAML samples",      "🗺️", "#6366f1", "Total"),
    "bdd":         ("BDD Tests",         "Behavior-driven scenarios",        "📝", "#f59e0b", "Scenarios"),
    "endurance":   ("Endurance Tests",   "Performance & stability tests",    "🏃", "#a855f7", "Iterations"),
}

def parse_tier(tier):
    """Return (total, passed, failed, rate) for a tier, or None."""
    json_path = reports_dir / f"{tier}.json"
    if not json_path.exists():
        return None
    try:
        data = json.loads(json_path.read_text())
    except Exception:
        return None

    if tier == "bdd":
        total = passed = failed = 0
        for feature in data:
            for el in feature.get("elements", []) or []:
                if el.get("type") != "scenario":
                    continue
                total += 1
                steps = el.get("steps", []) or []
                statuses = [(s.get("result") or {}).get("status") for s in steps]
                if any(s == "failed" for s in statuses):
                    failed += 1
                elif statuses and all(s == "passed" for s in statuses):
                    passed += 1
    else:
        tests = data.get("tests", []) or []
        summary = data.get("summary", {}) or {}
        total = summary.get("total", len(tests)) or len(tests)
        passed = sum(1 for t in tests if t.get("outcome") == "passed")
        failed = sum(1 for t in tests if t.get("outcome") in ("failed", "error"))

    rate = round((passed / total * 100), 0) if total else 0
    return total, passed, failed, int(rate)

cards = []
for tier in tiers:
    ui = TIER_UI.get(tier)
    if not ui:
        continue
    stats = parse_tier(tier)
    if not stats:
        continue
    url = os.environ.get(f"URL_{tier}", f"./{tier}/{timestamp}/report.html")
    cards.append((tier, ui, stats, url))

def rate_class(rate):
    if rate >= 80: return "high"
    if rate >= 60: return "medium"
    return "low"

def render_card(tier, ui, stats, url):
    label, subtitle, icon, accent, metric = ui
    total, passed, failed, rate = stats
    cls = rate_class(rate)
    return f"""
                <a href="{html.escape(url)}" class="category-card {tier}">
                    <div class="card-left">
                        <div class="card-header">
                            <div class="category-circle {tier}">{icon}</div>
                            <div class="card-title-section">
                                <h3>{label}</h3>
                                <p>{subtitle}</p>
                            </div>
                        </div>
                        <div class="stats-grid">
                            <div class="stat-box total"><div class="value">{total}</div><div class="label">{metric}</div></div>
                            <div class="stat-box passed"><div class="value">{passed}</div><div class="label">Passed</div></div>
                            <div class="stat-box failed"><div class="value">{failed}</div><div class="label">Failed</div></div>
                        </div>
                        <div class="pass-rate-bar">
                            <div class="pass-rate-fill {cls}" style="width: {rate}%"></div>
                        </div>
                        <div class="card-footer">
                            <span class="pass-rate-text {cls}">{rate}% Pass Rate</span>
                            <span class="view-btn">View Report</span>
                        </div>
                    </div>
                    <div class="card-right">
                        <div class="kpi-large {cls}">{rate}%</div>
                        <div class="kpi-label">Pass Rate</div>
                    </div>
                </a>"""

generated = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
cards_html = "\n".join(render_card(*c) for c in cards) or '<p style="text-align:center; padding:40px; color:#6b7280;">No reports generated.</p>'

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Reports - Nexus AI Engine</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f2 100%);
            color: #1e293b; line-height: 1.6; min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 50px 24px; text-align: center;
            position: relative; overflow: hidden;
        }
        .header h1 { font-size: 38px; margin-bottom: 10px; font-weight: 700; }
        .header p { font-size: 16px; opacity: 0.9; }
        .main-container {
            max-width: 1100px; margin: -40px auto 0;
            padding: 0 24px 40px; position: relative; z-index: 10;
        }
        .dashboard-box {
            background: white; border-radius: 20px;
            box-shadow: 0 10px 60px rgba(0,0,0,0.12);
            padding: 32px; margin-bottom: 24px;
        }
        .dashboard-title { text-align: center; margin-bottom: 32px; }
        .dashboard-title h2 { font-size: 24px; color: #374151; margin-bottom: 8px; }
        .dashboard-title p { color: #9ca3af; font-size: 14px; }
        .grid-2x2 {
            display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px;
        }
        .category-card {
            background: linear-gradient(145deg, #fafbfc 0%, #f3f4f6 100%);
            border-radius: 16px; padding: 24px; position: relative;
            transition: all 0.3s ease; border: 2px solid transparent;
            cursor: pointer; text-decoration: none; color: inherit;
            display: flex; gap: 20px;
        }
        .category-card:hover { transform: translateY(-6px); box-shadow: 0 20px 40px rgba(0,0,0,0.1); }
        .card-left { flex: 1; }
        .card-right {
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            min-width: 100px; padding-left: 20px;
            border-left: 2px dashed #e5e7eb;
        }
        .kpi-large { font-size: 48px; font-weight: 800; line-height: 1; margin-bottom: 4px; }
        .kpi-large.high { color: #059669; } .kpi-large.medium { color: #d97706; } .kpi-large.low { color: #dc2626; }
        .kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #6b7280; font-weight: 600; }
        .category-card.unit { border-color: #10b981; }
        .category-card.integration { border-color: #3b82f6; }
        .category-card.contract { border-color: #0ea5e9; }
        .category-card.property { border-color: #8b5cf6; }
        .category-card.e2e { border-color: #14b8a6; }
        .category-card.journeys { border-color: #6366f1; }
        .category-card.bdd { border-color: #f59e0b; }
        .category-card.endurance { border-color: #a855f7; }
        .card-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
        .category-circle {
            width: 70px; height: 70px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 32px; flex-shrink: 0; position: relative;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        }
        .category-circle.unit { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
        .category-circle.integration { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
        .category-circle.contract { background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); }
        .category-circle.property { background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); }
        .category-circle.e2e { background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%); }
        .category-circle.journeys { background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); }
        .category-circle.bdd { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
        .category-circle.endurance { background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%); }
        .card-title-section h3 { font-size: 18px; font-weight: 700; color: #1f2937; margin-bottom: 4px; }
        .card-title-section p { font-size: 12px; color: #6b7280; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
        .stat-box {
            text-align: center; padding: 12px 8px; background: white;
            border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        .stat-box .value { font-size: 24px; font-weight: 700; line-height: 1.2; }
        .stat-box .label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: #9ca3af; margin-top: 4px; }
        .stat-box.total .value { color: #374151; }
        .stat-box.passed .value { color: #059669; }
        .stat-box.failed .value { color: #dc2626; }
        .pass-rate-bar { height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; margin-bottom: 12px; }
        .pass-rate-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
        .pass-rate-fill.high { background: linear-gradient(90deg, #10b981 0%, #059669 100%); }
        .pass-rate-fill.medium { background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%); }
        .pass-rate-fill.low { background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%); }
        .card-footer { display: flex; justify-content: space-between; align-items: center; }
        .pass-rate-text { font-size: 14px; font-weight: 600; }
        .pass-rate-text.high { color: #059669; }
        .pass-rate-text.medium { color: #d97706; }
        .pass-rate-text.low { color: #dc2626; }
        .view-btn { font-size: 12px; color: #667eea; font-weight: 600; display: flex; align-items: center; gap: 4px; }
        .view-btn::after { content: '\\2192'; transition: transform 0.2s; }
        .category-card:hover .view-btn::after { transform: translateX(4px); }
        .timestamp { text-align: center; padding: 16px; color: #9ca3af; font-size: 13px; }
        @media (max-width: 768px) {
            .grid-2x2 { grid-template-columns: 1fr; }
            .main-container { margin-top: -20px; }
            .header { padding: 40px 24px; }
            .header h1 { font-size: 28px; }
            .category-card { flex-direction: column; }
            .card-right { border-left: none; border-top: 2px dashed #e5e7eb; padding-left: 0; padding-top: 16px; margin-top: 16px; flex-direction: row; gap: 8px; }
            .kpi-large { font-size: 36px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Test Reports Dashboard</h1>
        <p>Nexus AI Engine - Comprehensive Test Analytics</p>
    </div>
    <div class="main-container">
        <div class="dashboard-box">
            <div class="dashboard-title">
                <h2>Test Categories</h2>
                <p>Click on any category to view detailed analytics report</p>
            </div>
            <div class="grid-2x2">%%CARDS%%
            </div>
        </div>
        <div class="timestamp">Last updated: %%GENERATED%%</div>
    </div>
</body>
</html>
"""

final_html = INDEX_TEMPLATE.replace("%%CARDS%%", cards_html).replace("%%GENERATED%%", generated)
out_path.write_text(final_html, encoding="utf-8")
print(f"index.html written to {out_path}")
PYINDEX

    echo "   📤 index.html -> s3://$S3_BUCKET_NAME/$S3_REPORTS_PREFIX/index.html"
    aws s3 cp "$INDEX_HTML" \
        "s3://$S3_BUCKET_NAME/$S3_REPORTS_PREFIX/index.html" \
        --content-type "text/html; charset=utf-8" \
        --region "$S3_REPORTS_REGION" \
        >/dev/null

    echo ""
    echo "🔄 Creating CloudFront invalidation ..."
    INVALIDATION_ID="$(aws cloudfront create-invalidation \
        --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
        --paths "/*" \
        --query 'Invalidation.Id' \
        --output text)"
    echo "   Invalidation ID: $INVALIDATION_ID"

    WAIT=0
    MAX_WAIT=180
    while true; do
        STATUS="$(aws cloudfront get-invalidation \
            --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
            --id "$INVALIDATION_ID" \
            --query 'Invalidation.Status' \
            --output text 2>/dev/null || echo InProgress)"
        if [ "$STATUS" = "Completed" ]; then
            echo "   ✅ Invalidation completed (${WAIT}s)"
            break
        fi
        if [ "$WAIT" -ge "$MAX_WAIT" ]; then
            echo "   ⚠️  Still $STATUS after ${MAX_WAIT}s — reports will be live shortly."
            break
        fi
        sleep 5
        WAIT=$((WAIT + 5))
    done

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🌐 View the latest reports:"
    echo "   https://$CLOUDFRONT_DOMAIN/index.html"
    for TIER in "${!REMOTE_URL[@]}"; do
        echo "     • $TIER: ${REMOTE_URL[$TIER]}"
    done
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

# ────────────────────────────────────────────────────────────────────────
# 3. Summary
# ────────────────────────────────────────────────────────────────────────
echo "🎯 Tests complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "   Environment:  %s\n" "$ENV"
printf "   Region:       %s\n" "$REGION"
printf "   Cluster:      %s\n" "$CLUSTER_NAME"
printf "   Namespace:    %s\n" "$NAMESPACE"
printf "   Image:        %s/%s:%s\n" "$ECR_REGISTRY" "$IMAGE_NAME" "$IMAGE_TAG"
if [ "$TIERS" != "none" ]; then
    FINAL_RUN_TOTAL=$((TESTS_TOTAL - TESTS_NOTESTS))
    printf "   Tests:        %d/%d passed" "$((FINAL_RUN_TOTAL - TESTS_FAILED))" "$FINAL_RUN_TOTAL"
    if [ "$TESTS_NOTESTS" -gt 0 ]; then
        printf " (%d tier(s) had no tests)" "$TESTS_NOTESTS"
    fi
    printf "\n"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$TESTS_FAILED" -gt 0 ]; then
    echo "❌ One or more test tiers failed."
    exit 1
fi

echo "✅ Done!"
