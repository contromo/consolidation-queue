from cq.eval.external.longmemeval.transfer import _followup_outcome
from tests.test_longmemeval_external_transfer import _followup_payloads

outcome = _followup_outcome(
    _followup_payloads(
        denominator=71,
        followup_hits=70,  # 70 >= min(70, 71)
        capped_hits=0,     # Reproduces readout loss
        sensitivity_followup_hits=70, # Stable across cells!
    )
)
print("Bucket:", outcome["bucket"])
print("Reason:", outcome["reason"])
