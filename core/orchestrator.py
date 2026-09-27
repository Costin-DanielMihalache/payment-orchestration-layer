from gateways.paymentgateway import PaymentGateway
from core.transaction import Transaction
from core.status import Status
import time
import logging

logger=logging.getLogger(__name__)



def check_gateway_health(gateway: PaymentGateway, transaction: Transaction) -> bool:
    if not gateway.circuit_breaker.allow_request():
        logger.warning(f"Circuit breaker open for {gateway.name}, skipping")
        return False
    if not gateway.check_health():
        logger.warning(f"Gateway {gateway.name} is unavailable for transaction {transaction.transaction_id}!")
        return False
    return True


def process_and_advance(gateway: PaymentGateway, transaction: Transaction, next_status: Status, max_attempts=3, delay=0.1,repository=None,payment_registry=None) -> bool:
    if not check_gateway_health(gateway, transaction):
        return False
    # Idempotency: if this transaction was already sent successfully to the
    # same gateway (e.g. a retry triggered by a client-side timeout that
    # didn't know the payment had succeeded), don't send it again - avoids
    # double-charging
    already_processed=payment_registry.is_processed(transaction.transaction_id,gateway.name) if payment_registry else False
    if already_processed:
        logger.info(f"Transaction {transaction.transaction_id} has already been successfully processed on {gateway.name}!")
    else:
        attempts = 0
        success = False
        while attempts < max_attempts and not success:
            if attempts == 0:
                logger.info(f"Processing payment ...")
            else:
                logger.info(f"Payment processing failed, retrying ...")
            time.sleep(delay * 3)
            success = gateway.process_payment(transaction)
            gateway.total_attempts += 1
            if success:
                gateway.successful_attempts += 1
                gateway.circuit_breaker.record_success()
            else:
                gateway.circuit_breaker.record_failure()
            time.sleep(delay)
            attempts += 1
        if not success:
            logger.error(f"Payment processing failed permanently after {attempts} attempts!")
            return False
        if payment_registry:
            payment_registry.mark_processed(transaction.transaction_id,gateway.name)
    # The payment already succeeded at the gateway at this point - if the
    # status transition fails now (corrupted/inconsistent internal state), we
    # can NOT treat this as a normal retry failure: the money was taken, but
    # the system isn't sure what state the transaction is in. That's why we raise
    # RuntimeError instead of returning False - this case needs manual intervention,
    # not failover.
    if not transaction.try_change_status(next_status, delay=delay):
        raise RuntimeError(f"Payment succeeded but the status transition failed for {transaction.transaction_id} - requires manual intervention!")
    if repository:
        repository.save(transaction)
    logger.info(transaction)
    return True


def process_full_flow(gateway: PaymentGateway, transaction: Transaction, statuses: list[Status], delay=0.1,repository=None,payment_registry=None) -> bool:
    for status in statuses:
        try:
            if not process_and_advance(gateway, transaction, status, delay=delay,repository=repository,payment_registry=payment_registry):
                return False
        except RuntimeError as e:
            logger.error(f"CRITICAL ERROR: {e}")
            raise
    return True


def sort_gateways_by_success_rate(gateways: list[PaymentGateway]) -> list[PaymentGateway]:
    return sorted(gateways, key=lambda g: g.success_rate, reverse=True)


def process_with_failover(gateways: list[PaymentGateway], transaction: Transaction, statuses: list[Status], delay=0.1,repository=None,payment_registry=None) -> bool:
    # Try gateways in order of historical success rate (not random/fixed), to
    # maximize the chance of success on the first attempt
    gateways = sort_gateways_by_success_rate(gateways)
    logger.info(transaction)
    if repository:
        repository.save(transaction)
    for gateway in gateways:
        # If a previous gateway was already tried and failed, the transaction
        # is left in PROCESSING - reset it explicitly to PENDING before
        # moving to the next gateway, so the transition below (PENDING ->
        # PROCESSING) is always valid per the state machine
        if transaction.status == Status.PROCESSING:
            transaction.try_change_status(Status.PENDING, delay=delay)
            if repository:
                repository.save(transaction)
        if check_gateway_health(gateway, transaction):
            try:
                if process_full_flow(gateway, transaction, statuses, delay=delay,repository=repository,payment_registry=payment_registry):
                    return True
            except RuntimeError as e:
                # Don't continue to the next gateway - the payment already
                # succeeded once (see RuntimeError in process_and_advance), so
                # trying another gateway would risk a double charge
                logger.error(f"Failover stopped - requires manual intervention {e}")
                return False
    # All gateways failed (or were unhealthy) - the transaction is
    # permanently rejected
    transaction.try_change_status(Status.REJECTED, delay=delay)
    if repository:
        repository.save(transaction)
    logger.info(transaction)
    return False