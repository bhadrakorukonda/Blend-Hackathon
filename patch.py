import re

with open('lambda_matching/lambda_function.py', 'r') as f:
    content = f.read()

old = """        SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')   # fill this in when ready
        if SNS_TOPIC_ARN != 'PLACEHOLDER':
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=json.dumps({
                    'request_id': request_id,
                    'patient_id': patient_id,
                    'top_donors': top5
                }),
                Subject='NewMatchRequest'
            )"""

new = """        SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
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
                print(f'SNS publish FAILED: {sns_err}')"""

with open('lambda_matching/lambda_function.py', 'w') as f:
    f.write(content.replace(old, new))
print('done')
