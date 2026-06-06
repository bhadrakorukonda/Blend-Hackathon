"""
Switch OutreachLambda, BotLambda, and EscalationLambda to Twilio WhatsApp.
TWILIO_AUTH_TOKEN is intentionally left empty — set it manually in the
Lambda console after deployment (it was not provided at deploy time).

Run from: lambda_matching\
  python deploy_whatsapp.py
"""
import boto3
import zipfile
import time

REGION     = 'ap-south-1'
ACCOUNT_ID = '179503921630'
LAMBDA_ROLE = f'arn:aws:iam::{ACCOUNT_ID}:role/BloodWarriorsLambdaRole'

TWILIO_ACCOUNT_SID   = 'YOUR_TWILIO_ACCOUNT_SID'
TWILIO_WHATSAPP_FROM = 'whatsapp:+13613265415'
TWILIO_WHATSAPP_TO   = 'whatsapp:+918639448680'
# Auth token intentionally blank — set manually in Lambda console
TWILIO_AUTH_TOKEN    = ''

lam = boto3.client('lambda', region_name=REGION)


def wait_ready(function_name):
    for _ in range(20):
        cfg = lam.get_function_configuration(FunctionName=function_name)
        if cfg.get('LastUpdateStatus', 'Successful') == 'Successful' and cfg.get('State') == 'Active':
            return
        time.sleep(2)


def redeploy(source_file, zip_file, function_name, env_vars):
    print(f"\n  Zipping {source_file}...")
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(source_file)
    with open(zip_file, 'rb') as f:
        zip_bytes = f.read()

    lam.update_function_code(FunctionName=function_name, ZipFile=zip_bytes)
    wait_ready(function_name)

    lam.update_function_configuration(
        FunctionName=function_name,
        Environment={'Variables': env_vars},
    )
    wait_ready(function_name)
    print(f"  [OK] {function_name} updated")


# ── OutreachLambda ────────────────────────────────────────────────────────────
print("\n[1/3] Updating OutreachLambda...")
redeploy(
    source_file='outreach_lambda.py',
    zip_file='outreach_lambda.zip',
    function_name='OutreachLambda',
    env_vars={
        'TWILIO_ACCOUNT_SID':   TWILIO_ACCOUNT_SID,
        'TWILIO_AUTH_TOKEN':    TWILIO_AUTH_TOKEN,
        'TWILIO_WHATSAPP_FROM': TWILIO_WHATSAPP_FROM,
        'TWILIO_WHATSAPP_TO':   TWILIO_WHATSAPP_TO,
    },
)

# ── BotLambda ─────────────────────────────────────────────────────────────────
print("\n[2/3] Updating BotLambda...")
redeploy(
    source_file='bot_lambda.py',
    zip_file='bot_lambda.zip',
    function_name='BotLambda',
    env_vars={
        'TWILIO_ACCOUNT_SID':   TWILIO_ACCOUNT_SID,
        'TWILIO_AUTH_TOKEN':    TWILIO_AUTH_TOKEN,
        'TWILIO_WHATSAPP_FROM': TWILIO_WHATSAPP_FROM,
    },
)

# ── EscalationLambda ──────────────────────────────────────────────────────────
print("\n[3/3] Updating EscalationLambda...")
redeploy(
    source_file='escalation_lambda.py',
    zip_file='escalation_lambda.zip',
    function_name='EscalationLambda',
    env_vars={
        'TWILIO_ACCOUNT_SID':      TWILIO_ACCOUNT_SID,
        'TWILIO_AUTH_TOKEN':       TWILIO_AUTH_TOKEN,
        'TWILIO_WHATSAPP_FROM':    TWILIO_WHATSAPP_FROM,
        'TWILIO_WHATSAPP_TO':      TWILIO_WHATSAPP_TO,
        'ESCALATION_WINDOW_SECONDS': '120',
    },
)

print("\n" + "=" * 60)
print("DEPLOYMENT COMPLETE")
print("=" * 60)
print()
print("IMPORTANT: Set TWILIO_AUTH_TOKEN manually on all three Lambdas:")
print("  AWS Console -> Lambda -> [function] -> Configuration -> Environment variables")
print("  Functions to update: OutreachLambda, BotLambda, EscalationLambda")
print()
print("Twilio sandbox webhook URL (already deployed):")
print("  https://046giqhktg.execute-api.ap-south-1.amazonaws.com/prod/webhook")
print()
print("End-to-end flow:")
print("  POST /match -> OutreachLambda -> Twilio WhatsApp -> donor replies")
print("  Twilio -> POST /webhook -> BotLambda (intent: YES/NO/MAYBE)")
print("  Timeout/NO -> EscalationLambda -> Twilio WhatsApp next donor")
