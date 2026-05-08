FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        ffmpeg \
        gosu \
        jq \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/meta-cloud-bridge

COPY pyproject.toml uv.lock README.md LICENSE.md CHANGELOG.md ./
COPY whatsapp ./whatsapp
COPY meta_cloud_bridge ./meta_cloud_bridge

RUN uv sync --frozen --no-dev

COPY docker-run.sh ./docker-run.sh
RUN chmod +x ./docker-run.sh \
    && cp meta_cloud_bridge/example-config.yaml ./example-config.yaml

ENV PATH="/opt/meta-cloud-bridge/.venv/bin:${PATH}" \
    UID=1337 \
    GID=1337

VOLUME /data

CMD ["/opt/meta-cloud-bridge/docker-run.sh"]
