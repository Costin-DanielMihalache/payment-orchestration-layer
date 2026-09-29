import logging
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
from core.transaction import Transaction
from core.status import Status
from core.logging_config import setup_logging
from core.orchestrator import process_with_failover
from core.database import Database
from core.repository import TransactionRepository,ConcurrentModificationError
from core.payment_registry import PaymentRegistry
from gateways.razorpaymock import RazorpayMock
from gateways.stripemock import StripeMock
from gateways.payumock import PayUMock
from gateways.upimock import UPIMock
from core.webhook import WebhookProcessor
from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel,Field,field_validator
from core.idempotency import IdempotencyStore
from core.currency import SUPPORTED_CURRENCIES
from core.status import  WebhookStatus
import os
from fastapi import FastAPI,HTTPException,Header,Depends,Request
from pydantic import BaseModel,Field,field_validator,ValidationError
from core.webhook_security import verify_signature

setup_logging()

logger=logging.getLogger(__name__)
app=FastAPI()

# One shared Database (single SQLite connection) for everything, so related
# writes can be grouped in one atomic db.transaction() block
db=Database()
repository=TransactionRepository(db=db)
payment_registry=PaymentRegistry(db=db)
gateways=[RazorpayMock(),StripeMock(),PayUMock(),UPIMock()]
idempotency_store=IdempotencyStore(db=db)
webhook_processor=WebhookProcessor(db=db)
# Secret shared with the gateway, read from the environment - never hardcoded.
# If it is missing, the webhook endpoint refuses everything (fail closed).
webhook_secret=os.environ.get("WEBHOOK_SECRET")

class TransactionRequest(BaseModel):
    # Minor units (1050 = 10.50 EUR). strict=True rejects floats and strings.
    amount: int = Field(gt=0, strict=True)
    currency: str = "EUR"

    @field_validator("currency")
    @classmethod
    def currency_must_be_supported(cls, value: str) -> str:
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency, expected one of {sorted(SUPPORTED_CURRENCIES)}")
        return value

class WebhookPayload(BaseModel):
    webhook_id: str
    transaction_id: str
    amount: int = Field(strict=True)
    status: WebhookStatus
@app.get("/")
def root():
    return {"message":"Payment Orchestration Layer API"}


@app.get("/transactions/{transaction_id}")
def get_transaction(transaction_id:str):
    transaction=repository.get(transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404,detail="Transaction not found")
    return {
        "transaction_id":transaction.transaction_id,
        "amount":transaction.amount,
        "currency":transaction.currency,
        "status":transaction.status.value,
        "created_at":transaction.created_at.isoformat(),
        "updated_at":transaction.updated_at.isoformat()
    }
@app.post("/transactions")
def create_transaction(request:TransactionRequest,idempotency_key:str|None=Header(default=None)):
    if not idempotency_key or len(idempotency_key)>255:
        raise HTTPException(status_code=400,detail="Idempotency-Key header is required (max 255 characters)")
    t=Transaction(request.amount,request.currency)
    fingerprint=f"{request.amount}:{request.currency}"
    # Reserve the key and save the transaction in ONE database transaction: if
    # the save fails, the key is not left reserved for a transaction that
    # doesn't exist (which would make every retry fail with 409)
    with db.transaction():
        existing = idempotency_store.reserve(idempotency_key, fingerprint, t.transaction_id)
        if existing is None:
            repository.save(t)
    if existing is not None:
        existing_id,existing_fingerprint=existing
        if existing_fingerprint!=fingerprint:
            raise HTTPException(status_code=422,detail="Idempotency-Key was already used with a different request")
        previous=repository.get(existing_id)
        if previous is None:
            raise HTTPException(status_code=409,detail="The original request is still being created, retry shortly")
        logger.info(f"Replayed request for Idempotency-Key {idempotency_key}, returning transaction {existing_id}")
        return {"transaction_id":previous.transaction_id,"status":previous.status.value}

    logger.info(f"New transaction creation request: amount={request.amount}, currency={request.currency}")
    try:
        process_with_failover(gateways,t,[Status.PROCESSING],repository=repository,payment_registry=payment_registry)
    except ConcurrentModificationError:
        raise HTTPException(status_code=409,detail="Transaction was modified concurrently, fetch it again to see its current state")
    return {"transaction_id":t.transaction_id,"status":t.status.value}

async def verified_webhook_body(request:Request,x_signature:str|None=Header(default=None)) -> bytes:
    # Runs BEFORE anything is parsed or read from the database: an unsigned or
    # forged webhook must not get to learn anything (not even 404 vs 200)
    if not webhook_secret:
        logger.error("WEBHOOK_SECRET is not configured, refusing all webhooks")
        raise HTTPException(status_code=500,detail="Webhook verification is not configured")
    body=await request.body()
    if not verify_signature(webhook_secret,body,x_signature):
        logger.warning("Webhook rejected: missing or invalid X-Signature")
        raise HTTPException(status_code=401,detail="Invalid webhook signature")
    return body

@app.post("/webhooks")
def receive_webhook_endpoint(body:bytes=Depends(verified_webhook_body)):
    # The signature was checked on the raw bytes, so the payload is parsed
    # from those same bytes
    try:
        payload=WebhookPayload.model_validate_json(body)
    except ValidationError as e:
        raise HTTPException(status_code=422,detail=e.errors(include_url=False,include_context=False))
    transaction=repository.get(payload.transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404,detail="Transaction not found")
    transactions_dict={transaction.transaction_id:transaction}
    # The repository is passed in so the status save and the "webhook processed"
    # mark are committed together. If another request changed this transaction
    # since we read it, nothing is applied or marked, and the gateway's retry
    # (after the 409) will read the fresh state.
    try:
        result = webhook_processor.receive_webhook(payload.model_dump(), transactions_dict, repository=repository)
    except ConcurrentModificationError:
        raise HTTPException(status_code=409, detail="Transaction was modified concurrently, retry the webhook")
    return {"processed":result, "status":transaction.status.value}