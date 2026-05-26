FROM ghcr.io/dexidp/dex:v2.41.1

USER root

# Install Python3, pip, wget
RUN apk add --no-cache python3 py3-pip wget

# Install grpcurl
RUN wget -q -O /tmp/grpcurl.tar.gz \
      https://github.com/fullstorydev/grpcurl/releases/download/v1.9.1/grpcurl_1.9.1_linux_x86_64.tar.gz \
    && tar xz -C /usr/local/bin/ -f /tmp/grpcurl.tar.gz grpcurl \
    && rm /tmp/grpcurl.tar.gz

# Download Dex API proto at build time — avoids runtime network dependency
RUN wget -q -O /etc/dex/dex_api.proto \
      https://raw.githubusercontent.com/dexidp/dex/v2.41.1/api/v2/api.proto

# Install Python deps in a venv to avoid system-package conflicts
COPY requirements-manage.txt /tmp/requirements-manage.txt
RUN python3 -m venv /opt/manage-venv \
    && /opt/manage-venv/bin/pip install --no-cache-dir -r /tmp/requirements-manage.txt

COPY dex.yaml /etc/dex/config.template.yaml
COPY manage.py /etc/dex/manage.py
COPY start.sh /etc/dex/start.sh
RUN chmod +x /etc/dex/start.sh

EXPOSE 5556

ENTRYPOINT ["/etc/dex/start.sh"]
