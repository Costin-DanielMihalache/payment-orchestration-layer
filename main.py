from gateways.paymentgateway import PaymentGateway
from gateways.razorpaymock import RazorpayMock
from gateways.stripemock import StripeMock
from gateways.payumock import PayUMock
from gateways.upimock import UPIMock
from core.transaction import Transaction
from core.status import Status
import time

processed_payments=set()

def check_gateway_health(gateway: PaymentGateway, transaction:Transaction) ->bool:
    if not gateway.check_health():
        print(f"Gateway-ul {gateway.name} este indisponibil pentru tranzactia {transaction.transaction_id}!")
        return False
    return True


def process_and_advance(gateway: PaymentGateway, transaction:Transaction,next_status:Status,max_attempts=3,delay=0.1)->bool:
    if not check_gateway_health(gateway,transaction):
        return False
    key=(transaction.transaction_id,gateway.name)
    if key in processed_payments:
        print(f"Tranzactia {transaction.transaction_id} a fost deja procesata cu succes pe {gateway.name}!")
    else:
        attempts=0
        success=False
        while attempts<max_attempts and not success:
            if attempts==0:
                print(f"Se proceseaza plata ...")
            else:
                print(f"Procesarea platii a esuat, se reincearca din nou ...")
            time.sleep(delay*3)
            success=gateway.process_payment(transaction)
            gateway.total_attempts+=1
            if success:
                gateway.successful_attempts+=1
            time.sleep(delay)
            attempts+=1
        if not success:
            print(f"Procesarea platii a esuat definitiv dupa {attempts} incercari!")
            return False
        processed_payments.add(key)
    if not transaction.try_change_status(next_status,delay=delay):
        raise RuntimeError(f"Plata a reusit dar tranzitia de status a esuat pentru {transaction.transaction_id} - necesita interventie manuala!")
    print(transaction)
    return True

def process_full_flow(gateway:PaymentGateway,transaction:Transaction,statuses:list[Status],delay=0.1) -> bool:
    for status in statuses:
        try:
            if not process_and_advance(gateway,transaction,status,delay=delay):
                return False
        except RuntimeError as e:
            print(f"EROARE CRITICA: {e}")
            raise
    return True

def process_with_failover(gateways: list[PaymentGateway], transaction: Transaction, statuses:list[Status],delay=0.1) -> bool:
    gateways=sort_gateways_by_success_rate(gateways)
    print(transaction)
    for gateway in gateways:
        if transaction.status== Status.PROCESSING:
            transaction.try_change_status(Status.PENDING,delay=delay)
        if check_gateway_health(gateway,transaction):
            try:
                if process_full_flow(gateway,transaction,statuses,delay=delay):
                    return True
            except RuntimeError as e:
                print(f"Failover oprit - necesita interventie manuala: {e}")
                return False
    transaction.try_change_status(Status.REJECTED,delay=delay)
    print(transaction)
    return False

def sort_gateways_by_success_rate(gateways:list[PaymentGateway]) -> list[PaymentGateway]:
    return sorted(gateways,key=lambda g:g.success_rate,reverse=True)

def main():
    gateways=[RazorpayMock(),StripeMock(),PayUMock(),UPIMock()]
    t=Transaction(200,"LEU")
    process_with_failover(gateways,t,[Status.PROCESSING,Status.ACCEPTED])
    t1=Transaction(500)
    process_with_failover(gateways,t1,[Status.ACCEPTED,Status.PROCESSING])
if __name__ == "__main__":
    main()