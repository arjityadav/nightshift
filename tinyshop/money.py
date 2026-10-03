def to_cents(amount: str) -> int:
    """
    Convert a string representation of an amount in euros to cents.
    The input string should be in the format "X.YY" where X is the euro part and YY is the cent part.
    """
    if not isinstance(amount, str):
        raise ValueError("Amount must be a string")

    amount = amount.strip()

    if not amount.replace(",", "").replace(".", "").isdigit():
        raise ValueError("Amount must be a valid number in string format")

    amount = amount.replace(",", ".")
    amount = amount.split(".")
    if len(amount) == 1:
        euros = int(amount[0])
        cents = 0
    elif len(amount) == 2:
        euros = int(amount[0])
        cents = int(amount[1].ljust(2, "0"))  # Ensure two digits for cents
    else:
        raise ValueError("Amount must be in the format 'X.YY' or 'X'")
    if cents >= 100:
        raise ValueError("Cents must be less than 100")

    return euros * 100 + cents


def format_eur(cents: int) -> str:
    """
    Format an integer amount in cents to a string representation in euros.
    The output string will be in the format "X.YY" where X is the euro part and YY is the cent part.
    """
    if not isinstance(cents, int):
        raise ValueError("Cents must be an integer")
    if cents < 0:
        raise ValueError("Cents cannot be negative")

    euros = cents // 100
    remaining_cents = cents % 100

    return f"{euros}.{remaining_cents:02d} EUR"


def split_evenly(cents: int, parts: int) -> list[int]:
    if parts <= 0:
        raise ValueError("Parts must be a positive integer")
    if cents < 0:
        raise ValueError("Cents cannot be negative")
    base_amount = cents // parts
    remainder = cents % parts
    result = [base_amount] * parts
    for i in range(remainder):
        result[i] += 1
    return result
