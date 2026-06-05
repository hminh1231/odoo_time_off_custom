MULTI_STEP_RESET_CTX = "time_off_multi_step_reset_skip"
SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX = "skip_responsible_submit_notify"
SKIP_OUTCOME_BOT_NOTIFY_CTX = "skip_outcome_bot_notify"
SKIP_SPLIT_GROUP_NOTIFY_DEDUP_CTX = "skip_split_group_notify_dedupe"

MAX_EMPLOYEE_HR_RESPONSIBLES = 15
MAX_EMPLOYEE_HR_RESPONSIBLES_MULTI_DIRECTOR = 40
DIRECTOR_JOB_TITLE_KEY = "giám đốc"
# Leave validations that use responsible_approval_line_ids + OdooBot skip/remind rules.
RESPONSIBLE_APPROVAL_VALIDATION_TYPES = ("employee_hr_responsibles", "vp_chain")
