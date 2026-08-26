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

setup_logging()

logger=logging.getLogger(__name__)
app=FastAPI()

repository=TransactionRepository()
payment_registry=PaymentRegistry()
gateways=[RazorpayMock(),StripeMock(),PayUMock(),UPIMock()]
webhook_processor=WebhookProcessor()

class TransactionRequest(BaseModel):
    amount:float
    currency:str="EUR"

class WebhookPayload(BaseModel):
    webhook_id:str
    transaction_id:str
    amount:float
    status:str
@app.get("/")
def root():
    return {"message":"Payment Orchestration Layer API"}


@app.get("/transactions/{transaction_id}")
def get_transaction(transaction_id:str):
    transaction=repository.get(transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404,detail="Tranzactia cu a fost gasita")
    return {
        "transaction_id":transaction.transaction_id,
        "amount":transaction.amount,
        "currency":transaction.currency,
        "status":transaction.status.value,
        "created_at":transaction.created_at.isoformat(),
        "updated_at":transaction.updated_at.isoformat()
    }
@app.post("/transactions")
def create_transaction(request:TransactionRequest):
    t=Transaction(request.amount,request.currency)
    logger.info(f"Cerere noua de creare tranzactie: amount={request.amount}, currency={request.currency}")
    process_with_failover(gateways,t,[Status.PROCESSING],repository=repository,payment_registry=payment_registry)
    return {"transaction_id":t.transaction_id,"status":t.status.value}

@app.post("/webhooks")
def receive_webhook_endpoint(payload:WebhookPayload):
    transaction=repository.get(payload.transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404,detail="Transactia nu a fost gasita")
    transactions_dict={transaction.transaction_id:transaction}
    result=webhook_processor.receive_webhook(payload.model_dump(),transactions_dict)
    if result:
        repository.save(transaction)
    return {"processed":result, "status":transaction.status.value}

