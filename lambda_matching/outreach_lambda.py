import json
import boto3
import logging
import os
import time
import urllib.request
import urllib.parse
import urllib.error
import base64
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client('bedrock-runtime', region_name='ap-south-1')
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
match_requests_table = dynamodb.Table('MatchRequests')

BEDROCK_MODEL       = 'anthropic.claude-3-haiku-20240307-v1:0'
TWILIO_ACCOUNT_SID  = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN   = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', '')
TWILIO_WHATSAPP_TO  = os.environ.get('TWILIO_WHATSAPP_TO', '')


def send_whatsapp(to, body):
    url = f'https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json'
    data = urllib.parse.urlencode({
        'From': TWILIO_WHATSAPP_FROM,
        'To':   to,
        'Body': body,
    }).encode('utf-8')
    credentials = base64.b64encode(
        f'{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}'.encode()
    ).decode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type':  'application/x-www-form-urlencoded',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        logger.error(f"Twilio HTTP {e.code}: {body}")
        raise


def generate_personalized_message(donor, patient_blood_grp, rank):
    donations     = int(donor.get('donations_till_date') or 0)
    donor_type    = donor.get('donor_type', 'Volunteer')
    blood_grp     = donor.get('blood_group', '')
    distance      = donor.get('distance_km', 0)
    donation_line = f"{donations} lifetime donations" if donations > 0 else "a first-time donor"
    distance_line = f"{distance}km from the patient" if float(distance) > 0 else "near the patient"

    prompt = (
        f"Write a warm, urgent SMS from Blood Warriors to a blood donor. "
        f"Under 160 characters. No placeholders like [Name]. Use only the facts given. "
        f"End with: Reply YES if available.\n"
        f"Facts: {blood_grp} blood group, {donor_type}, {donation_line}, {distance_line}\n"
        f"Patient urgently needs: {patient_blood_grp} blood in Hyderabad\n"
        f"SMS:"
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 80,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}]
    })

    for attempt in range(3):
        try:
            response = bedrock.invoke_model(
                modelId=BEDROCK_MODEL, body=body,
                contentType='application/json', accept='application/json'
            )
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 ** attempt)
            else:
                raise

    message = json.loads(response['body'].read())['content'][0]['text'].strip()
    if message.startswith('"') and message.endswith('"'):
        message = message[1:-1].strip()
    return message[:160]


def fallback_message(donor, patient_blood_grp, rank, request_id):
    blood_grp  = donor.get('blood_group', 'Unknown')
    distance   = donor.get('distance_km', '?')
    donor_type = donor.get('donor_type', 'Donor')
    score      = donor.get('score', 0)
    return (
        f"[Blood Warriors] URGENT\n"
        f"Patient needs {patient_blood_grp} blood.\n"
        f"Your group: {blood_grp} | Score: {score}/100 | {distance}km away\n"
        f"Type: {donor_type}\n"
        f"Ref: {request_id[:8]}\n"
        f"Reply YES if available."
    )


def lambda_handler(event, context):
    results = []

    for record in event.get('Records', []):
        try:
            raw_message = record['Sns']['Message']
            payload = json.loads(raw_message)
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse SNS message: {e}")
            continue

        request_id        = payload.get('request_id', 'N/A')
        patient_id        = payload.get('patient_id', 'Unknown')
        patient_blood_grp = payload.get('patient_blood_group', 'Unknown')
        top_donors        = payload.get('top_donors', [])

        logger.info(
            f"Outreach triggered | Request: {request_id} | "
            f"Patient: {patient_id} | Blood: {patient_blood_grp} | Donors: {len(top_donors)}"
        )

        if not top_donors:
            logger.warning(f"No donors in payload for request {request_id}")
            continue

        donor    = top_donors[0]
        donor_id = donor.get('user_id', 'Unknown')
        blood_grp = donor.get('blood_group', 'Unknown')
        score    = donor.get('score', 0)
        distance = donor.get('distance_km', '?')
        to_phone = TWILIO_WHATSAPP_TO
        now      = datetime.utcnow().isoformat()

        logger.info(f"Contacting donor #1: {donor_id[:16]}... | Blood: {blood_grp} | Score: {score} | {distance}km")

        if not to_phone:
            logger.warning("TWILIO_WHATSAPP_TO not set — logging only")
            results.append({'donor_rank': 1, 'donor_id': donor_id, 'status': 'logged_only'})
            continue

        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            logger.error("Twilio credentials missing — cannot send WhatsApp message")
            results.append({'donor_rank': 1, 'donor_id': donor_id, 'status': 'no_credentials'})
            continue

        # Generate personalised message via Bedrock
        ai_generated = False
        try:
            message      = generate_personalized_message(donor, patient_blood_grp, 1)
            ai_generated = True
            logger.info(f"Bedrock message for donor #1: {message}")
        except Exception as be:
            logger.warning(f"Bedrock failed, using fallback: {be}")
            message = fallback_message(donor, patient_blood_grp, 1, request_id)

        # Send via Twilio WhatsApp
        try:
            twilio_resp = send_whatsapp(to_phone, message)
            msg_sid     = twilio_resp.get('sid', 'N/A')
            logger.info(f"WhatsApp sent to {to_phone} | SID: {msg_sid} | AI: {ai_generated}")
            results.append({
                'donor_rank': 1, 'donor_id': donor_id, 'blood_group': blood_grp,
                'score': score, 'status': 'whatsapp_sent', 'message_sid': msg_sid,
                'ai_generated': ai_generated, 'message_preview': message[:80],
            })
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            results.append({'donor_rank': 1, 'donor_id': donor_id, 'status': 'failed', 'error': str(e)})
            continue

        # Write outreach metadata back to MatchRequests for EscalationLambda
        try:
            match_requests_table.update_item(
                Key={'request_id': request_id},
                UpdateExpression='SET current_donor_rank = :zero, last_outreach_at = :now',
                ExpressionAttributeValues={':zero': 0, ':now': now}
            )
        except Exception as e:
            logger.error(f"MatchRequests update failed: {e}")

    logger.info(f"Outreach complete: {json.dumps(results)}")
    return {
        'statusCode': 200,
        'body': json.dumps({'outreach_results': results})
    }
