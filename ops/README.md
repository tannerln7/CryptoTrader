# Ops

Use this directory for deployment, service, and monitoring artifacts such as systemd units, container files, and operational helpers.

Keep long-lived runtime and deployment assets here rather than scattering them across the repo.

Current shipped assets include `ops/systemd/market-recorder@.service` and `ops/systemd/market-recorder.env.example` for systemd-based deployments.