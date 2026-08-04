import json
import subprocess


def test_legacy_history_remains_unchecked_and_keeps_compliance():
    script = r'''
import { historySummary } from "./static/history-summary.js";
const summary = historySummary({
  id: "legacy-1",
  title: "旧版附图",
  compliance: [{name: "基础校验", passed: true}],
  time: "2026-08-01 10:00"
});
console.log(JSON.stringify(summary));
'''

    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(completed.stdout)

    assert summary["patent_precheck_status"] is None
    assert summary["compliance"] == [{"name": "基础校验", "passed": True}]


def test_unchecked_history_disables_and_clears_precheck_button():
    script = r'''
import { updatePatentPrecheckButton } from "./static/history-summary.js";
const classes = new Set(["is-passed"]);
const button = {
  disabled: false,
  title: "旧状态",
  classList: {
    add: (...names) => names.forEach((name) => classes.add(name)),
    remove: (...names) => names.forEach((name) => classes.delete(name)),
  },
};
updatePatentPrecheckButton(button, null);
console.log(JSON.stringify({disabled: button.disabled, title: button.title, classes: [...classes]}));
'''

    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    state = json.loads(completed.stdout)

    assert state == {
        "disabled": True,
        "title": "该历史记录尚未执行专利附图预检",
        "classes": [],
    }
