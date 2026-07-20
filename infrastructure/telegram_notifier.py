import requests

from core.notification import NotificationError
from core.position import Position
from core.trade import Trade
from core.trade_statistics import TradeStatistics


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout: tuple[float, float] = (3.05, 5.0),
        session: requests.Session | None = None,
    ) -> None:
        bot_token = bot_token.strip()
        chat_id = chat_id.strip()

        if not bot_token or not chat_id:
            raise ValueError(
                "Telegram bot token and chat ID are required."
            )

        self._url = (
            f"https://api.telegram.org/bot{bot_token}/sendMessage"
        )
        self._chat_id = chat_id
        self._timeout = timeout
        self._session = session or requests.Session()

    def position_opened(self, position: Position) -> None:
        message = "\n".join(
            (
                "🟢 Position Opened",
                f"Symbol: {position.symbol}",
                f"Direction: {position.decision.value}",
                f"Entry: {position.entry}",
                f"Volume: {position.volume}",
                f"Ticket: {position.ticket}",
                f"Opened at: {position.opened_at.isoformat()}",
            )
        )
        self._send(message)

    def trade_closed(
        self,
        trade: Trade,
        statistics: TradeStatistics,
    ) -> None:
        message = "\n".join(
            (
                "🔴 Trade Closed",
                f"Symbol: {trade.symbol}",
                f"Direction: {trade.decision.value}",
                f"Entry: {trade.entry}",
                f"Exit: {trade.exit}",
                f"Volume: {trade.volume}",
                f"PnL: {trade.pnl}",
                f"Fees: {trade.fees}",
                f"Ticket: {trade.ticket}",
                f"Closed at: {trade.closed_at.isoformat()}",
                "",
                f"Total trades: {statistics.total_trades}",
                f"Win rate: {statistics.win_rate * 100:.2f}%",
                f"Net PnL: {statistics.net_pnl}",
            )
        )
        self._send(message)

    def _send(self, message: str) -> None:
        try:
            response = self._session.post(
                self._url,
                json={"chat_id": self._chat_id, "text": message},
                timeout=self._timeout,
            )
        except requests.RequestException:
            raise NotificationError("Telegram request failed.") from None

        try:
            response.raise_for_status()
        except requests.RequestException:
            raise NotificationError(
                "Telegram returned an HTTP error."
            ) from None

        try:
            result = response.json()
        except ValueError:
            raise NotificationError(
                "Telegram returned an invalid response."
            ) from None

        if not isinstance(result, dict) or "ok" not in result:
            raise NotificationError(
                "Telegram returned an invalid response."
            )

        if result["ok"] is not True:
            raise NotificationError("Telegram rejected the message.")
