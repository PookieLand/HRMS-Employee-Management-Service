# todo: improvements
# use better images
# inspect after builds
# using dove
# reduce image sizes
# check security
# optimize layers

FROM python:3.13-slim

# Install system dependencies required for mysqlclient
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
COPY . /app

# Install the application dependencies.
WORKDIR /app
RUN uv sync --frozen --no-cache

# Run the application.
CMD ["/app/.venv/bin/fastapi", "run", "app/main.py", "--port", "80", "--host", "0.0.0.0"]
