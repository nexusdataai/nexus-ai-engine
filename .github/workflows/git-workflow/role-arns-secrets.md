# StarHub Backend GitHub Actions Role ARNs

| Secret Name | Value |
|-------------|-------|
| AWS_ROLE_TO_ASSUME_DEV | arn:aws:iam::764119721991:role/GitHubActions-starhub-backend-dev |
| AWS_ROLE_TO_ASSUME_TEST | arn:aws:iam::764119721991:role/GitHubActions-starhub-backend-test |
| AWS_ROLE_TO_ASSUME_STAGE | arn:aws:iam::764119721991:role/GitHubActions-starhub-backend-stage |
| AWS_ROLE_TO_ASSUME_PROD | arn:aws:iam::764119721991:role/GitHubActions-starhub-backend-main |

## Environment URLs

| Environment | API URL | ECS Cluster | ECS Service |
|-------------|---------|-------------|-------------|
| dev | https://call-api-dev.totogicore.com | call-processing-dev-cluster | call-processing-dev-service |
| test | https://call-api-test.totogicore.com | call-processing-test-cluster | call-processing-test-service |
| stage | https://call-api-stage.totogicore.com | call-processing-stage-cluster | call-processing-stage-service |
| prod | https://call-api.totogicore.com | call-processing-prod-cluster | call-processing-prod-service |
