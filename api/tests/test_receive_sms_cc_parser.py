from services.receive_sms_cc_parser import (
    amazon_history_on_inbox,
    latest_amazon_otp,
    parse_receive_sms_cc_html,
)

SAMPLE = """
<div class="row list-message">
  <div class="col-12">
    <div class="item">
      <div class="form">From <a href="/Receive-SMS-From/Amazon">Amazon</a></div>
      <span class="time">7 seconds ago</span>
      <div class="con">265076 est votre mot de passe  usage unique Amazon. Ne le partagez pas.</div>
    </div>
  </div>
</div>
"""


def test_parse_amazon_otp() -> None:
    msgs = parse_receive_sms_cc_html(SAMPLE)
    assert len(msgs) == 1
    assert msgs[0].is_amazon
    assert amazon_history_on_inbox(msgs)
    assert latest_amazon_otp(msgs) == "265076"
