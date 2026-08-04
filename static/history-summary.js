const MANUAL_REVIEW_CODES = new Set(["protected_subject", "reference_consistency", "view_adequacy"]);


export function historySummary(item) {
  const existingPatentChecks = item.patent_checks || [];
  const hasPatentResult = existingPatentChecks.length > 0 || Array.isArray(item.manual_review_checks);
  const manual_review_checks = item.manual_review_checks
    || existingPatentChecks.filter((check) => MANUAL_REVIEW_CODES.has(check.code));
  const patent_checks = existingPatentChecks.filter((check) => !MANUAL_REVIEW_CODES.has(check.code));
  const automaticStatuses = new Set(patent_checks.map((check) => check.status));
  const patent_precheck_status = !hasPatentResult
    ? null
    : item.manual_review_checks
      ? item.patent_precheck_status
      : automaticStatuses.has("fail")
        ? "fail"
        : automaticStatuses.has("review")
          ? "review"
          : "pass";
  const {
    id, title, part_type, parameters, structural_parameters, compliance,
    parser, parser_detail, step_url, spec_id, spec_url, generation_source,
    spec_fingerprint, core_elements, selected_components, multiviews,
    quality_score, semantic_assembly, review_status, reference_score, time,
  } = item;
  return {
    id, title, part_type, parameters, structural_parameters, compliance,
    patent_precheck_status, patent_checks, manual_review_checks, parser,
    parser_detail, step_url, spec_id, spec_url, generation_source,
    spec_fingerprint, core_elements, selected_components, multiviews,
    quality_score, semantic_assembly, review_status, reference_score, time,
  };
}


export function updatePatentPrecheckButton(button, status) {
  button.classList.remove("is-passed", "is-review", "is-failed");
  if (!status) {
    button.disabled = true;
    button.title = "该历史记录尚未执行专利附图预检";
    return;
  }
  button.disabled = false;
  button.classList.add(status === "pass" ? "is-passed" : status === "fail" ? "is-failed" : "is-review");
  button.title = status === "pass"
    ? "专利附图自动预检通过"
    : status === "fail"
      ? "专利附图自动预检发现明确形式问题"
      : "专利附图自动预检存在待人工确认项";
}
