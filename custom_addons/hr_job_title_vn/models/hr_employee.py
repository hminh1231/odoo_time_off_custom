from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from .hr_version import JOB_TITLE_SELECTION

_JOB_TITLE_RANK = {key: idx for idx, (key, _label) in enumerate(JOB_TITLE_SELECTION)}


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _job_title_rank(self, job_title):
        if not job_title or job_title not in _JOB_TITLE_RANK:
            return None
        return _JOB_TITLE_RANK[job_title]

    def _manager_rank_invalid_vs_employee(self):
        self.ensure_one()
        if not self.parent_id:
            return False
        r_emp = self._job_title_rank(self.job_title)
        r_mgr = self._job_title_rank(self.parent_id.job_title)
        if r_emp is None or r_mgr is None:
            return False
        return r_mgr < r_emp

    def _ensure_manager_not_below_subordinate(self):
        self.ensure_one()
        if not self._manager_rank_invalid_vs_employee():
            return
        labels = dict(JOB_TITLE_SELECTION)
        raise ValidationError(
            _(
                "Invalid reporting line: “%(employee)s” (%(emp_title)s) cannot report to “%(manager)s” "
                "(%(mgr_title)s). The manager’s job title must be equal or higher on the company scale than "
                "the employee’s (organization chart follows the job title order).",
                employee=self.name,
                emp_title=labels.get(self.job_title, self.job_title or "-"),
                manager=self.parent_id.name,
                mgr_title=labels.get(self.parent_id.job_title, self.parent_id.job_title or "-"),
            )
        )

    @api.onchange("parent_id", "job_title")
    def _onchange_warn_manager_job_title_order(self):
        if not self._manager_rank_invalid_vs_employee():
            return
        labels = dict(JOB_TITLE_SELECTION)
        emp_lbl = labels.get(self.job_title, self.job_title or "-")
        mgr_lbl = labels.get(self.parent_id.job_title, self.parent_id.job_title or "-")
        return {
            "warning": {
                "title": _("Chức danh quản lý"),
                "message": _(
                    "Không thể chọn người có chức danh thấp hơn làm Quản lý. "
                    "Trên org chart, quản lý phải có bậc chức danh bằng hoặc cao hơn người được quản lý.\n"
                    "Hiện: %(emp)s — %(emp_lbl)s; Quản lý chọn: %(mgr)s — %(mgr_lbl)s.",
                    emp=self.name or "—",
                    emp_lbl=emp_lbl,
                    mgr=self.parent_id.name,
                    mgr_lbl=mgr_lbl,
                ),
            }
        }

    def _check_manager_job_title_hierarchy(self):
        for emp in self:
            emp._ensure_manager_not_below_subordinate()
            for sub in emp.child_ids:
                sub._ensure_manager_not_below_subordinate()

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._check_manager_job_title_hierarchy()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ("parent_id", "job_title")):
            self._check_manager_job_title_hierarchy()
        return res
