import json

open('method-response-params.json','w').write(json.dumps({
    'method.response.header.Access-Control-Allow-Headers': False,
    'method.response.header.Access-Control-Allow-Methods': False,
    'method.response.header.Access-Control-Allow-Origin': False
}))

open('integration-response-params.json','w').write(json.dumps({
    'method.response.header.Access-Control-Allow-Headers': "'Content-Type,Authorization'",
    'method.response.header.Access-Control-Allow-Methods': "'POST,OPTIONS'",
    'method.response.header.Access-Control-Allow-Origin': "'*'"
}))
print('done')
