"""Assinatura local de transações Ethereum já preparadas."""

from eth_account import Account


def sign_prepared_transaction(*, transaction: dict, signer_private_key: str) -> str:
    """Assinar uma transação preparada pelo backend sem contactar RPC."""
    transaction_to_sign = dict(transaction)
    transaction_to_sign.pop("from", None)
    signed = Account.sign_transaction(transaction_to_sign, private_key=signer_private_key)
    return signed.raw_transaction.hex()
