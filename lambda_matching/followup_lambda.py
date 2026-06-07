import json
import boto3
import os
import logging
from datetime import date
from urllib.request import urlopen, Request
from urllib.parse import urlencode
import base64

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
match_requests_table = dynamodb.Table('MatchRequests')
donors_table = dynamodb.Table('Donors')

TWILIO_ACCOUNT_SID   = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN    = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', '')


def send_whatsapp(to, message):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = urlencode({'From': TWILIO_WHATSAPP_FROM, 'To': f'whatsapp:{to}', 'Body': message}).encode()
    credentials = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()).decode()
    req = Request(url, data=data, headers={'Authorization': f'Basic {credentials}'})
    urlopen(req)


def lambda_handler(event, context):
    phone      = event.get('phone', '')
    request_id = event.get('request_id', '')
    donor_name = event.get('donor_name', 'Donor')

    message = (
        f"Hi {donor_name}, this is Blood Warriors. "
        f"Did you complete your blood donation today? "
        f"Reply DONATED if yes, or UNABLE if you could not make it. "
        f"Your response helps us improve our system. Thank you!"
    )

    try:
        send_whatsapp(phone, message)
        logger.info(f"Follow-up sent to {phone} for request {request_id[:8]}")
    except Exception as e:
        logger.error(f"Follow-up send failed: {e}")
        return

    # BotLambda will handle the DONATED/UNABLE reply via webhook
    # Just log the outreach for now
    try:
        match_requests_table.update_item(
            Key={'request_id': request_id},
            UpdateExpression='SET followup_sent_at = :ts',
            ExpressionAttributeValues={':ts': date.today().isoformat()}
        )
    except Exception as e:
        logger.error(f"MatchRequest followup update failed: {e}")
