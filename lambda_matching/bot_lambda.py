import json
import boto3
import logging
import os
import uuid
from datetime import datetime, date, timedelta
from urllib.parse import parse_qs
import urllib.request
import urllib.error
import base64

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
match_requests_table = dynamodb.Table('MatchRequests')
bot_sessions_table   = dynamodb.Table('BotSessions')
donors_table         = dynamodb.Table('Donors')
bedrock = boto3.client('bedrock-runtime', region_name='ap-south-1')
scheduler = boto3.client('scheduler', region_name='ap-south-1')

BEDROCK_MODEL        = 'anthropic.claude-3-haiku-20240307-v1:0'
TWILIO_ACCOUNT_SID   = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN    = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', '')
TWILIO_WHATSAPP_TO   = os.environ.get('TWILIO_WHATSAPP_TO', '')

QUESTION_WORDS = {'when', 'where', 'what', 'how', 'time', 'tomorrow', 'available', 'which', 'why'}

# --- Hesitation sub-types ---
# HESITANT_LOGISTICS: donor is willing but has a practical barrier (transport, location, timing)
# HESITANT_AWARE: donor is unsure what blood donation involves (safety, process, eligibility)
HESITATION_TYPES = {'HESITANT_LOGISTICS', 'HESITANT_AWARE'}

# Targeted follow-up messages when AI generation fails
LOGISTICS_FALLBACK = (
    "Blood Warriors: The donation centre is at Care Hospital, Banjara Hills. "
    "We can arrange a cab if needed. Reply YES and we will coordinate!"
)
AWARE_FALLBACK = (
    "Blood Warriors: Donation takes 10 mins, is completely safe, and you are eligible. "
    "Your gift saves a life. Reply YES — we will guide you through every step."
)

HARDCODED_REPLIES = {
    'YES':     "Blood Warriors: Thank you! Your confirmation is recorded. A coordinator will be in touch shortly.",
    'NO':      "Blood Warriors: Understood. We will reach the next matched donor. Thank you for letting us know.",
    'DONATED': "Thank you! Your donation has been recorded. You are a lifesaver.",
    'UNABLE':  "Thank you for letting us know. We hope to see you next time.",
}
MAYBE_FALLBACK = "Blood Warriors: Got it. If you become available, reply YES at any time. Thank you."

