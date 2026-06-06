import boto3
apig = boto3.client('apigateway', region_name='ap-south-1')
resources = apig.get_resources(restApiId='046giqhktg')['items']
for r in sorted(resources, key=lambda x: x.get('path','')):
    methods = list(r.get('resourceMethods',{}).keys())
    print(f"  {r['id']}  {r.get('path','?')}  methods={methods}")
