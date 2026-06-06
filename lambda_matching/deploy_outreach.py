import boto3
import zipfile
import os
import json
import sys

REGION          = 'ap-south-1'
ACCOUNT_ID      = '179503921630'
TOPIC_NAME      = 'BloodMatchTopic'
LAMBDA_NAME     = 'OutreachLambda'
LAMBDA_ROLE_ARN = f'arn:aws:iam::{ACCOUNT_ID}:role/BloodWarriorsLambdaRole'
SOURCE_FILE     = 'outreach_lambda.py'
ZIP_FILE        = 'outreach_lambda.zip'

sns    = boto3.client('sns',    region_name=REGION)
lam    = boto3.client('lambda', region_name=REGION)
iam    = boto3.client('iam',    region_name=REGION)

# ── Step 1: Create SNS Topic ─────────────────────────────────────────────────
print("\n[1/4] Creating SNS topic...")
resp = sns.create_topic(Name=TOPIC_NAME)
topic_arn = resp['TopicArn']
print(f"      ✅ Topic ARN: {topic_arn}")

# ── Step 2: Zip the Lambda ───────────────────────────────────────────────────
print(f"\n[2/4] Zipping {SOURCE_FILE}...")
with zipfile.ZipFile(ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(SOURCE_FILE)
print(f"      ✅ Created {ZIP_FILE}")

# ── Step 3: Deploy OutreachLambda ────────────────────────────────────────────
print(f"\n[3/4] Deploying {LAMBDA_NAME}...")
with open(ZIP_FILE, 'rb') as f:
    zip_bytes = f.read()

try:
    resp = lam.create_function(
        FunctionName=LAMBDA_NAME,
        Runtime='python3.12',
        Role=LAMBDA_ROLE_ARN,
        Handler='outreach_lambda.lambda_handler',
        Code={'ZipFile': zip_bytes},
        Timeout=60,
        MemorySize=256,
        Environment={
            'Variables': {
                'SNS_TOPIC_ARN': topic_arn,
                'REGION': REGION,
            }
        },
        Description='Sends SMS to top-matched blood donors via SNS'
    )
    lambda_arn = resp['FunctionArn']
    print(f"      ✅ Created: {lambda_arn}")

except lam.exceptions.ResourceConflictException:
    print(f"      ⚠️  {LAMBDA_NAME} already exists — updating code...")
    resp = lam.update_function_code(
        FunctionName=LAMBDA_NAME,
        ZipFile=zip_bytes
    )
    lambda_arn = resp['FunctionArn']
    # also update env vars
    lam.update_function_configuration(
        FunctionName=LAMBDA_NAME,
        Environment={
            'Variables': {
                'SNS_TOPIC_ARN': topic_arn,
                'REGION': REGION,
            }
        }
    )
    print(f"      ✅ Updated: {lambda_arn}")

# Wait for Lambda to be active
import time
print("      ⏳ Waiting for Lambda to be Active...")
for _ in range(20):
    state = lam.get_function(FunctionName=LAMBDA_NAME)['Configuration']['State']
    if state == 'Active':
        break
    time.sleep(3)
print(f"      ✅ Lambda state: Active")

# ── Step 4: Subscribe Lambda to SNS ─────────────────────────────────────────
print(f"\n[4/4] Subscribing {LAMBDA_NAME} to {TOPIC_NAME}...")

# Grant SNS permission to invoke the Lambda
try:
    lam.add_permission(
        FunctionName=LAMBDA_NAME,
        StatementId='SNSInvokePermission',
        Action='lambda:InvokeFunction',
        Principal='sns.amazonaws.com',
        SourceArn=topic_arn
    )
    print("      ✅ Lambda invoke permission granted to SNS")
except lam.exceptions.ResourceConflictException:
    print("      ✅ Invoke permission already exists")

# Subscribe
sub_resp = sns.subscribe(
    TopicArn=topic_arn,
    Protocol='lambda',
    Endpoint=lambda_arn
)
print(f"      ✅ Subscription ARN: {sub_resp['SubscriptionArn']}")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("DEPLOYMENT COMPLETE ✅")
print("="*60)
print(f"\nSNS_TOPIC_ARN = {topic_arn}")
print(f"\n👉 Next step: Add this env var to MatchingLambda:")
print(f'   aws lambda update-function-configuration \\')
print(f'       --function-name MatchingLambda \\')
print(f'       --region {REGION} \\')
print(f'       --environment "Variables={{SNS_TOPIC_ARN={topic_arn}}}"')
print("\nThen deploy the updated matching_lambda.py (with SNS publish call).")  
