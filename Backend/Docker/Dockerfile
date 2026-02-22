FROM python:3.12-slim

# Install Node.js 20 LTS (required by sphinx-cli)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install punycode where sphinx-cli.cjs can find it (same directory)
RUN cd $(python -c "import sphinx_cli; import os; print(os.path.dirname(sphinx_cli.__file__))") && \
    npm init -y && npm install punycode

ENV NODE_PATH=/usr/local/lib/node_modules

COPY . .

EXPOSE 8888

CMD ["python", "server.py"]
