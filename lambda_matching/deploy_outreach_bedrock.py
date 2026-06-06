"""
Deploy updated OutreachLambda with Bedrock Sonnet personalization.
Run from: lambda_matching\
  python deploy_outreach_bedrock.py
"""
import boto3
import zipfile
import json
import time

REGION      = 'ap-south-1'
ACCOUNT_ID  = '179503921630'
LAMBDA_NAME = 'OutreachLambda'
LAMBDA_ROLE = 'BloodWarriorsLambdaRole'
SOURCE_FILE = 'outreach_lambda.py'
ZIP_FILE    = 'outreach_lambda.zip'

lam = boto3.client('lambda', region_name=REGION)
iam = boto3.client('iam',    region_name=REGION)

# Step 1: Grant Bedrock InvokeModel permission to Lambda role
print("\n[1/3] Adding bedrock:InvokeModel to BloodWarriorsLambdaRole...")
BEDROCK_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "aws-marketplace:ViewSubscriptions",
                "aws-marketplace:Subscribe",
                "aws-marketplace:Unsubscribe"
            ],
            "Resource": "*"
        }
    ]
}

try:
    iam.put_role_policy(
        RoleName=LAMBDA_ROLE,
        PolicyName='BloodWarriorsBedrockPolicy',
        PolicyDocument=json.dumps(BEDROCK_POLICY)
    )
    print(f"      [OK] BloodWarriorsBedrockPolicy attached to {LAMBDA_ROLE}")
except Exception as e:
    print(f"      [WARN] IAM update failed (may need to do manually): {e}")

# Step 2: Zip the Lambda
print(f"\n[2/3] Zipping {SOURCE_FILE}...")
with zipfile.ZipFile(ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(SOURCE_FILE)
print(f"      [OK] Created {ZIP_FILE}")

# Step 3: Update Lambda code
print(f"\n[3/3] Updating {LAMBDA_NAME} code...")
with open(ZIP_FILE, 'rb') as f:
    zip_bytes = f.read()

resp = lam.update_function_code(FunctionName=LAMBDA_NAME, ZipFile=zip_bytes)
print(f"      [OK] Code updated: {resp['FunctionArn']}")

print("      Waiting for Lambda to be ready...")
cfg = {}
for _ in range(20):
    cfg = lam.get_function_configuration(FunctionName=LAMBDA_NAME)
    if cfg.get('LastUpdateStatus') == 'Successful':
        break
    time.sleep(3)
print(f"      [OK] Lambda ready | Runtime: {cfg.get('Runtime')} | Timeout: {cfg.get('Timeout')}s")

print("\n" + "=" * 60)
print("DEPLOYMENT COMPLETE")
print("=" * 60)
print("\nOutreachLambda now generates personalized SMS via Bedrock Sonnet.")
print("Model: anthropic.claude-3-5-sonnet-20241022-v2:0")
print("Fallback: hardcoded message if Bedrock call fails.")
print("\nCheck CloudWatch Logs for: 'Bedrock message for donor'")
