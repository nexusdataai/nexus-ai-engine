# Nexus test-reports portal

Single tabbed landing page that aggregates per-component test dashboards
published by each component's `deploy/test.sh`.

## Layout

```
s3://ai-engine-test-reports/test-reports/
  index.html              <- this portal (publish-portal.sh)
  ai-engine/
    index.html            <- per-component dashboard (deploy/test.sh in nexus-ai-engine)
    <tier>/<TS>/report.html
  backend/
    index.html            <- per-component dashboard (deploy/test.sh in nexus-backend)
    <tier>/<TS>/report.html
  deployer/               <- (future)
  simulator/              <- (future)
```

Public URLs (CloudFront `E269STPYK4FJVQ` / `d37vwg02pj6oqg.cloudfront.net`):

- Portal:    https://d37vwg02pj6oqg.cloudfront.net/index.html
- AI Engine: https://d37vwg02pj6oqg.cloudfront.net/ai-engine/index.html
- Backend:   https://d37vwg02pj6oqg.cloudfront.net/backend/index.html

## Cutover / smoke validation

Run these in order the first time. Subsequent test runs only need step 2/3.

### 1. Publish the portal page (one-shot, only when `index.html` changes)

```bash
cd nexus-ai-engine
./deploy/portal/publish-portal.sh
```

Expected output ends with:

```
Portal: https://d37vwg02pj6oqg.cloudfront.net/index.html
```

Open the URL — all four tabs should be visible. Tabs whose
`<component>/index.html` does not exist yet show a friendly "No reports
yet" placeholder.

### 2. Light up the AI Engine tab

```bash
cd nexus-ai-engine
UPLOAD_TO_S3=true ./deploy/test.sh --env dev
```

Verify in the test.sh summary block:

```
🌐 View the latest reports:
   Portal:    https://d37vwg02pj6oqg.cloudfront.net/index.html
   Component: https://d37vwg02pj6oqg.cloudfront.net/ai-engine/index.html
     • unit:        https://.../ai-engine/unit/<TS>/report.html
     • integration: https://.../ai-engine/integration/<TS>/report.html
     ...
```

Then reload the portal — the **AI Engine** tab should render the 2x2 grid.

### 3. Light up the Backend tab

```bash
cd nexus-backend
./deploy/test.sh --env dev
```

(`UPLOAD_TO_S3=true` is already set in `nexus-backend/deploy/.env.local`.)

Verify the same shape of summary, with `Component: .../backend/index.html`.
Reload the portal — the **Backend** tab should render its 2x2 grid.

### 4. Sanity-check the per-tier drilldowns

Click any card in either tab. The page should be the enhanced HTML rendered
by `tests/report_generators/` (hierarchical drilldown for pytest tiers,
feature/scenario tree for BDD).

## Adding a new component (deployer / simulator)

1. Copy `nexus-ai-engine/deploy/.env.local` to the new repo's
   `deploy/.env.local`. Change `COMPONENT=<slug>`. Keep the bucket /
   CloudFront values identical.
2. Copy `nexus-ai-engine/deploy/_common.sh` to the new repo's
   `deploy/_common.sh`. Adjust the `NAMESPACE` and `IMAGE_NAME` defaults
   in `set_defaults()` to match the new component's K8s deployment.
3. Copy `nexus-backend/deploy/test.sh` (closest template — uses the same
   shared bucket and a generic tier list) to the new repo's
   `deploy/test.sh`. Change the pod selector
   (`app.kubernetes.io/name=<component>`) and `DEFAULT_TIERS` to match
   the test directories that exist.
4. Add the new tab button + frame-wrap to
   `deploy/portal/index.html` and rerun `publish-portal.sh`.

The first successful `./deploy/test.sh` in the new repo lights up the new
tab automatically.

## Operator IAM requirement

The AWS profile used to run `deploy/test.sh` (or `publish-portal.sh`)
needs:

- `s3:PutObject` on `arn:aws:s3:::ai-engine-test-reports/test-reports/*`
- `cloudfront:CreateInvalidation` and `cloudfront:GetInvalidation` on
  distribution `E269STPYK4FJVQ`

The profile used by the existing ai-engine pipeline already has these.
