from main import main as run_application


def main() -> None:
    """Assemble the application without starting the live trading cycle."""
    run_application(run_loop=False)


if __name__ == "__main__":
    main()
