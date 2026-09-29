# Multi-stage build for the linbpq runtime image published to Docker Hub.
# The first stage compiles linbpq from source against the dev libs; the
# second stage carries only the binary, the HTML/ static assets, and the
# matching runtime shared libraries.

FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        libpaho-mqtt-dev \
        libjansson-dev \
        libminiupnpc-dev \
        libconfig-dev \
        libpcap-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# libbacktrace (linked since 6.0.25.41) isn't packaged here, so build
# it from a pinned upstream commit as a static library.
ARG LIBBACKTRACE_COMMIT=0b9b49cf4a2c9229fc052d6716e1528b2f23e91a
RUN curl -fsSL "https://github.com/ianlancetaylor/libbacktrace/archive/${LIBBACKTRACE_COMMIT}.tar.gz" \
        | tar -xz -C /tmp \
    && cd /tmp/libbacktrace-${LIBBACKTRACE_COMMIT} \
    && ./configure --prefix=/usr/local --disable-shared --with-pic \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/libbacktrace-${LIBBACKTRACE_COMMIT}

WORKDIR /src
COPY . .

# .dockerignore strips object files and the host-built binary so the
# build is reproducible.  setcap in the makefile is allowed to fail
# (- prefix) — inside a container we don't need raw-socket caps.
RUN make -j"$(nproc)" \
    && test -x linbpq

FROM debian:bookworm-slim AS runtime

# Runtime shared libraries matching the dev packages above.  Names are
# pinned to bookworm; refresh on a debian-version bump.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        libpaho-mqtt1.3 \
        libjansson4 \
        libminiupnpc17 \
        libconfig9 \
        libpcap0.8 \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/linbpq /usr/local/bin/linbpq
COPY --from=builder /src/HTML  /opt/linbpq/HTML
COPY docker/entrypoint.sh        /usr/local/bin/linbpq-entrypoint.sh
COPY docker/bpq32.cfg.example    /opt/linbpq/bpq32.cfg.example

# /data is the volume.  Users mount their bpq32.cfg here; runtime
# state (BPQNODES.dat, *.mes files, logs/, etc.) lands here too.
VOLUME ["/data"]
WORKDIR /data

# Common defaults — Telnet 8010, HTTP 8008.  Override in your cfg
# and re-publish as needed; EXPOSE is documentation only.
EXPOSE 8008/tcp 8010/tcp

ENTRYPOINT ["/usr/local/bin/linbpq-entrypoint.sh"]
# No default CMD: the entrypoint execs ``linbpq`` with whatever args
# you pass to ``docker run``.  Pass ``mail chat`` (or any subset) to
# enable the BBS / Chat subsystems — but only when the cfg actually
# registers BBSCALL / CHATCALL.  Starting them unconditionally claims
# AGW application slots and can hijack inbound 'C' frames destined
# for other APPLn registrations (issue #41).