FLAGGED_HUMAN_REPLY = "Blood Warriors: Thank you for reaching out. A coordinator will be in touch with you shortly."


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
    Single Bedrock call: classify intent and detect language.

    Intent values:
      YES               — donor agrees or confirms
      NO                — donor declines
      MAYBE             — uncertain or conditional
      HESITANT_LOGISTICS — willing but has a practical barrier (transport, location, timing, hospital)
      HESITANT_AWARE    — unsure about safety, process, eligibility, or what donation involves
      FLAGGED_HUMAN     — abuse, hostility, distress, mental health signals, medical emergency,
                          or too ambiguous to handle autonomously — needs human coordinator review
      DONATED           — donor confirms the donation happened (in response to a follow-up)
      UNABLE            — donor confirms they could not make it to donate (in response to a follow-up)

    Also returns:
      decline_reason (only meaningful when intent=NO):
        TRANSPORT | TIMING | HEALTH | AWARENESS | OTHER

    Returns: (intent, language_code, decline_reason)
    """
    history_block = ''
    if history:
        lines = [f"  [{h['role']}]: {h['message']}" for h in history]
        history_block = "Conversation so far:\n" + "\n".join(lines) + "\n\n"

    prompt = (
        "You are classifying a blood donor's WhatsApp reply for Blood Warriors, an NGO in Hyderabad.\n"
        "The donor may reply in ANY Indian language: Hindi, Telugu, Tamil, Kannada, Malayalam, Bengali, Marathi, Gujarati, or English.\n\n"
        f"{history_block}"
        f"Latest donor message: \"{text}\"\n\n"
        "INTENT — pick exactly one:\n"
        "  YES                = donor agrees, confirms, or says they are available\n"
        "  NO                 = donor declines or says unavailable\n"
        "  MAYBE              = uncertain, conditional, gives no clear signal\n"
        "  HESITANT_LOGISTICS = donor is willing BUT has a practical barrier "
        "(e.g. no transport, asks which hospital, asks for address, timing conflict, asks about location)\n"
        "  HESITANT_AWARE     = donor unsure about what donation involves "
        "(e.g. asks if it is safe, how long it takes, will it hurt, asks about eligibility, blood loss)\n"
        "  FLAGGED_HUMAN      = reply contains abuse, hostility, distress, mental health signals, "
        "medical emergency, or is too ambiguous to handle autonomously — a human coordinator must review\n"
        "  DONATED            = donor confirms they completed the blood donation "
        "(e.g. 'yes I donated', 'done', 'completed it')\n"
        "  UNABLE             = donor confirms they could NOT make it to donate "
        "(e.g. 'could not go', 'missed it', 'wasn't able to')\n\n"
        "DECLINE_REASON — only when intent is NO, pick one:\n"
        "  TRANSPORT  = no vehicle or travel issue\n"
        "  TIMING     = busy, wrong time, schedule conflict\n"
        "  HEALTH     = unwell, on medication, health concern\n"
        "  AWARENESS  = does not understand why blood is needed or what is involved\n"
        "  OTHER      = any other reason or unspecified\n\n"
        "LANG — language code: en hi te ta kn ml bn mr gu other\n\n"
        "Respond with EXACTLY one line in this format:\n"
        "<INTENT> <LANG> <DECLINE_REASON>\n"
        "If intent is not NO, use NONE for DECLINE_REASON. FLAGGED_HUMAN always uses NONE.\n\n"
        "Examples:\n"
        "  YES en NONE\n"
        "  NO te TIMING\n"
        "  HESITANT_LOGISTICS en NONE\n"
        "  HESITANT_AWARE hi NONE\n"
        "  MAYBE en NONE\n"
        "  FLAGGED_HUMAN en NONE\n"
        "  DONATED en NONE\n"
        "  UNABLE en NONE\n"
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

        intent         = 'MAYBE'
        language       = 'en'
        decline_reason = 'OTHER'

        valid_intents = {
            'YES', 'NO', 'MAYBE', 'HESITANT_LOGISTICS', 'HESITANT_AWARE',
            'FLAGGED_HUMAN', 'DONATED', 'UNABLE',
        }
        valid_reasons = {'TRANSPORT', 'TIMING', 'HEALTH', 'AWARENESS', 'OTHER', 'NONE'}

        for word in valid_intents:
            if word in parts:
                intent = word
                break

        # language is always the second token in our format
        if len(parts) >= 2:
            language = parts[1].lower()

        # decline_reason is the third token
        if len(parts) >= 3 and parts[2] in valid_reasons:
            decline_reason = parts[2] if parts[2] != 'NONE' else None
        else:
            decline_reason = None

        logger.info(f"Bedrock classification | intent={intent} lang={language} decline_reason={decline_reason} raw='{raw}'")
        return intent, language, decline_reason

    except Exception as e:
        logger.error(f"Bedrock classification failed: {e}")
        return 'MAYBE', 'en', None


def generate_conversational_reply(text, intent, language, history, donor_info, patient_blood_grp):
    """
    Second Bedrock call: generate a warm, context-aware reply.

    For HESITANT_LOGISTICS: directly answer the logistical question (address, transport offer).
    For HESITANT_AWARE: reassure about safety/process, answer the specific concern.
    For MAYBE or general questions: acknowledge warmly and encourage YES.

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

    # Tailored instruction based on hesitation type
    if intent == 'HESITANT_LOGISTICS':
        task_instruction = (
            "The donor is willing but has a PRACTICAL BARRIER (transport, location, timing). "
            "Directly address their concern: give the donation centre address (Care Hospital, Banjara Hills, Hyderabad), "
            "offer transport coordination, or clarify timing. Be specific and helpful. "
            "End with encouragement to reply YES."
        )
    elif intent == 'HESITANT_AWARE':
        task_instruction = (
            "The donor is unsure about what blood donation involves. "
            "Reassure them directly: donation takes 10 minutes, is completely safe, "
            "no pain beyond a small prick, full recovery in minutes, "
            "and they are already verified eligible. "
            "Answer their specific concern if possible. End with encouragement to reply YES."
        )
    else:
        task_instruction = (
            "If the donor asked a question, answer it using the facts above. "
            "If MAYBE, acknowledge warmly and encourage them to reply YES when ready."
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
        f"{task_instruction}\n"
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
    # Includes 'confirmed' so a donor's later DONATED/UNABLE follow-up reply
    # can still be matched back to their already-confirmed request.
    resp = match_requests_table.scan(
        FilterExpression='#s IN (:p, :a, :c)',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':p': 'pending', ':a': 'awaiting', ':c': 'confirmed'}
    )
    items = resp.get('Items', [])
    if not items:
        return None
    items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return items[0]


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
        err_body = e.read().decode('utf-8', errors='replace')
        logger.error(f"Twilio HTTP {e.code}: {err_body}")
        raise


