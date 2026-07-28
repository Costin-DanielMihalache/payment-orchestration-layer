from main import sort_gateways_by_success_rate
from tests.fake_gateway import FakeGateway

def test_sorts_gateways_by_success_rate():
    good=FakeGateway(name="Good")
    good.total_attempts=10
    good.successful_attempts=9

    bad=FakeGateway(name="Bad")
    bad.total_attempts=10
    bad.successful_attempts=2

    result=sort_gateways_by_success_rate([good,bad])

    assert result[0].name=="Good"
    assert result[1].name=="Bad"