# Security requirements

## Untrusted configuration

Never accept arbitrary FFmpeg arguments, GStreamer pipeline strings, shell
fragments, executable paths, environment names, or local file paths from an
untrusted client. Public configuration selects an administrator-defined profile.
All process execution uses argument vectors and `shell=False` semantics.

## Source locators and SSRF

Before probing or opening an RTSP/HTTP source, enforce allowed schemes, hosts,
CIDRs, DNS resolutions, redirect targets, ports, and time budgets. Block
loopback, link-local, cloud metadata, and internal control-plane destinations
unless explicitly required. Run probes in a restricted media worker network.

## Secrets

The core stores references, not values. The Janus bridge accepts injected
secret and RTSP credential resolvers. Do not put passwords, Janus admin keys,
mountpoint secrets, SRS tokens, SDP, or ICE candidates in labels, metadata,
ordinary logs, or browser-visible responses.

## Publishing

An issued SRS token is useful only when a reverse proxy or callback layer
validates it. Authenticate callback senders, enforce replay/idempotency rules,
use short expirations, and verify app/stream/protocol claims.

## RTP

Plain RTP/UDP lacks application authentication. Use private networking,
firewalls, source restrictions, or SRTP where appropriate. Treat port leases as
security-sensitive capacity resources.

## Application authorization

Django/GUI/API layers must authorize every stream command. Administrative
mountpoint operations and viewer signaling are separate privileges. Never allow
a client to submit an arbitrary Janus plugin body.

## Supply chain

Pin tested dependency ranges, review lockfile changes, build with isolated
backends, produce hashes/SBOMs for releases, and scan both Python packages and
media-worker images.