def notify_coordinator(request_id, donor_info, patient_blood_group):
    donor_name  = donor_info.get('name', 'A donor')
    donor_blood = donor_info.get('blood_group', patient_blood_group)
    distance    = donor_info.get('distance_km', 0)
    donations   = donor_info.get('donations_till_date', 0)

    message = (
        f"Blood Warriors: CONFIRMED. {donor_name} ({donor_blood}, "
        f"{donations} lifetime donations, {distance}km away) has confirmed "
        f"for request {request_id[:8].upper()}. "
        f"Please coordinate hospital visit. Request ID: {request_id[:8].upper()}"
    )

    if not TWILIO_WHATSAPP_TO or not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.warning("Twilio coordinator notification skipped — credentials or TWILIO_WHATSAPP_TO not set")
        return

    send_whatsapp(TWILIO_WHATSAPP_TO, message)


def schedule_donation_followup(from_phone, request_id, donor_name):
    fire_time = datetime.utcnow() + timedelta(hours=2)
    fire_time_str = fire_time.strftime('%Y-%m-%dT%H:%M:%S')

    try:
        scheduler.create_schedule(
            Name=f"followup-{request_id[:8]}",
            ScheduleExpression=f"at({fire_time_str})",
            FlexibleTimeWindow={'Mode': 'OFF'},
            Target={
                'Arn': 'arn:aws:lambda:ap-south-1:179503921630:function:FollowUpLambda',
                'RoleArn': 'arn:aws:iam::179503921630:role/BloodWarriorsLambdaRole',
                'Input': json.dumps({
                    'phone': from_phone,
                    'request_id': request_id,
                    'donor_name': donor_name
                })
            },
            ActionAfterCompletion='DELETE'
        )
        logger.info(f"Follow-up scheduled for {from_phone} in 2 hours")
    except Exception as e:
        logger.error(f"Follow-up scheduling failed: {e}")


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

    # --- Classify intent + detect language + get decline reason (single Bedrock call) ---
    intent, language, decline_reason = classify_intent_and_language(reply_text, recent_history)
    logger.info(f"Intent: {intent} | Language: {language} | Decline reason: {decline_reason} | Message: '{reply_text}'")

    # --- Find active match request ---
    match_request = get_latest_pending_request()
    now = datetime.utcnow().isoformat()

    if not match_request:
        logger.warning("No pending match request found")
        return twiml("Blood Warriors: No active blood request found. Thank you for your response.")

    request_id        = match_request['request_id']
    patient_blood_grp = match_request.get('patient_blood_group', 'Unknown')
    donor_info        = get_donor_info_from_request(match_request)

    # --- Map intent to MatchRequest status ---
    # Hesitation types keep the request in 'awaiting' — the bot is actively trying to convert
    status_map = {
        'YES':                 'confirmed',
        'NO':                  'escalate',
        'MAYBE':               'awaiting',
        'HESITANT_LOGISTICS':  'awaiting',
        'HESITANT_AWARE':      'awaiting',
        'FLAGGED_HUMAN':       'awaiting',
        'DONATED':             'confirmed',
        'UNABLE':              'confirmed',
    }
    new_status = status_map.get(intent, 'awaiting')

    # --- Build update expression — include decline_reason only when NO ---
    try:
        update_expr   = 'SET #s = :status, donor_response = :dr, responded_at = :ts'
        expr_names    = {'#s': 'status'}
        expr_values   = {
            ':status': new_status,
            ':dr': {
                'phone':          from_phone,
                'intent':         intent,
                'message':        reply_text,
                'decline_reason': decline_reason,
            },
            ':ts': now,
        }
        if decline_reason:
            update_expr += ', decline_reason = :dcr'
            expr_values[':dcr'] = decline_reason

        # FLAGGED_HUMAN: freeze for human review — do not advance to next donor
        if intent == 'FLAGGED_HUMAN':
            update_expr += ', human_escalation_flag = :hef, human_escalation_reason = :her'
            expr_values[':hef'] = True
            expr_values[':her'] = reply_text

        # DONATED / UNABLE: record the donation follow-up outcome
        if intent == 'DONATED':
            update_expr += ', donation_confirmed = :dc, donation_date = :dd'
            expr_values[':dc'] = True
            expr_values[':dd'] = date.today().isoformat()
        elif intent == 'UNABLE':
            update_expr += ', donation_confirmed = :dc'
            expr_values[':dc'] = False

        match_requests_table.update_item(
            Key={'request_id': request_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        logger.info(f"MatchRequest {request_id[:8]} -> status={new_status} decline_reason={decline_reason}")
    except Exception as e:
        logger.error(f"MatchRequests update failed: {e}")

    # --- Notify coordinator on confirmation + schedule donation follow-up ---
    if intent == 'YES':
        try:
            notify_coordinator(request_id, donor_info, patient_blood_grp)
            logger.info(f"Coordinator notified for confirmed request {request_id[:8]}")
        except Exception as e:
            logger.error(f"Coordinator notification failed: {e}")

        schedule_donation_followup(from_phone, request_id, donor_info.get('name', 'Donor'))

    # --- Increment donor's confirmed_donations when they confirm the donation happened ---
    if intent == 'DONATED':
        try:
            donor_id = donor_info.get('user_id', '')
            if donor_id:
                donors_table.update_item(
                    Key={'user_id': donor_id},
                    UpdateExpression='SET confirmed_donations = if_not_exists(confirmed_donations, :zero) + :one',
                    ExpressionAttributeValues={':zero': 0, ':one': 1}
                )
                logger.info(f"Donor {donor_id[:16]} confirmed_donations incremented")
        except Exception as e:
            logger.error(f"Donor confirmed_donations update failed: {e}")

    # --- Append turn to conversation history ---
    conv_history.append({
        'role':           'donor',
        'message':        reply_text,
        'intent':         intent,
        'language':       language,
        'decline_reason': decline_reason,
        'timestamp':      now,
    })

    # --- Upsert BotSession with full conversation_history ---
    try:
        bot_sessions_table.put_item(Item={
            'phone_number':         from_phone,
            'request_id':           request_id,
            'last_message':         reply_text,
            'intent':               intent,
            'language':             language,
            'decline_reason':       decline_reason,
            'message_sid':          message_sid,
            'updated_at':           now,
            'conversation_history': json.dumps(conv_history),
        })
        logger.info(f"BotSession saved | phone={from_phone} | lang={language} | turns={len(conv_history)}")
    except Exception as e:
        logger.error(f"BotSessions write failed: {e}")

    # --- Dynamic re-ranking on NO / UNABLE (7-day penalty: push back in rotation) ---
    if intent in ('NO', 'UNABLE'):
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
                logger.info(f"Re-rank: last_contacted_date={date.today()} for donor {donor_id[:16]} (said {intent}, reason={decline_reason})")
        except Exception as e:
            logger.error(f"Re-rank update failed: {e}")

    # --- TwiML reply ---

    # Clear YES / NO: hardcoded, no AI needed
    if intent in HARDCODED_REPLIES:
        return twiml(HARDCODED_REPLIES[intent])

    # FLAGGED_HUMAN: graceful hold reply, no AI generation — coordinator takes over
    if intent == 'FLAGGED_HUMAN':
        return twiml(FLAGGED_HUMAN_REPLY)

    # Hesitation or MAYBE: generate targeted AI reply
    if intent in HESITATION_TYPES or intent == 'MAYBE' or is_question(reply_text):
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
        # Targeted fallbacks if AI fails
        if intent == 'HESITANT_LOGISTICS':
            return twiml(LOGISTICS_FALLBACK)
        if intent == 'HESITANT_AWARE':
            return twiml(AWARE_FALLBACK)

    return twiml(MAYBE_FALLBACK)