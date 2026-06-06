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

QUESTION_WORDS = {'when', 'where', 'what', 'how', 'time', 'tomorrow', 'available', 'which', 'why'}

HARDCODED_REPLIES = {
    'YES': "Blood Warriors: Thank you! Your confirmation is recorded. A coordinator will be in touch shortly.",
    'NO':  "Blood Warriors: Understood. We will reach the next matched donor. Thank you for letting us know.",
}
MAYBE_FALLBACK = "Blood Warriors: Got it. If you become available, reply YES at any time. Thank you."


def is_question(text):
    if '?' in text:
        return True
    return bool(set(text.lower().split()) & QUESTION_WORDS)


def get_bot_session(phone):
    try:
        resp = bot_sessions_table.get_item(Key={'phone_number': phone})
        return resp.get('Item', {})
    except Exception as e:
        logger.error(f"BotSession fetch failed: {e}")
        return {}


def classify_intent_and_language(text, history):
    """
    Single Bedrock call: classify intent (YES/NO/MAYBE) and detect language.
    Returns (intent, language_code).
    Supports Hindi, Telugu, Tamil, Kannada, Malayalam, and other Indian languages.
    """
    history_block = ''
    if history:
        lines = [f"  [{h['role']}]: {h['message']}" for h in history]
        history_block = "Conversation so far:\n" + "\n".join(lines) + "\n\n"

    prompt = (
        "You are classifying a blood donor's WhatsApp reply for Blood Warriors, an NGO.\n"
        "The donor may reply in ANY Indian language including Hindi, Telugu, Tamil, "
        "Kannada, Malayalam, Bengali, Marathi, Gujarati, or English.\n"
        "Classify the intent regardless of language.\n\n"
        f"{history_block}"
        f"Latest donor message: \"{text}\"\n\n"
        "Intent definitions:\n"
        "  YES   = donor agrees, confirms, or says they are available\n"
        "  NO    = donor declines, says unavailable, or refuses\n"
        "  MAYBE = donor is uncertain, asks a question, or gives a conditional answer\n\n"
        "Also detect the language. Language codes: en hi te ta kn ml bn mr gu other\n\n"
        "Respond with EXACTLY two tokens on one line: <INTENT> <LANG_CODE>\n"
        "Examples: 'YES en'  'MAYBE hi'  'NO te'  'MAYBE ta'\n"
        "Response:"
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 20,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}]
    })
    try:
        resp = bedrock.invoke_model(
            modelId=BEDROCK_MODEL, body=body,
            contentType='application/json', accept='application/json'
        )
        raw = json.loads(resp['body'].read())['content'][0]['text'].strip().upper()
        parts = raw.split()
        intent   = 'MAYBE'
        language = 'en'
        for word in ('YES', 'NO', 'MAYBE'):
            if word in parts:
                intent = word
                break
        if len(parts) >= 2:
            language = parts[1].lower()
        logger.info(f"Bedrock classification | intent={intent} lang={language} raw='{raw}'")
        return intent, language
    except Exception as e:
        logger.error(f"Bedrock classification failed: {e}")
        return 'MAYBE', 'en'


def generate_conversational_reply(text, intent, language, history, donor_info, patient_blood_grp):
    """
    Second Bedrock call: generate a warm, context-aware reply for MAYBE or question messages.
    Replies in the donor's detected language. Returns string <= 160 chars, or None on failure.
    """
    history_block = ''
    if history:
        lines = [f"  [{h['role']}]: {h['message']}" for h in history]
        history_block = "Previous messages:\n" + "\n".join(lines) + "\n\n"

    blood_grp     = donor_info.get('blood_group', '')
    donations     = donor_info.get('donations_till_date', 0)
    donor_type    = donor_info.get('donor_type', 'donor')
    next_eligible = donor_info.get('next_eligible_date', '')
    distance      = donor_info.get('distance_km', '')

    donor_facts = (
        f"Donor: {blood_grp} blood, {donor_type}, {donations} lifetime donations"
        + (f", next eligible: {next_eligible}" if next_eligible else "")
        + (f", {distance}km from patient" if distance else "")
    )

    lang_names = {
        'hi': 'Hindi', 'te': 'Telugu', 'ta': 'Tamil',
        'kn': 'Kannada', 'ml': 'Malayalam', 'bn': 'Bengali',
        'mr': 'Marathi', 'gu': 'Gujarati',
    }
    lang_instruction = (
        f"Reply in {lang_names.get(language, language.upper())} language."
        if language != 'en'
        else "Reply in English."
    )

    prompt = (
        "You represent Blood Warriors, a blood donation NGO in Hyderabad, India.\n"
        "A donor replied to an urgent blood donation request. Write a warm, helpful WhatsApp reply.\n"
        f"Rules: under 160 characters, no placeholders, factual, encouraging. {lang_instruction}\n\n"
        f"{history_block}"
        f"Donor's latest message: \"{text}\"\n"
        f"Classified intent: {intent}\n"
        f"Patient urgently needs: {patient_blood_grp} blood\n"
        f"{donor_facts}\n\n"
        "If the donor asked a question, answer it using the facts above. "
        "If MAYBE, acknowledge warmly and encourage them to reply YES when ready.\n"
        "Response:"
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "temperature": 0.6,
        "messages": [{"role": "user", "content": prompt}]
    })
    try:
        resp = bedrock.invoke_model(
            modelId=BEDROCK_MODEL, body=body,
            contentType='application/json', accept='application/json'
        )
        reply = json.loads(resp['body'].read())['content'][0]['text'].strip()
        if reply.startswith('"') and reply.endswith('"'):
            reply = reply[1:-1].strip()
        logger.info(f"AI reply (lang={language} intent={intent}): {reply[:80]}")
        return reply[:160]
    except Exception as e:
        logger.error(f"Bedrock reply generation failed: {e}")
        return None


