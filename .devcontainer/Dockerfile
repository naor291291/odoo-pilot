FROM odoo:18.0
USER root
ARG PILOT_UID=1000
RUN apt-get update && apt-get install -y --no-install-recommends git postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*
RUN if id ubuntu >/dev/null 2>&1; then userdel ubuntu; fi \
    && usermod --uid "${PILOT_UID}" --shell /bin/bash odoo
USER odoo
