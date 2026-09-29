import json
from core.webhook_security import sign_payload

TEST_SECRET="test-secret"


def post_signed_webhook(client,payload:dict,secret=TEST_SECRET):
    # Signs the exact bytes that are sent, like a real gateway would
    body=json.dumps(payload).encode()
    return client.post(
        "/webhooks",
        content=body,
        headers={"X-Signature":sign_payload(secret,body),"Content-Type":"application/json"}
    )