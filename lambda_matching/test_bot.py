"""
Simulate BotLambda locally with test events.
Run from lambda_matching/:
  python test_bot.py

Requires: AWS credentials with DynamoDB + Bedrock access in ap-south-1.
TWILIO_* env vars can be left blank for local tests (TwiML is returned, not sent).

Note: non-ASCII replies (Hindi, Telugu, etc.) are handled correctly by the
Lambda on Linux/UTF-8. The local test forces UTF-8 stdout to avoid Windows
console encoding errors.
"""
import sys
import os
import urllib.parse

# Force UTF-8 console output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Point at real AWS but skip Twilio sends
os.environ.setdefault('TWILIO_ACCOUNT_SID',   '')
os.environ.setdefault('TWILIO_AUTH_TOKEN',    '')
os.environ.setdefault('TWILIO_WHATSAPP_FROM', 'whatsapp:+13613265415')

import bot_lambda  # noqa: E402  (import after env setup)

DEMO_PHONE = '+918639448680'

TEST_CASES = [
    {
        'label': 'Clear YES (English)',
        'From':  f'whatsapp:{DEMO_PHONE}',
        'Body':  'Yes I can donate',
    },
    {
        'label': 'Clear NO (English)',
        'From':  f'whatsapp:{DEMO_PHONE}',
        'Body':  'No I am not available',
    },
    {
        'label': 'MAYBE (English)',
        'From':  f'whatsapp:{DEMO_PHONE}',
        'Body':  'Maybe, I need to check my schedule',
    },
    {
        'label': 'Question with ? (English)',
        'From':  f'whatsapp:{DEMO_PHONE}',
        'Body':  'When do you need the blood?',
    },
    {
        'label': 'Question word without ? (English)',
        'From':  f'whatsapp:{DEMO_PHONE}',
        'Body':  'Where is the hospital',
    },
    {
        'label': 'MAYBE in Hindi',
        'From':  f'whatsapp:{DEMO_PHONE}',
        'Body':  'Haan shayad, mujhe confirm karna hai',   # "Yes maybe, I need to confirm"
    },
    {
        'label': 'Question in Telugu',
        'From':  f'whatsapp:{DEMO_PHONE}',
        'Body':  'Enduku blood kavali?',  # "Why is blood needed?"
    },
    {
        'label': 'Available tomorrow (question word)',
        'From':  f'whatsapp:{DEMO_PHONE}',
        'Body':  'I am available tomorrow morning',
    },
]


def make_event(from_field, body_field):
    encoded = urllib.parse.urlencode({
        'From':       from_field,
        'Body':       body_field,
        'MessageSid': 'SM_test_' + body_field[:8].replace(' ', '_'),
    })
    return {
        'body':           encoded,
        'isBase64Encoded': False,
    }


def extract_reply(response):
    body = response.get('body', '')
    start = body.find('<Message>') + len('<Message>')
    end   = body.find('</Message>')
    if start > len('<Message>') - 1 and end > start:
        return body[start:end]
    return body


def run():
    print("=" * 70)
    print("BotLambda local test — multi-turn memory + AI replies")
    print("=" * 70)

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"\n[{i}] {tc['label']}")
        print(f"     Input : \"{tc['Body']}\"")
        event = make_event(tc['From'], tc['Body'])
        try:
            resp  = bot_lambda.lambda_handler(event, None)
            reply = extract_reply(resp)
            print(f"     Reply : \"{reply}\"")
            print(f"     Status: {resp.get('statusCode')}")
        except Exception as e:
            print(f"     ERROR : {e}")

    print("\n" + "=" * 70)
    print("Done. Check CloudWatch logs for classification + language details.")
    print("=" * 70)


if __name__ == '__main__':
    run()
