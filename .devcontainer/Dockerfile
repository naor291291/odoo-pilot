FROM odoo:18.0
USER root
ARG PILOT_UID=1000
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN usermod --uid "${PILOT_UID}" --shell /bin/bash odoo
USER odoo
