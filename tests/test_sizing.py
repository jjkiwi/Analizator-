import pytest

from cfd.cli import main
from cfd.sizing import ContractSpec, load_contracts, position_size

SPEC = ContractSpec(lot_multiplier=50, currency="USD")


def test_basic_size_rounds_down_to_step():
    # ryzyko 1% z 10 000 = 100; strata 1 lota = 20 pkt * 50 = 1000 -> 0.10 lota
    r = position_size(entry=5000, sl=4980, risk_pct=1, equity=10_000, spec=SPEC)
    assert r.volume == pytest.approx(0.10)
    assert r.loss_at_sl == pytest.approx(100)
    r = position_size(entry=5000, sl=4983, risk_pct=1, equity=10_000, spec=SPEC)
    assert r.raw_volume == pytest.approx(100 / 850)
    assert r.volume == pytest.approx(0.11)
    assert r.loss_at_sl <= r.risk_amount  # zaokraglenie nigdy nie zwieksza ryzyka


def test_short_is_symmetric_and_fx_scales_loss():
    long = position_size(5000, 4980, 1, 10_000, SPEC)
    short = position_size(4980, 5000, 1, 10_000, SPEC)
    assert long.volume == short.volume
    pln = position_size(5000, 4980, 1, 10_000, SPEC, fx_rate=4.0)
    assert pln.loss_per_lot == pytest.approx(4000)
    assert pln.volume == pytest.approx(0.02)


def test_below_min_lot_gives_zero_and_flag():
    r = position_size(5000, 4000, 0.1, 1_000, SPEC)
    assert r.below_min_lot and r.volume == 0 and r.loss_at_sl == 0


@pytest.mark.parametrize("kw", [
    dict(entry=5000, sl=5000), dict(entry=-1, sl=10), dict(entry=10, sl=9, risk_pct=0),
    dict(entry=10, sl=9, risk_pct=101), dict(entry=10, sl=9, equity=0), dict(entry=10, sl=9, fx_rate=0),
])
def test_invalid_inputs_raise(kw):
    args = dict(entry=10, sl=9, risk_pct=1, equity=1000, spec=SPEC, fx_rate=1.0) | kw
    with pytest.raises(ValueError):
        position_size(**args)


def test_load_contracts(tmp_path):
    p = tmp_path / "contracts.yaml"
    p.write_text("contracts:\n  US500: {lot_multiplier: 50, currency: USD}\n", encoding="utf-8")
    assert load_contracts(p)["US500"].lot_step == 0.01
    assert load_contracts(tmp_path / "brak.yaml") == {}


def test_cli_size(tmp_path, capsys):
    (tmp_path / "instruments.yaml").write_text(
        "instruments:\n  - {symbol: US500, name: SP, category: indices, sources: {}}\n", encoding="utf-8")
    base = ["--config-dir", str(tmp_path), "size", "US500", "--entry", "5000", "--sl", "4980",
            "--risk-pct", "1", "--equity", "10000"]
    with pytest.raises(SystemExit) as e:  # brak specyfikacji -> jasny blad, nie zgadywanie
        main(base)
    assert "contracts.yaml" in str(e.value)
    main(base + ["--lot-multiplier", "50", "--currency", "USD", "--account-currency", "USD"])
    assert "0.10" in capsys.readouterr().out
    with pytest.raises(SystemExit) as e:  # inna waluta rachunku wymaga kursu
        main(base + ["--lot-multiplier", "50", "--currency", "USD", "--account-currency", "PLN"])
    assert "--fx-rate" in str(e.value)
