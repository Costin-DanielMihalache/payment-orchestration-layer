from gateways.paymentgateway import PaymentGateway
from gateways.razorpaymock import RazorpayMock
from gateways.stripemock import StripeMock
from gateways.payumock import PayUMock
from gateways.upimock import UPIMock
from core.transaction import Transaction
from core.status import Status

def check_gateway_health(gateway: PaymentGateway, transaction:Transaction) ->bool:
    if not gateway.check_health():
        print(f"Gateway indisponibil pentru tranzactia {transaction.transaction_id}")
        return False
    return True


def process_and_advance(gateway: PaymentGateway, transaction:Transaction,next_status:Status)->bool:
    if not check_gateway_health(gateway,transaction):
        return False
    if not gateway.process_payment(transaction):
        print(f"Procesarea platii a esuat pentru tranzactia {transaction.transaction_id}!")
        return False
    if not transaction.try_change_status(next_status):
        return False
    print(transaction)
    return True

def process_full_flow(gateway:PaymentGateway,transaction:Transaction,statuses:list[Status]) -> bool:
    for status in statuses:
        if not process_and_advance(gateway,transaction,status):
            return False
    return True

def test_all_gateways(gateways: list[PaymentGateway],transaction:Transaction,statuses:list[Status]):
    print(transaction)
    for gateway in gateways:
        clone=transaction.clone()
        if check_gateway_health(gateway,clone):
            process_full_flow(gateway,clone,statuses)

def main():
    gateways=[RazorpayMock(),StripeMock(),PayUMock(),UPIMock()]
    t=Transaction(200,"LEU")
    test_all_gateways(gateways,t,[Status.PROCESSING,Status.ACCEPTED])
    t1=Transaction(500)
    test_all_gateways(gateways,t1,[Status.ACCEPTED,Status.PROCESSING])
if __name__ == "__main__":
    main()