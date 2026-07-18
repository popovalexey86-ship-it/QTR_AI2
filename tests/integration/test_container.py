from infrastructure.container import Container


def main():
    container = Container()

    print(container.config)
    print(container.client)
    print(container.collector)
    print(container.broker)


if __name__ == "__main__":
    main()
