FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV TRADING_MODE=SIMULATION
ENV INITIAL_BALANCE_USDT=10000
EXPOSE 8000

CMD ["uvicorn", "git_binance_trader.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
