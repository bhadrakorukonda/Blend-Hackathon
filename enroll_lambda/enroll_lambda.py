import json
import uuid
import boto3
from decimal import Decimal
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
patients_table = dynamodb.Table('Patients')
match_requests_table = dynamodb.Table('MatchRequests')

VALID_BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
VALID_URGENCIES = ['CRITICAL', 'HIGH', 'NORMAL']

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
}


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))

        required_fields = ['name', 'blood_group', 'latitude', 'longitude', 'phone', 'urgency']
        missing = [f for f in required_fields if body.get(f) in (None, '')]
        if missing:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': f"Missing required field(s): {', '.join(missing)}"})
            }

        blood_group = str(body.get('blood_group')).strip()
        if blood_group not in VALID_BLOOD_GROUPS:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': f"Invalid blood_group. Must be one of: {', '.join(VALID_BLOOD_GROUPS)}"})
            }

        urgency = str(body.get('urgency')).strip().upper()
        if urgency not in VALID_URGENCIES:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': f"Invalid urgency. Must be one of: {', '.join(VALID_URGENCIES)}"})
            }

        try:
            latitude = float(body.get('latitude'))
            longitude = float(body.get('longitude'))
        except (TypeError, ValueError):
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'latitude and longitude must be valid numbers'})
            }

        patient_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        patient_item = {
            'user_id': patient_id,
            'name': str(body.get('name')).strip(),
            'blood_group': blood_group,
            'latitude': Decimal(str(latitude)),
            'longitude': Decimal(str(longitude)),
            'phone': str(body.get('phone')).strip(),
            'urgency': urgency,
            'created_at': created_at,
        }
        if body.get('city'):
            patient_item['city'] = str(body.get('city')).strip()
        if body.get('age') is not None:
            patient_item['age'] = int(body.get('age'))

        patients_table.put_item(Item=patient_item)

        request_id = str(uuid.uuid4())
        match_requests_table.put_item(Item={
            'request_id': request_id,
            'patient_id': patient_id,
            'status': 'PENDING',
            'urgency': urgency,
            'created_at': created_at,
            'blood_group': blood_group,
        })

        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'patient_id': patient_id,
                'message': 'Enrollment successful. You will be contacted when a donor is matched.',
                'urgency': urgency,
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': str(e)})
        }
