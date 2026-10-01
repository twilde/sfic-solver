"""Repository settings on GitHub that protect users from leaking real key data."""
import re

from conftest import ROOT

FORMS = sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
ISSUE_FORMS = [p for p in FORMS if p.name != "config.yml"]


def test_blank_issues_are_disabled():
    text = (ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text()
    assert re.search(r"^blank_issues_enabled: false$", text, re.M)


def test_there_are_issue_forms():
    assert {p.name for p in ISSUE_FORMS} >= {"bug_report.yml", "feature_request.yml"}


def test_every_issue_form_warns_and_requires_the_checkbox():
    for form in ISSUE_FORMS:
        text = form.read_text()
        assert "Never post real key data" in text, form.name
        assert "type: checkboxes" in text, form.name
        # the checkbox option must be required
        option = re.search(r"- label: I have not included real bittings.*\n\s+required: true", text)
        assert option, f"{form.name}: the no-real-data checkbox must be required"


def test_readme_repeats_the_issue_warning():
    text = (ROOT / "README.md").read_text()
    assert "Issues and pull requests are public too" in text


def test_dependabot_keeps_github_actions_current():
    text = (ROOT / ".github" / "dependabot.yml").read_text()
    assert re.search(r'package-ecosystem: "github-actions"', text)
    assert re.search(r'interval: "weekly"', text)


def test_security_policy_exists_and_is_consistent():
    text = (ROOT / "SECURITY.md").read_text()
    assert "Report a vulnerability" in text
    assert "never post real key data" in text.lower()
    assert "@" not in text                     # no personal email address published
    assert "[SECURITY.md](SECURITY.md)" in (ROOT / "README.md").read_text()
