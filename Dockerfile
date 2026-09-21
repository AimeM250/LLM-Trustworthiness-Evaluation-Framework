FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY ltef ./ltef
COPY examples ./examples
COPY docs ./docs
COPY README.md ./

RUN pip install --no-cache-dir .

# The web workspace's own auth model assumes a trusted network boundary (see SECURITY.md).
# Binding beyond 127.0.0.1 (the default here, since Docker networking needs it to be reachable
# via published ports) means YOU are responsible for TLS/access control in front of it.
EXPOSE 8765
VOLUME ["/data"]

ENTRYPOINT ["python", "-m"]
CMD ["ltef.webapp", "--host", "0.0.0.0", "--port", "8765", "--database", "/data/workspace.sqlite3"]
