# External evaluation data

ABCD is not committed into this repository. Download `abcd_v1.1.json.gz` from the official
ASAPP ABCD repository and pass its local path to `load_abcd_subset`.

- Source: https://github.com/asappresearch/abcd
- License: MIT (verify the upstream repository before redistribution)
- Intended use here: external conversation, interaction-act, route and action evaluation
- Not used as linked EcomDispute order/payment/logistics records

The adapter deterministically selects up to 50 dialogues from refund, return, shipping,
delivery-time and returned-item billing subflows. It preserves the upstream conversation ID,
split, flow, subflow and action annotations.

