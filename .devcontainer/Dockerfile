# Both release and development use the same reviewed runtime stage.
ARG ODOO_BASE_IMAGE=odoo:18.0
FROM ${ODOO_BASE_IMAGE} AS runtime
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-pil python3-pip \
    && rm -rf /var/lib/apt/lists/*
COPY scripts/security/runtime-overrides.txt /opt/field-crm/runtime-overrides.txt
RUN pip3 install --no-deps --require-hashes --only-binary=:all: --target /opt/field-crm/python -r /opt/field-crm/runtime-overrides.txt
ENV PYTHONPATH=/opt/field-crm/python
COPY scripts/security/patch_pypdf2.py /opt/field-crm/patch_pypdf2.py
RUN python3 /opt/field-crm/patch_pypdf2.py
USER odoo

FROM runtime AS development
USER root
ARG PILOT_UID=1000
RUN apt-get update && apt-get install -y --no-install-recommends git postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*
RUN if id ubuntu >/dev/null 2>&1; then userdel ubuntu; fi \
    && usermod --uid "${PILOT_UID}" --shell /bin/bash odoo
USER odoo
