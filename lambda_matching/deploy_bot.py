"""
Deploy BotLambda and wire /webhook on the existing API Gateway.
Run from: lambda_matching\
  python deploy_bot.py
"""
import boto3
import zipfile
import time

REGION       = 'ap-south-1'
ACCOUNT_ID   = '179503921630'
API_ID       = '046giqhktg'
STAGE        = 'prod'
ROOT_ID      = 'ktb88z3qx6'
LAMBDA_NAME  = 'BotLambda'
LAMBDA_ROLE  = f'arn:aws:iam::{ACCOUNT_ID}:role/BloodWarriorsLambdaRole'
SOURCE_FILE  = 'bot_lambda.py'
ZIP_FILE     = 'bot_lambda.zip'

lam   = boto3.client('lambda',     region_name=REGION)
apigw = boto3.client('apigateway', region_name=REGION)

# Step 1: Zip
print("\n[1/4] Zipping bot_lambda.py...")
with zipfile.ZipFile(ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(SOURCE_FILE)
print(f"      [OK] {ZIP_FILE} created")

# Step 2: Deploy Lambda
print(f"\n[2/4] Deploying {LAMBDA_NAME}...")
with open(ZIP_FILE, 'rb') as f:
    zip_bytes = f.read()

try:
    resp = lam.create_function(
        FunctionName=LAMBDA_NAME,
        Runtime='python3.12',
        Role=LAMBDA_ROLE,
        Handler='bot_lambda.lambda_handler',
        Code={'ZipFile': zip_bytes},
        Timeout=30,
        MemorySize=256,
        Description='Classifies donor SMS replies via Bedrock Haiku, updates DynamoDB'
    )
    lambda_arn = resp['FunctionArn']
    print(f"      [OK] Created: {lambda_arn}")
except lam.exceptions.ResourceConflictException:
    resp = lam.update_function_code(FunctionName=LAMBDA_NAME, ZipFile=zip_bytes)
    lambda_arn = resp['FunctionArn']
    print(f"      [OK] Updated: {lambda_arn}")

print("      Waiting for Lambda to be ready...")
for _ in range(20):
    cfg = lam.get_function_configuration(FunctionName=LAMBDA_NAME)
    if cfg.get('State') == 'Active':
        break
    time.sleep(2)
print(f"      [OK] Lambda active | Runtime: {cfg.get('Runtime')}")

# Step 3: Add /webhook resource + POST method
print(f"\n[3/4] Wiring /webhook on API Gateway {API_ID}...")

# Check if /webhook already exists
resources = apigw.get_resources(restApiId=API_ID)['items']
webhook_id = next((r['id'] for r in resources if r.get('path') == '/webhook'), None)

if webhook_id:
    print(f"      [OK] /webhook resource exists: {webhook_id}")
else:
    webhook_id = apigw.create_resource(
        restApiId=API_ID,
        parentId=ROOT_ID,
        pathPart='webhook'
    )['id']
    print(f"      [OK] /webhook resource created: {webhook_id}")

# PUT POST method (NONE auth — Twilio calls this)
try:
    apigw.put_method(
        restApiId=API_ID,
        resourceId=webhook_id,
        httpMethod='POST',
        authorizationType='NONE'
    )
    print(f"      [OK] POST method added")
except apigw.exceptions.ConflictException:
    print(f"      [OK] POST method already exists")

# Lambda proxy integration
lambda_uri = (
    f"arn:aws:apigateway:{REGION}:lambda:path/2015-03-31"
    f"/functions/{lambda_arn}/invocations"
)
apigw.put_integration(
    restApiId=API_ID,
    resourceId=webhook_id,
    httpMethod='POST',
    type='AWS_PROXY',
    integrationHttpMethod='POST',
    uri=lambda_uri
)
print(f"      [OK] Lambda proxy integration set")

# Deploy to prod
apigw.create_deployment(restApiId=API_ID, stageName=STAGE)
print(f"      [OK] Deployed to stage '{STAGE}'")

# Step 4: Grant API Gateway permission to invoke BotLambda
print(f"\n[4/4] Adding invoke permission for API Gateway...")
source_arn = f"arn:aws:execute-api:{REGION}:{ACCOUNT_ID}:{API_ID}/*/POST/webhook"
try:
    lam.add_permission(
        FunctionName=LAMBDA_NAME,
        StatementId='APIGatewayWebhookInvoke',
        Action='lambda:InvokeFunction',
        Principal='apigateway.amazonaws.com',
        SourceArn=source_arn
    )
    print(f"      [OK] Permission granted")
except lam.exceptions.ResourceConflictException:
    print(f"      [OK] Permission already exists")

webhook_url = f"https://{API_ID}.execute-api.{REGION}.amazonaws.com/{STAGE}/webhook"

print("\n" + "=" * 60)
print("DEPLOYMENT COMPLETE")
print("=" * 60)
print(f"\nWebhook URL:  POST {webhook_url}")
print(f"\nConfigure in Twilio Console:")
print(f"  Phone Numbers > Active Numbers > Messaging > Webhook = {webhook_url}")
print(f"\nTest manually:")
print(f'  $body = "From=%2B918639448680&Body=YES&MessageSid=test001"')
print(f'  Invoke-RestMethod -Method POST -Uri "{webhook_url}" \\')
print(f'    -ContentType "application/x-www-form-urlencoded" -Body $body')
