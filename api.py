import logging
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
from core.transaction import Transaction
from core.status import Status
from core.logging_config import setup_logging
from core.orchestrator import process_with_failover
from core.repository import TransactionRepository
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

setup_logging()

logger=logging.getLogger(__name__)
app=FastAPI()

repository=TransactionRepository()
payment_registry=PaymentRegistry()
gateways=[RazorpayMock(),StripeMock(),PayUMock(),UPIMock()]
idempotency_store=IdempotencyStore()
webhook_processor=WebhookProcessor()

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
    existing=idempotency_store.reserve(idempotency_key,fingerprint,t.transaction_id)
    if existing is not None:
        existing_id,existing_fingerprint=existing
        if existing_fingerprint!=fingerprint:
            raise HTTPException(status_code=422,detail="Idempotency-Key was already used with a different request")
        previous=repository.get(existing_id)
        if previous is None:
            raise HTTPException(status_code=409,detail="The original request is still being created, retry shortly")
        logger.info(f"Replayed request for Idempotency-Key {idempotency_key}, returning transaction {existing_id}")
        return {"transaction_id":previous.transaction_id,"status":previous.status.value}
    repository.save(t)
    logger.info(f"New transaction creation request: amount={request.amount}, currency={request.currency}")
    # (comentariul tău despre procesarea sincronă rămâne aici)
    process_with_failover(gateways,t,[Status.PROCESSING],repository=repository,payment_registry=payment_registry)
    return {"transaction_id":t.transaction_id,"status":t.status.value}

@app.post("/webhooks")
def receive_webhook_endpoint(payload:WebhookPayload):
    transaction=repository.get(payload.transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404,detail="Transaction not found")
    transactions_dict={transaction.transaction_id:transaction}
    result=webhook_processor.receive_webhook(payload.model_dump(),transactions_dict)
    if result:
        repository.save(transaction)
    return {"processed":result, "status":transaction.status.value}

