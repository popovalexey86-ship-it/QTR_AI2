import math


def validate_entry_fill_fields(
    *,
    status_name: str,
    requested_volume: float,
    filled_volume: float,
    average_fill_price: float | None,
) -> None:
    """Validate normalized entry-order fill quantities and price."""

    if not math.isfinite(requested_volume) or requested_volume <= 0:
        raise ValueError("Requested volume must be finite and positive.")
    if not math.isfinite(filled_volume) or filled_volume < 0:
        raise ValueError("Filled volume must be finite and non-negative.")
    if filled_volume > requested_volume:
        raise ValueError("Filled volume cannot exceed requested volume.")

    if average_fill_price is not None and (
        not math.isfinite(average_fill_price) or average_fill_price <= 0
    ):
        raise ValueError("Average fill price must be finite and positive.")
    if filled_volume == 0 and average_fill_price is not None:
        raise ValueError("An unfilled entry cannot have an average fill price.")
    if filled_volume > 0 and average_fill_price is None:
        raise ValueError("A filled entry requires an average fill price.")

    if status_name in ("SUBMITTED", "WORKING"):
        if filled_volume != 0:
            raise ValueError(
                f"{status_name} entries cannot have filled volume."
            )
    elif status_name == "PARTIALLY_FILLED":
        if not 0 < filled_volume < requested_volume:
            raise ValueError(
                "A partially filled entry requires volume between zero "
                "and requested volume."
            )
    elif status_name == "FILLED":
        if filled_volume != requested_volume:
            raise ValueError(
                "A filled entry requires the entire requested volume."
            )
    elif filled_volume == requested_volume:
        raise ValueError("Only FILLED entries may contain the full volume.")
