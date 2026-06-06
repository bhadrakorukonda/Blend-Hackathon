import json
import boto3
import logging
import os
import time
import urllib.request
import urllib.parse
import base64
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
bedrock  = boto3.client('bedrock-runtime', region_name='ap-south-1')
match_requests_table = dynamodb.Table('MatchRequests')
donors_table         = dynamodb.Table('Donors')

BEDROCK_MODEL              = 'anthropic.claude-3-haiku-20240307-v1:0'
TWILIO_ACCOUNT_SID         = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN          = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM       = os.environ.get('TWILIO_WHATSAPP_FROM', '')
TWILIO_WHATSAPP_TO         = os.environ.get('TWILIO_WHATSAPP_TO', '')
ESCALATION_WINDOW_SECONDS  = int(os.environ.get('ESCALATION_WINDOW_SECONDS', '1800'))


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
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def generate_personalized_message(donor, patient_blood_grp, rank):
    donations     = int(donor.get('donations_till_date') or 0)
    donor_type    = donor.get('donor_type', 'Volunteer')
    blood_grp     = donor.get('blood_group', '')
    distance      = donor.get('distance_km', 0)
    donation_line = f"{donations} lifetime donations" if donations > 0 else "a new donor"
    distance_line = f"{distance}km from the patient" if float(distance) > 0 else "near the patient"

    prompt = (
        f"Write a warm, urgent follow-up SMS from Blood Warriors to a blood donor. "
        f"Under 160 characters. No placeholders. Use only the facts given. "
        f"Mention this is a follow-up — the previous donor was unavailable. "
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
            resp = bedrock.invoke_model(
                modelId=BEDROCK_MODEL, body=body,
                contentType='application/json', accept='application/json'
            )
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 ** attempt)
            else:
                raise

    text = json.loads(resp['body'].read())['content'][0]['text'].strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    return text[:160]


def fallback_message(donor, patient_blood_grp):
    bg   = donor.get('blood_group', 'Unknown')
    dist = donor.get('distance_km', '?')
    return (
        f"[Blood Warriors] Follow-up: A patient urgently needs {patient_blood_grp} blood in Hyderabad. "
        f"Your {bg} group is compatible. {dist}km away. Reply YES if available."
    )[:160]


def deprioritise_donor(top_donors, rank, request_id):
    """Set last_contacted_date=today so recency_score() gives 0 pts for 7 days."""
    try:
        donor_id = top_donors[rank].get('user_id', '') if rank < len(top_donors) else ''
        if not donor_id:
            return
        today = datetime.utcnow().date().isoformat()
        donors_table.update_item(
            Key={'user_id': donor_id},
            UpdateExpression='SET last_contacted_date = :today',
            ExpressionAttributeValues={':today': today}
        )
        logger.info(f"Re-rank: last_contacted_date={today} for donor {donor_id[:16]} (rank={rank}, req={request_id[:8]})")
    except Exception as e:
        logger.error(f"Re-rank update failed for rank {rank}: {e}")


def should_escalate(item):
    status = item.get('status', '')
    if status in ('confirmed', 'exhausted', 'cancelled'):
        return False
    if status == 'escalate':           # donor said NO — act immediately
        return True
    if status in ('pending', 'awaiting'):
        ts_str = item.get('last_outreach_at') or item.get('created_at', '')
        if not ts_str:
            return False
        try:
            last = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            return elapsed > ESCALATION_WINDOW_SECONDS
        except Exception as e:
            logger.warning(f"Timestamp parse error for {item.get('request_id','?')}: {e}")
            return False
    return False


