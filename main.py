from infrastructure.container import Container


def main():

    container = Container()

    positions = container.broker.get_positions()

    print(positions)

    print()

    print("Container created successfully!")

    print(type(container.client).__name__)
    print(type(container.collector).__name__)
    print(type(container.broker).__name__)
    print(type(container.order_mapper).__name__)
    print(type(container.position_mapper).__name__)


if __name__ == "__main__":
    main()