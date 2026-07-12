from gateways.paymentgateway import PaymentGateway
from gateways.razorpaymock import RazorpayMock
from gateways.stripemock import StripeMock
from gateways.payumock import PayUMock
from gateways.upimock import UPIMock
from core.transaction import Transaction
from core.status import Status
import time

def check_gateway_health(gateway: PaymentGateway, transaction:Transaction) ->bool:
    if not gateway.check_health():
        print(f"Gateway-ul {gateway.name} este indisponibil pentru tranzactia {transaction.transaction_id}!")
        return False
    return True


def process_and_advance(gateway: PaymentGateway, transaction:Transaction,next_status:Status,max_attempts=3)->bool:
    if not check_gateway_health(gateway,transaction):
        return False
    attempts=0
    success=False
    while attempts<max_attempts and not success:
        if attempts==0:
            print(f"Se proceseaza plata ...")
        else:
            print(f"Procesarea platii a esuat, se reincearca din nou ...")
        time.sleep(3)
        success=gateway.process_payment(transaction)
        time.sleep(1)
        attempts+=1
    if not success:
        print(f"Procesarea platii a esuat definitiv dupa {attempts} incercari!")
        return False
    if not transaction.try_change_status(next_status):
        raise RuntimeError(f"Plata a reusit dar tranzitia de status a esuat pentru {transaction.transaction_id} - necesita interventie manuala!")
    print(transaction)
    return True

def process_full_flow(gateway:PaymentGateway,transaction:Transaction,statuses:list[Status]) -> bool:
    for status in statuses:
        try:
            if not process_and_advance(gateway,transaction,status):
                return False
        except RuntimeError as e:
            print(f"EROARE CRITICA: {e}")
            raise
    return True

def process_with_failover(gateways: list[PaymentGateway], transaction: Transaction, statuses:list[Status]) -> bool:
    print(transaction)
    for gateway in gateways:
        if transaction.status== Status.PROCESSING:
            transaction.try_change_status(Status.PENDING)
        if check_gateway_health(gateway,transaction):
            try:
                if process_full_flow(gateway,transaction,statuses):
                    return True
            except RuntimeError as e:
                print(f"Failover oprit - necesita interventie manuala: {e}")
                return False
    transaction.try_change_status(Status.REJECTED)
    print(transaction)
    return False

def main():
    gateways=[RazorpayMock(),StripeMock(),PayUMock(),UPIMock()]
    t=Transaction(200,"LEU")
    process_with_failover(gateways,t,[Status.PROCESSING,Status.ACCEPTED])
    t1=Transaction(500)
    process_with_failover(gateways,t1,[Status.ACCEPTED,Status.PROCESSING])
if __name__ == "__main__":
    main()