def get_donor_info_from_request(match_request):
    """Extract the current donor's object from top_donors in the MatchRequest."""
    try:
        top_donors   = json.loads(match_request.get('top_donors', '[]'))
        current_rank = int(match_request.get('current_donor_rank', 0))
        if top_donors and current_rank < len(top_donors):
            return top_donors[current_rank]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


def get_latest_pending_request():
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
        'body': xml,
    }


def lambda_handler(event, context):
    # Parse Twilio URL-encoded body
    raw_body = event.get('body', '') or ''
    if event.get('isBase64Encoded'):
        raw_body = base64.b64decode(raw_body).decode('utf-8')

    params      = parse_qs(raw_body)
    raw_from    = params.get('From', [''])[0]
    from_phone  = raw_from.removeprefix('whatsapp:')
    reply_text  = params.get('Body', [''])[0].strip()
    message_sid = params.get('MessageSid', [str(uuid.uuid4())])[0]

    logger.info(f"Webhook | From: {from_phone} | Body: '{reply_text}' | SID: {message_sid}")

    if not reply_text:
        return twiml("Please reply YES, NO, or MAYBE to your blood donation request.")

    # --- Multi-turn memory: fetch existing session and history ---
    session = get_bot_session(from_phone)
    try:
        conv_history = json.loads(session.get('conversation_history', '[]'))
    except (json.JSONDecodeError, TypeError):
        conv_history = []

    # Pass last 5 turns to Bedrock for context
    recent_history = conv_history[-5:]

    # --- Classify intent + detect language (single Bedrock call) ---
    intent, language = classify_intent_and_language(reply_text, recent_history)
    logger.info(f"Intent: {intent} | Language: {language} | Message: '{reply_text}'")

    # --- Find active match request ---
    match_request = get_latest_pending_request()
    now = datetime.utcnow().isoformat()

    if not match_request:
        logger.warning("No pending match request found")
        return twiml("Blood Warriors: No active blood request found. Thank you for your response.")

    request_id        = match_request['request_id']
    patient_blood_grp = match_request.get('patient_blood_group', 'Unknown')
    donor_info        = get_donor_info_from_request(match_request)

    # --- Update MatchRequests ---
    new_status = {'YES': 'confirmed', 'NO': 'escalate', 'MAYBE': 'awaiting'}[intent]
    try:
        match_requests_table.update_item(
            Key={'request_id': request_id},
            UpdateExpression='SET #s = :status, donor_response = :dr, responded_at = :ts',
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

    # --- Append turn to conversation history ---
    conv_history.append({
        'role':      'donor',
        'message':   reply_text,
        'intent':    intent,
        'language':  language,
        'timestamp': now,
    })

    # --- Upsert BotSession with full conversation_history ---
    try:
        bot_sessions_table.put_item(Item={
            'phone_number':         from_phone,
            'request_id':           request_id,
            'last_message':         reply_text,
            'intent':               intent,
            'language':             language,
            'message_sid':          message_sid,
            'updated_at':           now,
            'conversation_history': json.dumps(conv_history),
        })
        logger.info(f"BotSession saved | phone={from_phone} | lang={language} | turns={len(conv_history)}")
    except Exception as e:
        logger.error(f"BotSessions write failed: {e}")

    # --- Dynamic re-ranking on NO ---
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

    # --- TwiML reply ---

    # Clear YES / NO: hardcoded, no AI needed
    if intent in HARDCODED_REPLIES:
        return twiml(HARDCODED_REPLIES[intent])

    # MAYBE or question: generate context-aware AI reply
    if (intent == 'MAYBE') or is_question(reply_text):
        ai_reply = generate_conversational_reply(
            text=reply_text,
            intent=intent,
            language=language,
            history=recent_history,
            donor_info=donor_info,
            patient_blood_grp=patient_blood_grp,
        )
        if ai_reply:
            return twiml(ai_reply)

    return twiml(MAYBE_FALLBACK)
