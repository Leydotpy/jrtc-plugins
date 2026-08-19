# jrtc-sip

An independently installable, fully typed async client for
`janus.plugin.sip`. It depends on `jrtc` and does not install any
other named Janus plugin.

```python
from jrtc.models.base import Jsep
from jrtc_sip import SipPlugin

sip = SipPlugin(session=session)
await sip.attach()
await sip.register_account(
    "sip:alice@example.com",
    secret="password",
    proxy="sip:registrar.example.com",
)
await sip.call(
    "sip:bob@example.com",
    Jsep(type="offer", sdp=offer_sdp),
)
```

Registration validates SIP/SIPS URIs, authentication choice, guest/helper
semantics, transport conflicts, and registration lifetime. A normal account
requires exactly one of `secret` and `ha1_secret`; `authuser` overrides the URI
username for digest authentication. Guest calls can provide credentials on the
`call` request. Helpers use the master account's returned `master_id`.

The client covers every documented SIP operation: registration, calls,
offerless-invite progress/accept flows, renegotiation, decline/hangup,
hold/unhold, MESSAGE, INFO/DTMF, subscriptions, blind/attended transfers,
recording, keyframes, and RTP forwarders. JSEP remains in the outer Janus
envelope and is never mixed into plugin data; `update()` automatically marks
its JSEP as a Janus renegotiation. RTP-forwarder helpers expose the optional
`unique_id` and configured `admin_key` controls from the current gateway.

Models follow the official [SIP API](https://janus.conf.meetecho.com/docs/sip.html)
and the current Janus implementation. Outbound objects reject unknown fields;
inbound events retain future fields and unknown event variants.
