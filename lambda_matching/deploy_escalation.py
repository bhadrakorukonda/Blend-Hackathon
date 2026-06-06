"""
Deploy EscalationLambda + EventBridge rule (every 5 min).
Also redeploys updated OutreachLambda (now contacts only top donor).
Run from: lambda_matching\
  python deploy_escalation.py
"""
import boto3
import zipfile
import json
import time

REGION       = 'ap-south-1'
ACCOUNT_ID   = '179503921630'
LAMBDA_ROLE  = f'arn:aws:iam::{ACCOUNT_ID}:role/BloodWarriorsLambdaRole'
DEMO_PHONE   = '+918639448680'
RULE_NAME    = 'BloodWarriorsEscalationRule'

# For hackathon demo set ESCALATION_WINDOW_SECONDS=120 (2 min) so you don't wait 30 min.
# Change to 1800 for production.
ESCALATION_WINDOW = '120'

lam    = boto3.client('lambda',   region_name=REGION)
events = boto3.client('events',   region_name=REGION)

def zip_and_deploy(source_file, zip_file, function_name, handler, env_vars, description, create=True):
    print(f"\n  Zipping {source_file}...")
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(source_file)

    with open(zip_file, 'rb') as f:
        zip_bytes = f.read()

    if create:
        try:
            resp = lam.create_function(
                FunctionName=function_name,
                Runtime='python3.12',
                Role=LAMBDA_ROLE,
                Handler=handler,
                Code={'ZipFile': zip_bytes},
                Timeout=60,
                MemorySize=256,
                Environment={'Variables': env_vars},
                Description=description
            )
            arn = resp['FunctionArn']
            print(f"  [OK] Created: {arn}")
        except lam.exceptions.ResourceConflictException:
            resp = lam.update_function_code(FunctionName=function_name, ZipFile=zip_bytes)
            arn  = resp['FunctionArn']
            lam.update_function_configuration(
                FunctionName=function_name,
                Environment={'Variables': env_vars}
            )
            print(f"  [OK] Updated: {arn}")
    else:
        resp = lam.update_function_code(FunctionName=function_name, ZipFile=zip_bytes)
        arn  = resp['FunctionArn']
        print(f"  [OK] Updated: {arn}")

    print(f"  Waiting for Lambda to be ready...")
    for _ in range(20):
        cfg = lam.get_function_configuration(FunctionName=function_name)
        if cfg.get('LastUpdateStatus', 'Successful') == 'Successful' and cfg.get('State') == 'Active':
            break
        time.sleep(2)
    print(f"  [OK] Ready | Runtime: {cfg.get('Runtime')} | Timeout: {cfg.get('Timeout')}s")
    return arn


# Step 1: Redeploy OutreachLambda (now contacts only top donor + writes back to MatchRequests)
print("\n[1/4] Redeploying OutreachLambda (top-donor-only mode)...")
outreach_arn = zip_and_deploy(
    source_file='outreach_lambda.py',
    zip_file='outreach_lambda.zip',
    function_name='OutreachLambda',
    handler='outreach_lambda.lambda_handler',
    env_vars={'DEMO_PHONE': DEMO_PHONE},
    description='Sends personalised SMS to top donor; EscalationLambda handles the rest',
    create=False
)

# Step 2: Deploy EscalationLambda
print("\n[2/4] Deploying EscalationLambda...")
escalation_arn = zip_and_deploy(
    source_file='escalation_lambda.py',
    zip_file='escalation_lambda.zip',
    function_name='EscalationLambda',
    handler='escalation_lambda.lambda_handler',
    env_vars={
        'DEMO_PHONE': DEMO_PHONE,
        'ESCALATION_WINDOW_SECONDS': ESCALATION_WINDOW,
    },
    description='Contacts next donor when top donor times out or says NO',
    create=True
)

# Step 3: Create/update EventBridge rule (every 5 minutes)
print(f"\n[3/4] Creating EventBridge rule '{RULE_NAME}' (rate 5 minutes)...")
rule_resp = events.put_rule(
    Name=RULE_NAME,
    ScheduleExpression='rate(5 minutes)',
    State='ENABLED',
    Description='Triggers EscalationLambda every 5 minutes to contact next donor if needed'
)
rule_arn = rule_resp['RuleArn']
print(f"  [OK] Rule ARN: {rule_arn}")

# Add EscalationLambda as target
events.put_targets(
    Rule=RULE_NAME,
    Targets=[{
        'Id':  'EscalationLambdaTarget',
        'Arn': escalation_arn,
    }]
)
print(f"  [OK] EscalationLambda set as target")

# Step 4: Grant EventBridge permission to invoke EscalationLambda
print(f"\n[4/4] Granting EventBridge invoke permission...")
try:
    lam.add_permission(
        FunctionName='EscalationLambda',
        StatementId='EventBridgeEscalationInvoke',
        Action='lambda:InvokeFunction',
        Principal='events.amazonaws.com',
        SourceArn=rule_arn
    )
    print(f"  [OK] Permission granted")
except lam.exceptions.ResourceConflictException:
    print(f"  [OK] Permission already exists")

print("\n" + "=" * 60)
print("DEPLOYMENT COMPLETE")
print("=" * 60)
print(f"\nEscalationLambda ARN:  {escalation_arn}")
print(f"EventBridge rule:      {RULE_NAME} (every 5 min)")
print(f"Escalation window:     {ESCALATION_WINDOW}s ({int(ESCALATION_WINDOW)//60} min) -- set ESCALATION_WINDOW_SECONDS=1800 for production")
print(f"\nFlow:")
print(f"  Match created -> OutreachLambda contacts donor #1")
print(f"  If donor says NO  -> BotLambda sets status=escalate -> EscalationLambda contacts #2 within 5 min")
print(f"  If no reply in {ESCALATION_WINDOW}s -> EscalationLambda contacts #2 on next tick")
print(f"  Repeats up to donor #5 then status=exhausted")
print(f"\nTest escalation manually:")
print(f'  aws lambda invoke --function-name EscalationLambda --region {REGION} --payload "{{}}" out.json && cat out.json')
