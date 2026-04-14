# NetBox Plus on Red Hat Universal Base Image (UBI).
# Build from repository root: docker build -t netbox-plus:local .
#
# Default is UBI 9 so the image runs on older x86_64 CPUs. UBI 10 userspace
# requires x86-64-v3; on capable hardware you can use:
#   podman build --build-arg BASE_IMAGE=registry.access.redhat.com/ubi10/ubi:latest ...
#
# Requires: subscription-free pull from registry.access.redhat.com
ARG BASE_IMAGE=registry.access.redhat.com/ubi9/ubi:latest
FROM ${BASE_IMAGE}

ARG NETBOX_CONFIGURATION=netbox.configuration_docker
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    NETBOX_CONFIGURATION=${NETBOX_CONFIGURATION}

# Python 3.12 and native build deps for psycopg, Pillow, django-auth-ldap, etc.
RUN dnf -y update && \
    dnf -y install \
        python3.12 \
        python3.12-pip \
        python3.12-devel \
        gcc \
        gcc-c++ \
        postgresql-devel \
        openldap-devel \
        openssl-devel \
        libffi-devel \
        libjpeg-turbo-devel \
        zlib-devel \
        libxml2-devel \
        libxslt-devel \
        gettext \
        file \
        && dnf clean all

RUN python3.12 -m venv /opt/netbox/venv \
    && /opt/netbox/venv/bin/python -m pip install --upgrade pip setuptools wheel

ENV PATH="/opt/netbox/venv/bin:${PATH}" \
    VIRTUAL_ENV=/opt/netbox/venv \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /opt/netbox/app

COPY requirements.txt /tmp/netbox-requirements.txt
RUN pip install --no-cache-dir -r /tmp/netbox-requirements.txt gunicorn

# Application tree
COPY netbox/ /opt/netbox/app/

# Docker-specific Django configuration
COPY docker/configuration_docker.py /opt/netbox/app/netbox/configuration_docker.py

COPY docker/entrypoint.sh /docker/entrypoint.sh
RUN chmod +x /docker/entrypoint.sh \
    && mkdir -p /opt/netbox/app/static /opt/netbox/app/media \
    && chmod -R g+w /opt/netbox/app/static /opt/netbox/app/media

EXPOSE 8080

ENTRYPOINT ["/docker/entrypoint.sh"]
CMD ["web"]
