import boto3
apig = boto3.client('apigateway', region_name='ap-south-1')

# Check the integration for GET /admin
try:
    integ = apig.get_integration(
        restApiId='046giqhktg',
        resourceId='erft7f',
        httpMethod='GET'
    )
    print("Integration type:", integ.get('type'))
    print("URI:", integ.get('uri'))
    print("Integration HTTP method:", integ.get('httpMethod'))
except Exception as e:
    print("Error:", e)

# Also invoke the Lambda directly to confirm it works
import json
lam = boto3.client('lambda', region_name='ap-south-1')
resp = lam.invoke(FunctionName='AdminLambda', Payload=json.dumps({}))
body = json.loads(resp['Payload'].read())
print("\nDirect Lambda response status:", body.get('statusCode'))
parsed = json.loads(body.get('body','{}'))
print("Total requests:", parsed.get('total'))
print("Status counts:", parsed.get('status_counts'))
print("Success rate:", parsed.get('success_rate'))
