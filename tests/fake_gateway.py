from gateways.paymentgateway import PaymentGateway
from core.transaction import Transaction

class FakeGateway(PaymentGateway):

    def __init__(self,name="FakeGateway",healthy=True,payment_results=None):
        super().__init__(name)
        self.healthy=healthy
        self.payment_results=payment_results if payment_results is not None else [True]
        self.call_count=0

    def check_health(self)->bool:
        return self.healthy

    def process_payment(self,transaction:Transaction)->bool:
        result=self.payment_results[self.call_count % len(self.payment_results)]
        self.call_count+=1
        return result