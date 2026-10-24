from jira_analytics.charts import build_reports
from test_analysis import issue


def test_build_six_report_families(tmp_path):
    """Integration check: analytics output is an HTML document with all six chart types."""
    result = build_reports([issue()], {"KAFKA-1": {"Open": 24}}, tmp_path, project="KAFKA")
    html = result.read_text(encoding="utf-8")
    assert all(f"0{index}_" in html for index in range(1, 7))
    assert len(list(tmp_path.glob("*.png"))) == 6
