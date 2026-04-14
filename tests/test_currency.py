"""Unit tests for currency conversion tool — mocked HTTP responses."""

import respx
from httpx import Response

from src.tools.currency import convert_currency


_MOCK_EXCHANGE_RESPONSE = {
    "result": "success",
    "conversion_result": 79500.0,
    "conversion_rate": 159.0,
    "time_last_update_utc": "Sat, 22 Mar 2026 00:00:01 +0000",
}


class TestCurrencyMocked:
    @respx.mock
    async def test_successful_conversion(self, monkeypatch):
        monkeypatch.setenv("EXCHANGERATE_API_KEY", "test-key")
        respx.get(url__regex=r"exchangerate-api\.com").mock(
            return_value=Response(200, json=_MOCK_EXCHANGE_RESPONSE)
        )

        result = await convert_currency.ainvoke(
            {
                "from_currency": "USD",
                "to_currency": "JPY",
                "amount": 500,
            }
        )

        assert "500" in result
        assert "USD" in result
        assert "JPY" in result
        assert "79,500" in result

    @respx.mock
    async def test_includes_exchange_rate(self, monkeypatch):
        monkeypatch.setenv("EXCHANGERATE_API_KEY", "test-key")
        respx.get(url__regex=r"exchangerate-api\.com").mock(
            return_value=Response(200, json=_MOCK_EXCHANGE_RESPONSE)
        )

        result = await convert_currency.ainvoke(
            {
                "from_currency": "USD",
                "to_currency": "JPY",
                "amount": 100,
            }
        )

        assert "Exchange rate" in result
        assert "159" in result

    @respx.mock
    async def test_handles_api_error(self, monkeypatch):
        monkeypatch.setenv("EXCHANGERATE_API_KEY", "test-key")
        respx.get(url__regex=r"exchangerate-api\.com").mock(
            return_value=Response(
                200,
                json={
                    "result": "error",
                    "error-type": "unsupported-code",
                },
            )
        )

        result = await convert_currency.ainvoke(
            {
                "from_currency": "USD",
                "to_currency": "XYZ",
                "amount": 100,
            }
        )

        assert "failed" in result.lower()
        assert "unsupported-code" in result
