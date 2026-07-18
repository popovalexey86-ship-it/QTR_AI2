from infrastructure.container import Container


def main():
    container = Container()

    market_data = container.collector.collect()

    print(f"Symbol: {market_data.symbol}")
    print(f"Timeframe: {market_data.timeframe}")
    print(f"Candles: {market_data.count}")

    print("\nLast candle:")
    print(market_data.last)


if __name__ == "__main__":
    main()
