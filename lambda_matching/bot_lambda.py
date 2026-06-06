import json
import boto3
import logging
import os
import uuid
from datetime import datetime, date
from urllib.parse import parse_qs
import base64

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
match_requests_table = dynamodb.Table('MatchRequests')
bot_sessions_table   = dynamodb.Table('BotSessions')
donors_table         = dynamodb.Table('Donors')
bedrock = boto3.client('bedrock-runtime', region_name='ap-south-1')

BEDROCK_MODEL        = 'anthropic.claude-3-haiku-20240307-v1:0'
TWILIO_ACCOUNT_SID   = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN    = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', '')


def classify_intent(text):
    prompt = (
        f"Classify this blood donor SMS reply as exactly one of: YES, NO, or MAYBE.\n"
        f"YES = donor agrees to donate or confirms availability\n"
        f"NO = donor declines or says unavailable\n"
        f"MAYBE = donor is uncertain, asks a question, or gives a partial answer\n"
        f"Reply text: \"{text}\"\n"
        f"Respond with only one word: YES, NO, or MAYBE"
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 10,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}]
    })
    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL,
        body=body,
        contentType='application/json',
        accept='application/json'
    )
    raw = json.loads(response['body'].read())['content'][0]['text'].strip().upper()
    for word in ('YES', 'NO', 'MAYBE'):
        if word in raw:
            return word
    return 'MAYBE'


def get_latest_pending_request():
    """Return the most recent MatchRequest with status pending/awaiting."""
    resp = match_requests_table.scan(
        FilterExpression='#s IN (:p, :a)',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':p': 'pending', ':a': 'awaiting'}
    )
    items = resp.get('Items', [])
    if not items:
        return None
    items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return items[0]


def twiml(message):
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Message>{message}</Message></Response>'
    )
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/xml'},
        'body': xml
    }


def lambda_handler(event, context):
    # Parse Twilio URL-encoded body
    raw_body = event.get('body', '') or ''
    if event.get('isBase64Encoded'):
        raw_body = base64.b64decode(raw_body).decode('utf-8')

    params      = parse_qs(raw_body)
    raw_from    = params.get('From', [''])[0]
    # Twilio WhatsApp prefixes From with "whatsapp:" — strip it for clean storage
    from_phone  = raw_from.removeprefix('whatsapp:')
    reply_text  = params.get('Body', [''])[0].strip()
    message_sid = params.get('MessageSid', [str(uuid.uuid4())])[0]

    logger.info(f"Webhook | From: {from_phone} | Body: '{reply_text}' | SID: {message_sid}")

    if not reply_text:
        return twiml("Please reply YES, NO, or MAYBE to your blood donation request.")

    # Classify intent with Bedrock Haiku
    try:
        intent = classify_intent(reply_text)
    except Exception as e:
        logger.error(f"Bedrock classification failed: {e}")
        intent = 'MAYBE'

    logger.info(f"Intent: {intent} for '{reply_text}'")

    # Find active match request
    match_request = get_latest_pending_request()
    now = datetime.utcnow().isoformat()

    if not match_request:
        logger.warning("No pending match request found")
        return twiml("Blood Warriors: No active blood request found. Thank you for your response.")

    request_id = match_request['request_id']

    # Map intent to status
    new_status = {'YES': 'confirmed', 'NO': 'escalate', 'MAYBE': 'awaiting'}[intent]

    # Update MatchRequests
    try:
        match_requests_table.update_item(
            Key={'request_id': request_id},
            UpdateExpression=(
                'SET #s = :status, donor_response = :dr, responded_at = :ts'
            ),
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': new_status,
                ':dr': {'phone': from_phone, 'intent': intent, 'message': reply_text},
                ':ts': now,
            }
        )
        logger.info(f"MatchRequest {request_id[:8]} -> status={new_status}")
    except Exception as e:
        logger.error(f"MatchRequests update failed: {e}")

    # Upsert BotSession (PK = phone_number)
    try:
        bot_sessions_table.put_item(Item={
            'phone_number': from_phone,
            'request_id': request_id,
            'last_message': reply_text,
            'intent': intent,
            'message_sid': message_sid,
            'updated_at': now,
        })
        logger.info(f"BotSession upserted for {from_phone}")
    except Exception as e:
        logger.error(f"BotSessions write failed: {e}")

    # Dynamic re-ranking: donor said NO — deprioritise them for the next 7 days
    # recency_score() in matcher.py gives 0 pts if last_contacted_date < 7 days ago
    if intent == 'NO':
        try:
            current_rank = int(match_request.get('current_donor_rank', 0))
            top_donors   = json.loads(match_request.get('top_donors', '[]'))
            donor_id     = top_donors[current_rank].get('user_id', '') if current_rank < len(top_donors) else ''
            if donor_id:
                donors_table.update_item(
                    Key={'user_id': donor_id},
                    UpdateExpression='SET last_contacted_date = :today',
                    ExpressionAttributeValues={':today': date.today().isoformat()}
                )
                logger.info(f"Re-rank: last_contacted_date={date.today()} for donor {donor_id[:16]} (said NO)")
        except Exception as e:
            logger.error(f"Re-rank update failed: {e}")

    # TwiML reply
    replies = {
        'YES':   "Blood Warriors: Thank you! Your confirmation is recorded. A coordinator will be in touch shortly.",
        'NO':    "Blood Warriors: Understood. We will reach the next matched donor. Thank you for letting us know.",
        'MAYBE': "Blood Warriors: Got it. If you become available, reply YES at any time. Thank you.",
    }
    return twiml(replies[intent])
