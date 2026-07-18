from infrastructure.container import Container


def main():
    container = Container()

    positions = container.broker.get_positions()

    print(f"Positions: {len(positions)}")

    for position in positions:
        print(position)


if __name__ == "__main__":
    main()