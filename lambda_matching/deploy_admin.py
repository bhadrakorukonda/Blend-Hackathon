"""
Deploy AdminLambda + wire GET /admin on API Gateway 046giqhktg.
Run from: lambda_matching\
  python deploy_admin.py
"""
import boto3
import zipfile
import time
import json

REGION     = 'ap-south-1'
ACCOUNT_ID = '179503921630'
LAMBDA_ROLE = f'arn:aws:iam::{ACCOUNT_ID}:role/BloodWarriorsLambdaRole'
API_ID      = '046giqhktg'
STAGE       = 'prod'

lam  = boto3.client('lambda',              region_name=REGION)
apig = boto3.client('apigateway',          region_name=REGION)

# ── Step 1: zip and deploy AdminLambda ──────────────────────────────────────
print("\n[1/4] Deploying AdminLambda...")
with zipfile.ZipFile('admin_lambda.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write('admin_lambda.py')

with open('admin_lambda.zip', 'rb') as f:
    zip_bytes = f.read()

try:
    resp = lam.create_function(
        FunctionName='AdminLambda',
        Runtime='python3.12',
        Role=LAMBDA_ROLE,
        Handler='admin_lambda.lambda_handler',
        Code={'ZipFile': zip_bytes},
        Timeout=30,
        MemorySize=256,
        Description='Returns aggregated MatchRequests stats for the admin dashboard',
    )
    admin_arn = resp['FunctionArn']
    print(f"  [OK] Created: {admin_arn}")
except lam.exceptions.ResourceConflictException:
    resp = lam.update_function_code(FunctionName='AdminLambda', ZipFile=zip_bytes)
    admin_arn = resp['FunctionArn']
    print(f"  [OK] Updated: {admin_arn}")

print("  Waiting for Lambda to be ready...")
for _ in range(20):
    cfg = lam.get_function_configuration(FunctionName='AdminLambda')
    if cfg.get('LastUpdateStatus', 'Successful') == 'Successful' and cfg.get('State') == 'Active':
        break
    time.sleep(2)
print(f"  [OK] Ready")

# ── Step 2: create /admin resource on API Gateway ────────────────────────────
print("\n[2/4] Creating /admin resource on API Gateway...")

resources = apig.get_resources(restApiId=API_ID)['items']
root_id   = next(r['id'] for r in resources if r['path'] == '/')

# Check if /admin already exists
admin_resource = next((r for r in resources if r.get('path') == '/admin'), None)
if admin_resource:
    admin_resource_id = admin_resource['id']
    print(f"  [OK] /admin already exists: {admin_resource_id}")
else:
    r = apig.create_resource(restApiId=API_ID, parentId=root_id, pathPart='admin')
    admin_resource_id = r['id']
    print(f"  [OK] Created /admin resource: {admin_resource_id}")

# ── Step 3: create GET method with Lambda proxy integration ──────────────────
print("\n[3/4] Wiring GET /admin -> AdminLambda...")

lambda_uri = (
    f'arn:aws:apigateway:{REGION}:lambda:path/2015-03-31/functions/'
    f'{admin_arn}/invocations'
)

try:
    apig.put_method(
        restApiId=API_ID,
        resourceId=admin_resource_id,
        httpMethod='GET',
        authorizationType='NONE',
    )
    print("  [OK] GET method created")
except apig.exceptions.ConflictException:
    print("  [OK] GET method already exists")

try:
    apig.put_integration(
        restApiId=API_ID,
        resourceId=admin_resource_id,
        httpMethod='GET',
        type='AWS_PROXY',
        integrationHttpMethod='POST',
        uri=lambda_uri,
    )
    print("  [OK] Lambda proxy integration set")
except apig.exceptions.ConflictException:
    print("  [OK] Integration already exists")

# Grant API Gateway permission to invoke AdminLambda
try:
    lam.add_permission(
        FunctionName='AdminLambda',
        StatementId='APIGatewayAdminInvoke',
        Action='lambda:InvokeFunction',
        Principal='apigateway.amazonaws.com',
        SourceArn=f'arn:aws:execute-api:{REGION}:{ACCOUNT_ID}:{API_ID}/*/GET/admin',
    )
    print("  [OK] Invoke permission granted")
except lam.exceptions.ResourceConflictException:
    print("  [OK] Invoke permission already exists")

# ── Step 4: deploy to prod stage ─────────────────────────────────────────────
print("\n[4/4] Deploying to prod stage...")
apig.create_deployment(restApiId=API_ID, stageName=STAGE)
print(f"  [OK] Deployed")

admin_url = f'https://{API_ID}.execute-api.{REGION}.amazonaws.com/{STAGE}/admin'
print(f"\n{'='*60}")
print("DEPLOYMENT COMPLETE")
print(f"{'='*60}")
print(f"\nAdminLambda ARN: {admin_arn}")
print(f"Admin endpoint:  {admin_url}")
print(f"\nTest:")
print(f"  curl {admin_url}")
