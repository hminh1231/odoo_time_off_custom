# Shared technical keys for handover workflow on hr.leave.

HANDOVER_ACTIVITY_XMLID = "time_off_work_handover.mail_act_leave_work_handover"
HANDOVER_ACTIVE_STATES = ("confirm", "validate1")
SKIP_SUBMIT_BOT_NOTIFY_CTX = "skip_handover_submit_bot_notify"
# Same key as time_off_responsible_approval (handover cancel must not double-notify outcome).
SKIP_OUTCOME_BOT_NOTIFY_CTX = "skip_outcome_bot_notify"

HANDOVER_ESCALATION_MINUTES = 5
HANDOVER_ESCALATION_TO_MANAGER_HOURS = 2
DEPARTMENT_HEAD_JOB_TITLE_KEY = "trưởng bộ phận"
DEPARTMENT_MANAGER_JOB_TITLE_KEY = "trưởng phòng"
