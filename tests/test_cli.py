import json

from scheme_checker.cli import main


def test_cli_farmer_text_output(capsys):
    main(["--state", "Gujarat", "--age", "35", "--gender", "Male",
          "--caste", "OBC", "--income", "120000", "--occupation", "farmer",
          "--land", "2.0"])
    out = capsys.readouterr().out
    assert "qualify for" in out
    assert "PM Kisan" in out


def test_cli_json_output(capsys):
    main(["--state", "Gujarat", "--age", "35", "--occupation", "farmer",
          "--land", "2.0", "--income", "120000", "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "count" in data
    assert data["count"] == len(data["schemes"])
    ids = {s["id"] for s in data["schemes"]}
    assert "pm_kisan" in ids


def test_cli_bpl_flag_unlocks_ayushman(capsys):
    main(["--state", "Maharashtra", "--age", "40", "--income", "50000",
          "--occupation", "daily_wage", "--bpl", "--json"])
    data = json.loads(capsys.readouterr().out)
    ids = {s["id"] for s in data["schemes"]}
    assert "ayushman_bharat" in ids


def test_cli_no_match(capsys):
    main(["--state", "Goa", "--age", "45", "--gender", "Male",
          "--caste", "General", "--income", "5000000",
          "--occupation", "salaried", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data["schemes"], list)
