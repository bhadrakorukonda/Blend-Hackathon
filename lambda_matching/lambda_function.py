import os
import boto3
import json
import math
import uuid
from decimal import Decimal
from datetime import datetime, date

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
donors_table = dynamodb.Table('Donors')
patients_table = dynamodb.Table('Patients')
match_requests_table = dynamodb.Table('MatchRequests')
sns = boto3.client('sns', region_name='ap-south-1')

BLOOD_COMPAT = {
    "O Negative":  ["O Negative","O Positive","A Negative","A Positive","B Negative","B Positive","AB Negative","AB Positive"],
    "O Positive":  ["O Positive","A Positive","B Positive","AB Positive"],
    "A Negative":  ["A Negative","A Positive","AB Negative","AB Positive"],
    "A Positive":  ["A Positive","AB Positive"],
    "B Negative":  ["B Negative","B Positive","AB Negative","AB Positive"],
    "B Positive":  ["B Positive","AB Positive"],
    "AB Negative": ["AB Negative","AB Positive"],
    "AB Positive": ["AB Positive"],
}

def sanitize(obj):
    """Recursively convert Decimals to float/int for JSON safety."""
    if isinstance(obj, list):
        return [sanitize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlam = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def distance_score(km):
    if km <= 50: return 30.0
    if km >= 500: return 0.0
    return 30.0 * (1 - (km - 50) / 450)

def reliability_score(ratio):
    try:
        r = min(float(ratio), 5.0)
    except:
        r = 2.5
    return 25.0 * (1 - r / 5.0)

def loyalty_score(donations):
    try:
        return 20.0 * min(float(donations) / 12.0, 1.0)
    except:
        return 0.0

def donor_type_score(donor_type):
    if str(donor_type).strip() == 'Regular Donor': return 15.0
    if str(donor_type).strip() == 'One-Time Donor': return 5.0
    return 8.0

def recency_score(last_contacted_date):
    if not last_contacted_date or str(last_contacted_date).strip() in ('', 'None', 'nan'):
        return 10.0
    try:
        last = datetime.strptime(str(last_contacted_date).strip(), '%Y-%m-%d').date()
        return 0.0 if (date.today() - last).days < 7 else 10.0
    except:
        return 10.0

def passes_hard_gates(donor, patient_blood_group):
    if str(donor.get('eligibility_status', '')).strip().lower() != 'eligible':
        return False
    if str(donor.get('user_donation_active_status', '')).strip().lower() != 'active':
        return False
    ned = str(donor.get('next_eligible_date', '')).strip()
    if ned and ned not in ('', 'None', 'nan'):
        try:
            if datetime.strptime(ned, '%Y-%m-%d').date() > date.today():
                return False
        except:
            pass
    donor_bg = str(donor.get('blood_group', '')).strip()
    return patient_blood_group in BLOOD_COMPAT.get(donor_bg, [])

def score_donor(donor, patient):
    km = haversine_km(
        donor.get('latitude', 0), donor.get('longitude', 0),
        patient.get('latitude', 0), patient.get('longitude', 0)
    )
    score = (
        distance_score(km) +
        reliability_score(donor.get('calls_to_donations_ratio', 2.5)) +
        loyalty_score(donor.get('donations_till_date', 0)) +
        donor_type_score(donor.get('donor_type', '')) +
        recency_score(donor.get('last_contacted_date', ''))
    )
    return round(score, 2), round(km, 1)

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        patient_id = body.get('patient_id')
        if not patient_id:
            return {'statusCode': 400, 'body': json.dumps({'error': 'patient_id required'})}

        # Fetch patient
        resp = patients_table.get_item(Key={'user_id': patient_id})
        patient = resp.get('Item')
        if not patient:
            return {'statusCode': 404, 'body': json.dumps({'error': f'Patient {patient_id} not found'})}

        patient_blood_group = str(patient.get('bridge_blood_group') or patient.get('blood_group', '')).strip()

        # Scan all donors
        all_donors = []
        scan_kwargs = {}
        while True:
            response = donors_table.scan(**scan_kwargs)
            all_donors.extend(response['Items'])
            if 'LastEvaluatedKey' not in response:
                break
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

        # Gate + score
        results = []
        for donor in all_donors:
            if not passes_hard_gates(donor, patient_blood_group):
                continue
            score, km = score_donor(donor, patient)
            results.append(sanitize({
                'user_id': donor.get('user_id'),
                'blood_group': donor.get('blood_group', ''),
                'score': score,
                'distance_km': km,
                'calls_to_donations_ratio': donor.get('calls_to_donations_ratio', 'N/A'),
                'donations_till_date': donor.get('donations_till_date', '0'),
                'donor_type': donor.get('donor_type', ''),
                'role': donor.get('role', ''),
                'name': donor.get('name', ''),
                'gender': donor.get('gender', ''),
                'eligibility_status': donor.get('eligibility_status', ''),
                'next_eligible_date': donor.get('next_eligible_date', ''),
                'last_donation_date': donor.get('last_donation_date', ''),
                'role': donor.get('role', ''),
                'name': donor.get('name', ''),
                'gender': donor.get('gender', ''),
                'eligibility_status': donor.get('eligibility_status', ''),
                'next_eligible_date': donor.get('next_eligible_date', ''),
                'last_donation_date': donor.get('last_donation_date', ''),
                'phone': donor.get('phone', donor.get('mobile', '')),
            }))

        results.sort(key=lambda x: x['score'], reverse=True)
        top5 = results[:5]

        # Save match request to DynamoDB
        request_id = str(uuid.uuid4())
        match_requests_table.put_item(Item={
            'request_id': request_id,
            'patient_id': patient_id,
            'patient_blood_group': patient_blood_group,
            'status': 'pending',
            'top_donors': json.dumps(top5),
            'created_at': datetime.utcnow().isoformat(),
        })

        # Publish to SNS to trigger OutreachLambda
        SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
        print(f'SNS_TOPIC_ARN={SNS_TOPIC_ARN}')
        if SNS_TOPIC_ARN and SNS_TOPIC_ARN != 'PLACEHOLDER':
            try:
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=json.dumps({
                        'request_id': request_id,
                        'patient_id': patient_id,
                        'patient_blood_group': patient_blood_group,
                        'top_donors': top5
                    }),
                    Subject='NewMatchRequest'
                )
                print('SNS publish SUCCESS')
            except Exception as sns_err:
                print(f'SNS publish FAILED: {sns_err}')

        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(sanitize({
                'request_id': request_id,
                'patient_blood_group': patient_blood_group,
                'top_donors': top5
            }))
        }

    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}   