def lambda_handler(event, context):
    logger.info(f"EscalationLambda triggered | window={ESCALATION_WINDOW_SECONDS}s")

    # Scan non-terminal requests
    resp  = match_requests_table.scan(
        FilterExpression='#s IN (:p, :a, :e)',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':p': 'pending', ':a': 'awaiting', ':e': 'escalate'}
    )
    items = resp.get('Items', [])
    logger.info(f"Non-terminal requests found: {len(items)}")

    results = []
    for item in items:
        if not should_escalate(item):
            continue

        request_id        = item['request_id']
        patient_blood_grp = item.get('patient_blood_group', 'Unknown')
        current_rank      = int(item.get('current_donor_rank', 0))
        next_rank         = current_rank + 1

        try:
            top_donors = json.loads(item.get('top_donors', '[]'))
        except (json.JSONDecodeError, TypeError):
            logger.error(f"Bad top_donors JSON for {request_id[:8]}")
            continue

        logger.info(
            f"Escalating {request_id[:8]} | "
            f"status={item.get('status')} | rank {current_rank} -> {next_rank} | "
            f"pool={len(top_donors)}"
        )

        # Dynamic re-ranking: current donor was unresponsive (timeout or NO).
        # Update their last_contacted_date so recency_score() gives 0 pts for 7 days.
        # For NO replies BotLambda already wrote this — the second write is idempotent (same day).
        deprioritise_donor(top_donors, current_rank, request_id)

        if next_rank >= len(top_donors):
            match_requests_table.update_item(
                Key={'request_id': request_id},
                UpdateExpression='SET #s = :x',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':x': 'exhausted'}
            )
            logger.warning(f"Request {request_id[:8]} exhausted all {len(top_donors)} donors")
            results.append({'request_id': request_id, 'action': 'exhausted'})
            continue

        next_donor = top_donors[next_rank]
        donor_id   = next_donor.get('user_id', 'Unknown')
        blood_grp  = next_donor.get('blood_group', 'Unknown')
        to_phone   = TWILIO_WHATSAPP_TO

        if not to_phone:
            logger.warning("TWILIO_WHATSAPP_TO not set — escalation logged only")
            results.append({'request_id': request_id, 'action': 'logged_only', 'next_rank': next_rank})
            continue

        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            logger.error("Twilio credentials missing — cannot send WhatsApp message")
            results.append({'request_id': request_id, 'action': 'no_credentials'})
            continue

        # Generate personalized escalation message
        try:
            message      = generate_personalized_message(next_donor, patient_blood_grp, next_rank + 1)
            ai_generated = True
        except Exception as e:
            logger.warning(f"Bedrock failed, using fallback: {e}")
            message      = fallback_message(next_donor, patient_blood_grp)
            ai_generated = False

        logger.info(f"Escalation WhatsApp (AI={ai_generated}) rank={next_rank}: {message}")

        # Send via Twilio WhatsApp
        try:
            twilio_resp = send_whatsapp(to_phone, message)
            msg_id      = twilio_resp.get('sid', 'N/A')
            logger.info(f"Escalation WhatsApp sent | rank={next_rank} | SID={msg_id}")
        except Exception as e:
            logger.error(f"Escalation WhatsApp failed: {e}")
            results.append({'request_id': request_id, 'action': 'whatsapp_failed', 'error': str(e)})
            continue

        # Update MatchRequest: advance rank, reset to pending, stamp outreach time
        now = datetime.utcnow().isoformat()
        match_requests_table.update_item(
            Key={'request_id': request_id},
            UpdateExpression=(
                'SET #s = :pending, current_donor_rank = :rank, last_outreach_at = :now, '
                'escalation_count = if_not_exists(escalation_count, :zero) + :one'
            ),
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':pending': 'pending',
                ':rank':    next_rank,
                ':now':     now,
                ':zero':    0,
                ':one':     1,
            }
        )

        results.append({
            'request_id':   request_id,
            'action':       'escalated',
            'from_rank':    current_rank,
            'to_rank':      next_rank,
            'donor_id':     donor_id[:16],
            'blood_group':  blood_grp,
            'ai_generated': ai_generated,
            'message_sid':  msg_id,
        })

    logger.info(f"Escalation run complete | escalated={len([r for r in results if r.get('action')=='escalated'])} | {json.dumps(results)}")
    return {
        'statusCode': 200,
        'evaluated':  len(items),
        'escalated':  len([r for r in results if r.get('action') == 'escalated']),
        'results':    results,
    }
