import logging


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("QTR_AI2")

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logger.addHandler(console)

    return logger


logger = setup_logger()