import json
from datetime import date

from odoo import _, fields, http
from odoo.fields import Command
from odoo.http import request
from odoo.osv import expression
from markupsafe import Markup, escape

from .base_api import FtiqCrmApiBase


class FtiqCrmMobileApi(FtiqCrmApiBase):
    @http.route("/api/dashboard/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def dashboard(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._dashboard))

    @http.route("/api/leads/", type="http", auth="none", methods=["GET", "POST"], cors="*", csrf=False)
    def leads(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._leads))

    @http.route("/api/leads/<int:lead_id>/", type="http", auth="none", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], cors="*", csrf=False)
    def lead_detail(self, lead_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._lead_detail(lead_id)))

    @http.route("/api/leads/comment/<int:comment_id>/", type="http", auth="none", methods=["DELETE"], cors="*", csrf=False)
    def lead_comment(self, comment_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._delete_message(comment_id)))

    @http.route("/api/opportunities/", type="http", auth="none", methods=["GET", "POST"], cors="*", csrf=False)
    def opportunities(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._opportunities))

    @http.route("/api/opportunities/<int:opportunity_id>/", type="http", auth="none", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], cors="*", csrf=False)
    def opportunity_detail(self, opportunity_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._opportunity_detail(opportunity_id)))

    @http.route("/api/tasks/", type="http", auth="none", methods=["GET", "POST"], cors="*", csrf=False)
    def tasks(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._tasks))

    @http.route("/api/tasks/<int:task_id>/", type="http", auth="none", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], cors="*", csrf=False)
    def task_detail(self, task_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._task_detail(task_id)))

    @http.route("/api/tasks/<int:task_id>/execution/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def task_execution(self, task_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._task_execution(task_id)))

    @http.route("/api/tasks/<int:task_id>/visit/start/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def task_visit_start(self, task_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._task_visit_start(task_id)))

    @http.route("/api/tasks/<int:task_id>/visit/draft/", type="http", auth="none", methods=["POST", "PATCH"], cors="*", csrf=False)
    def task_visit_draft(self, task_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._task_visit_draft(task_id)))

    @http.route("/api/tasks/<int:task_id>/visit/complete/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def task_visit_complete(self, task_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._task_visit_complete(task_id)))

    @http.route("/api/tasks/<int:task_id>/visit/cancel/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def task_visit_cancel(self, task_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._task_visit_cancel(task_id)))

    @http.route("/api/accounts/", type="http", auth="none", methods=["GET", "POST"], cors="*", csrf=False)
    def accounts(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._accounts))

    @http.route("/api/contacts/", type="http", auth="none", methods=["GET", "POST"], cors="*", csrf=False)
    def contacts(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._contacts))

    @http.route("/api/users/get-teams-and-users/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def teams_and_users(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._teams_and_users))

    @http.route("/api/tags/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def tags(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._tags))

    @http.route("/api/cases/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def cases(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._cases))

    @http.route("/api/invoices/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def invoices(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._invoices))

    def _with_auth(self, callback):
        self._authenticate()
        return callback()

    def _leads(self):
        if request.httprequest.method == "POST":
            payload = self._json_body()
            lead = request.env["crm.lead"].create(self._lead_values(payload))
            self._write_crm_relations(lead, payload)
            self._apply_mobile_location(lead, payload)
            return self._ok_message(_("Lead Created Successfully"))
        limit, offset = self._limit_offset()
        search = self._arg("search")
        domain = [("type", "=", "lead")]
        if search:
            domain = expression.AND([
                domain,
                self._domain_for_search(["name", "contact_name", "partner_name", "email_from"], search),
            ])
        status_value = self._arg("status")
        if status_value == "closed":
            domain.append(("active", "=", False))
        source_value = self._arg("source")
        if source_value:
            source = self._source_from_value(source_value, create=False)
            if source:
                domain.append(("source_id", "=", source.id))
        open_domain = expression.AND([domain, [("active", "=", True)]])
        close_domain = expression.AND([domain, [("active", "=", False)]])
        open_count = self._safe_search_count("crm.lead", open_domain, active_test=False)
        close_count = self._safe_search_count("crm.lead", close_domain, active_test=False)
        open_records = self._safe_search(
            "crm.lead",
            open_domain,
            order="id desc",
            limit=limit,
            offset=offset,
            active_test=False,
        )
        close_records = self._safe_search(
            "crm.lead",
            close_domain,
            order="id desc",
            limit=limit,
            offset=offset,
            active_test=False,
        )
        return self._json(
            {
                "per_page": limit,
                "page_number": int(offset / limit) + 1,
                "open_leads": {
                    "leads_count": open_count,
                    "open_leads": [self._serialize_lead(lead) for lead in open_records],
                    "offset": offset + len(open_records) if offset + len(open_records) < open_count else None,
                },
                "close_leads": {
                    "leads_count": close_count,
                    "close_leads": [self._serialize_lead(lead) for lead in close_records],
                    "offset": offset + len(close_records) if offset + len(close_records) < close_count else None,
                },
                "contacts": [
                    {
                        "id": str(partner.id),
                        "first_name": self._split_name(
                            self._field_value(partner, "name", "") or ""
                        )[0],
                    }
                    for partner in self._contact_records(limit=100)
                ],
                "status": self._lead_status_choices(),
                "source": self._lead_source_choices(),
                "tags": [self._serialize_tag(tag) for tag in self._crm_tags()],
                "users": [
                    {"id": str(user.id), "user__email": user.login or user.email or ""}
                    for user in self._assignable_users()
                ],
                "countries": self._country_choices(),
                "industries": [],
            }
        )

    def _lead_detail(self, lead_id):
        lead = request.env["crm.lead"].with_context(active_test=False).search(
            [("id", "=", lead_id), ("type", "=", "lead")],
            limit=1,
        )
        if not lead:
            return self._error(_("Lead not found."), status=404)
        method = request.httprequest.method
        if method == "GET":
            return self._json(self._lead_detail_payload(lead))
        if method == "POST":
            payload = self._json_body()
            comment = (payload.get("comment") or "").strip()
            if comment:
                lead.message_post(body=comment)
            return self._json(self._lead_detail_payload(lead))
        if method == "DELETE":
            lead.unlink()
            return self._ok_message(_("Lead deleted Successfully"))
        payload = self._json_body()
        values = self._lead_values(payload, existing=lead, partial=method == "PATCH")
        if values:
            lead.write(values)
        self._write_crm_relations(lead, payload)
        self._apply_mobile_location(lead, payload)
        if payload.get("status") == "converted":
            lead.write({"type": "opportunity"})
            return self._ok_message(
                _("Lead Converted Successfully"),
                opportunity_id=str(lead.id),
                account_id=str(lead.partner_id.commercial_partner_id.id) if lead.partner_id else None,
                contact_id=str(lead.partner_id.id) if lead.partner_id else None,
            )
        return self._ok_message(_("Lead updated Successfully"))

    def _lead_detail_payload(self, lead):
        users = self._assignable_users()
        lead_user = self._field_value(lead, "user_id")
        teams = self._safe_search("crm.team", order="sequence, id")
        return {
            "lead_obj": self._serialize_lead(lead),
            "attachments": [],
            "comments": self._serialize_messages(lead),
            "users_mention": [{"user__email": user.login or user.email or ""} for user in users],
            "assigned_data": self._assigned_users(lead_user) if lead_user else [],
            "users": [self._serialize_profile(user) for user in users],
            "users_excluding_team": [self._serialize_profile(user) for user in users],
            "source": self._lead_source_choices(),
            "status": self._lead_status_choices(),
            "teams": [self._serialize_team(team) for team in teams],
            "countries": self._country_choices(),
        }

    def _opportunities(self):
        if request.httprequest.method == "POST":
            payload = self._json_body()
            opportunity = request.env["crm.lead"].create(self._opportunity_values(payload))
            self._write_crm_relations(opportunity, payload)
            self._apply_mobile_location(opportunity, payload)
            return self._ok_message(_("Opportunity Created Successfully"))
        limit, offset = self._limit_offset()
        domain = [("type", "=", "opportunity")]
        search = self._arg("name") or self._arg("search")
        if search:
            domain = expression.AND([domain, self._domain_for_search(["name", "partner_name"], search)])
        stage_value = self._arg("stage")
        if stage_value:
            if stage_value == "CLOSED_LOST":
                domain.append(("active", "=", False))
            else:
                stage = self._stage_from_deal_code(stage_value, create=False)
                if stage:
                    domain.append(("stage_id", "=", stage.id))
        count = self._safe_search_count("crm.lead", domain, active_test=False)
        records = self._safe_search(
            "crm.lead",
            domain,
            order="id desc",
            limit=limit,
            offset=offset,
            active_test=False,
        )
        return self._json(
            {
                "opportunities_count": count,
                "offset": offset + len(records) if offset + len(records) < count else None,
                "per_page": limit,
                "page_number": int(offset / limit) + 1,
                "opportunities": [self._serialize_opportunity(lead) for lead in records],
                "accounts_list": [self._serialize_partner_account(partner) for partner in self._account_records(limit=100)],
                "contacts_list": [self._serialize_partner_contact(partner) for partner in self._contact_records(limit=100)],
                "tags": [self._serialize_tag(tag) for tag in self._crm_tags()],
                "stage": self._deal_stage_choices(),
                "lead_source": self._opportunity_source_choices(),
                "currency": self._currency_choices(),
            }
        )

    def _opportunity_detail(self, opportunity_id):
        opportunity = request.env["crm.lead"].with_context(active_test=False).search(
            [("id", "=", opportunity_id), ("type", "=", "opportunity")],
            limit=1,
        )
        if not opportunity:
            return self._error(_("Opportunity not found."), status=404)
        method = request.httprequest.method
        if method == "GET":
            return self._json(self._opportunity_detail_payload(opportunity))
        if method == "POST":
            payload = self._json_body()
            comment = (payload.get("comment") or "").strip()
            if comment:
                opportunity.message_post(body=comment)
            return self._json(self._opportunity_detail_payload(opportunity))
        if method == "DELETE":
            opportunity.unlink()
            return self._ok_message(_("Opportunity Deleted Successfully."))
        payload = self._json_body()
        values = self._opportunity_values(payload, existing=opportunity, partial=method == "PATCH")
        if values:
            opportunity.write(values)
        self._write_crm_relations(opportunity, payload)
        self._apply_mobile_location(opportunity, payload)
        return self._ok_message(_("Opportunity Updated Successfully"))

    def _opportunity_detail_payload(self, opportunity):
        users = self._assignable_users()
        partner = self._field_value(opportunity, "partner_id")
        return {
            "opportunity_obj": self._serialize_opportunity(opportunity),
            "comments": self._serialize_messages(opportunity),
            "attachments": [],
            "contacts": [self._serialize_partner_contact(partner)] if partner else [],
            "users": [self._serialize_profile(user) for user in users],
            "stage": self._deal_stage_choices(),
            "lead_source": self._opportunity_source_choices(),
            "currency": self._currency_choices(),
            "comment_permission": True,
            "users_mention": [{"user__email": user.login or user.email or ""} for user in users],
        }

    def _tasks(self):
        if request.httprequest.method == "POST":
            payload = self._json_body()
            task = request.env["project.task"].create(self._task_values(payload))
            self._apply_mobile_location(task, payload)
            return self._ok_message(_("Task Created Successfully"))
        limit, offset = self._limit_offset()
        domain = self._mobile_task_visibility_domain()
        search = self._arg("search") or self._arg("title")
        if search:
            domain = expression.AND([domain, self._domain_for_search(["name"], search)])
        priority = self._arg("priority")
        if priority:
            domain.append(("priority", "=", self._priority_to_odoo(priority)))
        status_value = self._arg("status")
        if status_value:
            state = self._task_state_from_status(status_value)
            if state:
                domain.append(("state", "=", state))
        else:
            domain = expression.AND([domain, self._mobile_open_task_domain()])
        count = self._safe_search_count("project.task", domain)
        records = self._safe_search(
            "project.task",
            domain,
            order="id desc",
            limit=limit,
            offset=offset,
        )
        return self._json(
            {
                "tasks_count": count,
                "offset": offset + len(records) if offset + len(records) < count else None,
                "tasks": [self._serialize_task(task) for task in records],
                "status": self._task_status_choices(),
                "priority": self._task_priority_choices(),
                "task_types": self._task_type_choices(),
                "accounts_list": [self._serialize_partner_account(partner) for partner in self._account_records(limit=100)],
                "contacts_list": [self._serialize_partner_contact(partner) for partner in self._contact_records(limit=100)],
            }
        )

    def _task_detail(self, task_id):
        task = request.env["project.task"].search(
            expression.AND([
                [("id", "=", task_id)],
                self._mobile_task_visibility_domain(),
            ]),
            limit=1,
        )
        if not task:
            return self._error(_("Task not found."), status=404)
        method = request.httprequest.method
        if method == "GET":
            return self._json(self._task_detail_payload(task))
        if method == "POST":
            payload = self._json_body()
            comment = (payload.get("comment") or "").strip()
            if comment:
                task.message_post(body=comment)
            return self._json(self._task_detail_payload(task))
        if method == "DELETE":
            task.unlink()
            return self._json({}, status=204)
        payload = self._json_body()
        values = self._task_values(payload, existing=task, partial=method == "PATCH")
        if values:
            task.write(values)
        self._apply_mobile_location(task, payload)
        return self._ok_message(_("Task updated Successfully"))

    def _task_detail_payload(self, task):
        users = self._assignable_users()
        assigned_users = self._field_value(task, "user_ids") or request.env["res.users"]
        teams = self._safe_search("crm.team", order="sequence, id")
        return {
            "task_obj": self._serialize_task(task),
            "attachments": [],
            "comments": self._serialize_messages(task),
            "users_mention": [{"user__email": user.login or user.email or ""} for user in users],
            "assigned_data": self._assigned_users(assigned_users),
            "users": [self._serialize_profile(user) for user in users],
            "users_excluding_team": [self._serialize_profile(user) for user in users],
            "teams": [self._serialize_team(team) for team in teams],
            "available_tags": [self._serialize_tag(tag) for tag in self._project_task_tags()],
            "task_types": self._task_type_choices(),
            "visit_states": self._task_visit_state_choices(),
            "execution": self._task_execution_payload(task),
        }

    def _task_execution(self, task_id):
        task = self._task_record_for_mobile(task_id)
        if not task:
            return self._error(_("Task not found."), status=404)
        return self._json(self._task_execution_response(task))

    def _task_visit_start(self, task_id):
        task = self._task_record_for_mobile(task_id)
        if not task:
            return self._error(_("Task not found."), status=404)
        if not self._field_value(task, "partner_id"):
            return self._error(_("This task is not linked to a client."), status=400)
        payload = self._json_body()
        now = fields.Datetime.now()
        values = {
            "ftiq_mobile_task_type": self._field_value(task, "ftiq_mobile_task_type") or "field_visit",
            "ftiq_mobile_visit_state": "in_progress",
            "ftiq_mobile_started_at": now,
        }
        values.update(self._task_location_values(payload, "start"))
        state = self._task_state_from_status("01_in_progress")
        if state:
            values["state"] = state
        self._write_mobile_task_values(task, values)
        self._apply_mobile_location(task, payload)
        task.message_post(
            body=self._task_visit_message_body(
                task,
                self._task_execution_event_title(task, _("Visit started"), _("Stock audit started")),
                payload=payload,
            )
        )
        return self._json(self._task_execution_response(task))

    def _task_visit_draft(self, task_id):
        task = self._task_record_for_mobile(task_id)
        if not task:
            return self._error(_("Task not found."), status=404)
        payload = self._json_body()
        draft = payload.get("draft")
        if not isinstance(draft, dict):
            draft = payload.get("execution")
        if not isinstance(draft, dict):
            draft = payload
        values = {
            "ftiq_mobile_execution_payload": json.dumps(draft or {}, ensure_ascii=False),
        }
        if self._field_value(task, "ftiq_mobile_visit_state") in (False, "", "not_started"):
            values["ftiq_mobile_visit_state"] = "in_progress"
            values["ftiq_mobile_started_at"] = fields.Datetime.now()
        self._write_mobile_task_values(task, values)
        return self._json(self._task_execution_response(task))

    def _task_visit_complete(self, task_id):
        task = self._task_record_for_mobile(task_id)
        if not task:
            return self._error(_("Task not found."), status=404)
        payload = self._json_body()
        request_uid = (payload.get("mobile_request_uid") or payload.get("request_uid") or "").strip()
        if request_uid and self._field_value(task, "ftiq_mobile_request_uid") == request_uid:
            return self._json(self._task_execution_response(task))
        report = payload.get("report")
        if not isinstance(report, dict):
            report = payload.get("execution")
        if not isinstance(report, dict):
            report = payload
        now = fields.Datetime.now()
        values = {
            "ftiq_mobile_execution_payload": json.dumps(report or {}, ensure_ascii=False),
            "ftiq_mobile_visit_state": "completed",
            "ftiq_mobile_completed_at": now,
        }
        if request_uid:
            values["ftiq_mobile_request_uid"] = request_uid
        if not self._field_value(task, "ftiq_mobile_started_at"):
            values["ftiq_mobile_started_at"] = now
        values.update(self._task_location_values(payload, "end"))
        done_state = self._task_state_from_status("1_done")
        if done_state:
            values["state"] = done_state
        self._write_mobile_task_values(task, values)
        self._apply_mobile_location(task, payload)
        task.message_post(
            body=self._task_visit_message_body(
                task,
                self._task_execution_event_title(task, _("Visit completed"), _("Stock audit completed")),
                payload=payload,
                report=report,
            )
        )
        return self._json(self._task_execution_response(task))

    def _task_visit_cancel(self, task_id):
        task = self._task_record_for_mobile(task_id)
        if not task:
            return self._error(_("Task not found."), status=404)
        payload = self._json_body()
        reason = (payload.get("reason") or "").strip()
        values = {
            "ftiq_mobile_visit_state": "cancelled",
            "ftiq_mobile_completed_at": fields.Datetime.now(),
        }
        values.update(self._task_location_values(payload, "end"))
        state = self._task_state_from_status("1_canceled")
        if state:
            values["state"] = state
        self._write_mobile_task_values(task, values)
        self._apply_mobile_location(task, payload)
        task.message_post(
            body=self._task_visit_message_body(
                task,
                self._task_execution_event_title(task, _("Visit cancelled"), _("Stock audit cancelled")),
                payload=payload,
                report={"reason": reason} if reason else {},
            )
        )
        return self._json(self._task_execution_response(task))

    def _task_record_for_mobile(self, task_id):
        return request.env["project.task"].search(
            expression.AND([
                [("id", "=", task_id)],
                self._mobile_task_visibility_domain(),
            ]),
            limit=1,
        )

    def _task_selection_options(self, field_name):
        Task = request.env["project.task"]
        if field_name not in Task._fields:
            return []
        field = Task._fields[field_name]
        selection = (
            field._description_selection(request.env)
            if hasattr(field, "_description_selection")
            else field.selection
        )
        return [
            {"value": value, "label": label, "sequence": index}
            for index, (value, label) in enumerate(selection or [])
        ]

    def _task_type_choices(self):
        choices = self._task_selection_options("ftiq_mobile_task_type")
        if choices:
            return choices
        return [
            {"value": "field_visit", "label": "Field Visit", "sequence": 0},
            {"value": "collection", "label": "Collection", "sequence": 1},
            {"value": "sales_order", "label": "Sales Order", "sequence": 2},
            {"value": "stock_audit", "label": "Customer Stock Audit", "sequence": 3},
        ]

    def _task_visit_state_choices(self):
        choices = self._task_selection_options("ftiq_mobile_visit_state")
        if choices:
            return choices
        return [
            {"value": "not_started", "label": "Not Started", "sequence": 0},
            {"value": "in_progress", "label": "In Progress", "sequence": 1},
            {"value": "completed", "label": "Completed", "sequence": 2},
            {"value": "cancelled", "label": "Cancelled", "sequence": 3},
        ]

    def _task_execution_payload(self, task):
        raw = self._field_value(task, "ftiq_mobile_execution_payload", "") or ""
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _task_execution_response(self, task):
        partner = self._field_value(task, "partner_id")
        return {
            "task_obj": self._serialize_task(task),
            "task": self._serialize_task(task),
            "client": self._serialize_partner_account(partner) if partner else None,
            "task_types": self._task_type_choices(),
            "visit_states": self._task_visit_state_choices(),
            "execution": self._task_execution_payload(task),
        }

    def _task_execution_event_title(self, task, visit_title, stock_audit_title):
        task_type = self._field_value(task, "ftiq_mobile_task_type") or ""
        return stock_audit_title if task_type == "stock_audit" else visit_title

    def _write_mobile_task_values(self, task, values):
        filtered = {
            key: value
            for key, value in (values or {}).items()
            if key in task._fields
        }
        if filtered:
            task.with_context(ftiq_mobile_location_write=True).write(filtered)

    def _task_location_values(self, payload, prefix):
        location_values = self._location_payload(payload)
        if not location_values:
            return {}
        mapping = {
            "ftiq_mobile_latitude": "ftiq_mobile_%s_latitude" % prefix,
            "ftiq_mobile_longitude": "ftiq_mobile_%s_longitude" % prefix,
            "ftiq_mobile_accuracy": "ftiq_mobile_%s_accuracy" % prefix,
            "ftiq_mobile_is_mock": "ftiq_mobile_%s_is_mock" % prefix,
        }
        Task = request.env["project.task"]
        return {
            target: location_values[source]
            for source, target in mapping.items()
            if source in location_values and target in Task._fields
        }

    def _task_visit_message_body(self, task, title, payload=None, report=None):
        payload = payload or {}
        report = report or {}
        location = self._location_payload(payload)
        latitude = location.get("ftiq_mobile_latitude") or self._field_value(task, "ftiq_mobile_latitude")
        longitude = location.get("ftiq_mobile_longitude") or self._field_value(task, "ftiq_mobile_longitude")
        accuracy = location.get("ftiq_mobile_accuracy") or self._field_value(task, "ftiq_mobile_accuracy")
        is_mock = location.get("ftiq_mobile_is_mock") or self._field_value(task, "ftiq_mobile_is_mock")
        recorded_at = location.get("ftiq_mobile_location_at") or self._field_value(task, "ftiq_mobile_location_at")
        partner = self._field_value(task, "partner_id")
        task_type = self._field_value(task, "ftiq_mobile_task_type") or "field_visit"
        task_type_labels = {item["value"]: item["label"] for item in self._task_type_choices()}
        outcome = report.get("outcome") or report.get("customer_interest") or ""
        summary = report.get("summary") or report.get("notes") or ""
        products = report.get("products") if isinstance(report.get("products"), list) else []
        stock_lines = report.get("stock_lines") if isinstance(report.get("stock_lines"), list) else []
        product_ids = []
        for product in products:
            if isinstance(product, dict):
                try:
                    product_id = int(product.get("product_id") or product.get("id") or 0)
                    if product_id:
                        product_ids.append(product_id)
                except Exception:
                    continue
        product_records = request.env["product.product"].sudo().browse(product_ids).exists()
        products_by_id = {str(product.id): product for product in product_records}
        stock_product_ids = []
        for line in stock_lines:
            if not isinstance(line, dict):
                continue
            try:
                product_id = int(line.get("product_id") or 0)
                if product_id:
                    stock_product_ids.append(product_id)
            except Exception:
                continue
        stock_product_records = request.env["product.product"].sudo().browse(stock_product_ids).exists()
        stock_products_by_id = {str(product.id): product for product in stock_product_records}

        product_rows = ""
        for product in products:
            if not isinstance(product, dict):
                continue
            product_id = str(product.get("product_id") or product.get("id") or "")
            product_record = products_by_id.get(product_id)
            default_code = product.get("default_code") or (product_record.default_code if product_record else "")
            product_name = product.get("name") or product.get("product_name") or (
                product_record.display_name if product_record else ""
            )
            product_label = "[%s] %s" % (default_code, product_name) if default_code else product_name
            product_image_src = ""
            if product_record:
                product_image_src = "/web/image/product.product/%s/image_128" % product_record.id
            elif product.get("image_base64"):
                product_image_src = "data:image/png;base64,%s" % product.get("image_base64")
            product_image = (
                "<img src='%s' alt='%s' style='width:48px;height:48px;object-fit:cover;"
                "border-radius:8px;border:1px solid #dbe3ef;background:#f8fafc;'/>"
                % (escape(product_image_src), escape(product_label or _("Product")))
                if product_image_src
                else (
                    "<div style='width:48px;height:48px;border-radius:8px;background:#e8f1ff;"
                    "border:1px solid #cfe0ff;color:#1d4ed8;display:flex;align-items:center;"
                    "justify-content:center;font-weight:700;'>%s</div>" % escape(_("Product"))
                )
            )
            product_rows += (
                "<tr style='background:#ffffff;'>"
                "<td style='padding:10px;border-bottom:1px solid #e5e7eb;width:58px;'>%s</td>"
                "<td style='padding:10px;border-bottom:1px solid #e5e7eb;font-weight:700;color:#111827;'>%s"
                "<div style='font-weight:400;color:#111827;font-size:12px;margin-top:2px;'>%s</div></td>"
                "<td style='padding:10px;border-bottom:1px solid #e5e7eb;color:#111827;font-weight:600;'>%s</td>"
                "<td style='padding:10px;border-bottom:1px solid #e5e7eb;color:#111827;'>%s</td>"
                "</tr>"
            ) % (
                product_image,
                escape(product_label),
                escape(product.get("uom_name") or ""),
                escape(product.get("interest") or ""),
                escape(product.get("notes") or ""),
            )
        products_table = ""
        if product_rows:
            products_table = (
                "<div style='margin-top:14px;border:1px solid #bbf7d0;border-radius:12px;overflow:hidden;background:#f0fdf4;'>"
                "<div style='padding:10px 12px;background:#dcfce7;color:#111827;font-weight:800;'>%s</div>"
                "<table style='width:100%%;border-collapse:collapse;background:white;'>"
                "<thead><tr style='background:#ecfdf5;color:#111827;'>"
                "<th style='padding:8px 10px;text-align:right;width:58px;'>%s</th>"
                "<th style='padding:8px 10px;text-align:right;'>%s</th>"
                "<th style='padding:8px 10px;text-align:right;'>%s</th>"
                "<th style='padding:8px 10px;text-align:right;'>%s</th>"
                "</tr></thead><tbody>%s</tbody></table></div>"
            ) % (
                escape(_("Products shown")),
                escape(_("Image")),
                escape(_("Product")),
                escape(_("Interest")),
                escape(_("Notes")),
                product_rows,
            )
        stock_line_rows = ""
        for line in stock_lines:
            if not isinstance(line, dict):
                continue
            product_id = str(line.get("product_id") or "")
            product_record = stock_products_by_id.get(product_id)
            default_code = line.get("default_code") or (product_record.default_code if product_record else "")
            product_name = line.get("name") or line.get("product_name") or (
                product_record.display_name if product_record else ""
            )
            product_label = "[%s] %s" % (default_code, product_name) if default_code else product_name
            shelf_photo_src = ""
            if line.get("shelf_photo"):
                shelf_photo_src = "data:image/png;base64,%s" % line.get("shelf_photo")
            shelf_photo = (
                "<img src='%s' alt='%s' style='width:52px;height:52px;object-fit:cover;"
                "border-radius:8px;border:1px solid #dbe3ef;background:#f8fafc;'/>"
                % (escape(shelf_photo_src), escape(line.get("name") or _("Shelf photo")))
                if shelf_photo_src
                else (
                    "<div style='width:52px;height:52px;border-radius:8px;background:#e8f1ff;"
                    "border:1px solid #cfe0ff;color:#1d4ed8;display:flex;align-items:center;"
                    "justify-content:center;font-weight:700;'>%s</div>" % escape(_("Shelf photo"))
                )
            )
            competitor_details = escape(line.get("competitor_product") or "-")
            if line.get("competitor_qty") not in (None, False, ""):
                competitor_details += (
                    "<div style='color:#111827;font-size:12px;margin-top:2px;'>%s: %s</div>"
                    % (escape(_("Competitor quantity")), escape(line.get("competitor_qty")))
                )
            product_details = (
                "<div style='font-weight:700;color:#111827;'>%s</div>"
                "<div style='color:#111827;font-size:12px;margin-top:2px;'>%s: %s</div>"
                "<div style='color:#111827;font-size:12px;margin-top:2px;'>%s: %s</div>"
            ) % (
                escape(product_label or "-"),
                escape(_("Batch number")),
                escape(line.get("batch_number") or "-"),
                escape(_("Shelf position")),
                escape(line.get("shelf_position") or "-"),
            )
            stock_line_rows += (
                "<tr style='background:#ffffff;'>"
                "<td style='padding:10px;border-bottom:1px solid #e5e7eb;width:62px;'>%s</td>"
                "<td style='padding:10px;border-bottom:1px solid #e5e7eb;'>%s</td>"
                "<td style='padding:10px;border-bottom:1px solid #e5e7eb;color:#111827;font-weight:700;'>%s</td>"
                "<td style='padding:10px;border-bottom:1px solid #e5e7eb;color:#111827;'>%s</td>"
                "<td style='padding:10px;border-bottom:1px solid #e5e7eb;color:#111827;'>%s</td>"
                "</tr>"
            ) % (
                shelf_photo,
                product_details,
                escape(line.get("stock_qty") or "-"),
                competitor_details,
                escape(line.get("notes") or line.get("note") or "-"),
            )
        stock_lines_table = ""
        if stock_line_rows:
            stock_lines_table = (
                "<div style='margin-top:14px;border:1px solid #bfdbfe;border-radius:12px;overflow:hidden;background:#eff6ff;'>"
                "<div style='padding:10px 12px;background:#dbeafe;color:#111827;font-weight:800;'>%s</div>"
                "<table style='width:100%%;border-collapse:collapse;background:white;'>"
                "<thead><tr style='background:#dbeafe;color:#111827;'>"
                "<th style='padding:8px 10px;text-align:right;width:62px;'>%s</th>"
                "<th style='padding:8px 10px;text-align:right;'>%s</th>"
                "<th style='padding:8px 10px;text-align:right;'>%s</th>"
                "<th style='padding:8px 10px;text-align:right;'>%s</th>"
                "<th style='padding:8px 10px;text-align:right;'>%s</th>"
                "</tr></thead><tbody>%s</tbody></table></div>"
            ) % (
                escape(_("Stock lines")),
                escape(_("Shelf photo")),
                escape(_("Product")),
                escape(_("Stock on hand")),
                escape(_("Competitor product")),
                escape(_("Notes")),
                stock_line_rows,
            )
        info_rows = "".join(
            "<tr><td style='padding:6px 0;color:#64748b;width:38%%;'>%s</td>"
            "<td style='padding:6px 0;color:#111827;font-weight:700;'>%s</td></tr>" % (
                escape(label),
                escape(value or "-"),
            )
            for label, value in [
                (_("Task"), self._record_name(task)),
                (_("Client"), self._record_name(partner, "-") if partner else "-"),
                (_("Task Type"), task_type_labels.get(task_type, task_type)),
                (_("Outcome"), outcome or "-") if task_type != "stock_audit" else (_("Stock lines"), str(len(stock_lines or []))),
            ]
        )
        location_rows = ""
        for label, value in [
            (_("Latitude"), latitude),
            (_("Longitude"), longitude),
            (_("Accuracy"), "%s m" % accuracy if accuracy not in (None, False, "") else ""),
            (_("Recorded At"), fields.Datetime.to_string(recorded_at) if recorded_at else ""),
        ]:
            if value not in (None, False, ""):
                location_rows += (
                    "<tr><td style='padding:5px 0;color:#111827;width:38%%;'>%s</td>"
                    "<td style='padding:5px 0;color:#111827;font-weight:700;'>%s</td></tr>"
                    % (escape(label), escape(value))
                )
        map_button = ""
        if latitude and longitude:
            maps_url = "https://www.google.com/maps/search/?api=1&query=%s,%s" % (latitude, longitude)
            map_button = (
                "<a href='%s' target='_blank' rel='noopener noreferrer' "
                "style='display:inline-block;margin-top:10px;padding:8px 12px;border-radius:8px;"
                "background:#f8fafc;border:1px solid #cbd5e1;color:#111827;text-decoration:none;font-weight:800;'>%s</a>"
            ) % (
                escape(maps_url),
                escape(_("Open location in Google Maps")),
            )
        location_section = ""
        if location_rows or map_button:
            mock_html = (
                "<div style='margin-top:8px;padding:7px 9px;border-radius:8px;background:#fee2e2;"
                "color:#991b1b;font-weight:700;'>%s</div>" % escape(_("Mock location detected"))
                if is_mock
                else ""
            )
            location_section = (
                "<div style='margin-top:14px;border:1px solid #fde68a;border-radius:12px;padding:12px;background:#fffbeb;'>"
                "<div style='font-weight:800;color:#111827;margin-bottom:6px;'>%s</div>"
                "<table style='width:100%%;border-collapse:collapse;'>%s</table>%s%s</div>"
                % (escape(_("Location")), location_rows, mock_html, map_button)
            )
        summary_html = (
            "<div style='margin-top:14px;border:1px solid #dbeafe;border-radius:12px;padding:12px;background:#eff6ff;'>"
            "<div style='font-weight:800;color:#111827;margin-bottom:6px;'>%s</div>"
            "<div style='white-space:pre-wrap;color:#111827;'>%s</div></div>"
            % (escape(_("Summary")), escape(summary))
            if summary
            else ""
        )
        return Markup(
            "<div style='max-width:760px;border:1px solid #d8dee4;border-radius:14px;overflow:hidden;"
            "background:#ffffff;direction:rtl;text-align:right;font-size:13px;'>"
            "<div style='padding:12px 14px;background:#f8fafc;color:#111827;border-bottom:1px solid #e5e7eb;'>"
            "<div style='font-size:15px;font-weight:900;'>%s</div>"
            "<div style='margin-top:4px;color:#111827;'>%s</div></div>"
            "<div style='padding:12px 14px;'>"
            "<div style='border:1px solid #e5e7eb;border-radius:12px;padding:10px;background:#f8fafc;'>"
            "<table style='width:100%%;border-collapse:collapse;'>%s</table></div>"
            "%s"
            "%s"
            "%s"
            "</div></div>"
            % (
                escape(title),
                escape(_("This task update was recorded from the mobile application.")),
                info_rows,
                summary_html,
                stock_lines_table if task_type == "stock_audit" else products_table,
                location_section,
            )
        )

    def _accounts(self):
        if request.httprequest.method == "POST":
            payload = self._json_body()
            partner = request.env["res.partner"].create(self._partner_values(payload, is_company=True))
            return self._json({"error": False, "message": _("Account Created Successfully"), "id": str(partner.id)})
        records = self._account_records(limit=self._arg_int("limit", 100))
        return self._json({"accounts": [self._serialize_partner_account(partner) for partner in records]})

    def _contacts(self):
        if request.httprequest.method == "POST":
            payload = self._json_body()
            partner = request.env["res.partner"].create(self._partner_values(payload, is_company=False))
            return self._json({"error": False, "message": _("Contact Created Successfully"), "id": str(partner.id)})
        records = self._contact_records(limit=self._arg_int("limit", 100))
        return self._json({"contacts": [self._serialize_partner_contact(partner) for partner in records]})

    def _teams_and_users(self):
        users = self._assignable_users()
        teams = self._safe_search("crm.team", order="sequence, id")
        return self._json(
            {
                "profiles": [self._serialize_profile(user) for user in users],
                "teams": [self._serialize_team(team) for team in teams],
            }
        )

    def _tags(self):
        model_name = (self._arg("model") or self._arg("scope") or "").strip().lower()
        if model_name in {"project.task", "task", "tasks"}:
            return self._json({"tags": [self._serialize_tag(tag) for tag in self._project_task_tags()]})
        return self._json({"tags": [self._serialize_tag(tag) for tag in self._crm_tags()]})

    def _cases(self):
        return self._json({"cases": [], "cases_count": 0, "results": [], "count": 0})

    def _invoices(self):
        if not self._has_model("account.move"):
            return self._json({"invoices": [], "invoices_count": 0})
        limit, offset = self._limit_offset()
        domain = [("move_type", "in", ("out_invoice", "out_refund"))]
        count = self._safe_search_count("account.move", domain)
        records = self._safe_search(
            "account.move",
            domain,
            order="invoice_date desc, id desc",
            limit=limit,
            offset=offset,
        )
        return self._json(
            {
                "invoices_count": count,
                "invoices": [self._serialize_invoice(move) for move in records],
            }
        )

    def _dashboard(self):
        today = fields.Date.context_today(request.env.user)
        accounts = self._account_records(limit=20)
        contacts = self._contact_records(limit=20)
        leads = self._safe_search(
            "crm.lead",
            [("type", "=", "lead")],
            limit=20,
            order="id desc",
            active_test=False,
        )
        opportunities = self._safe_search(
            "crm.lead",
            [("type", "=", "opportunity")],
            limit=20,
            order="id desc",
            active_test=False,
        )
        all_opportunities = self._safe_search(
            "crm.lead",
            [("type", "=", "opportunity")],
            active_test=False,
        )
        task_domain = expression.AND([
            self._mobile_task_visibility_domain(),
            self._mobile_open_task_domain(),
        ])
        tasks = self._safe_search(
            "project.task",
            task_domain,
            limit=10,
            order="date_deadline asc, id desc",
        )
        in_progress_domain = expression.AND([
            task_domain,
            [("ftiq_mobile_visit_state", "=", "in_progress")],
        ]) if "ftiq_mobile_visit_state" in request.env["project.task"]._fields else []
        in_progress_tasks = self._safe_search(
            "project.task",
            in_progress_domain,
            limit=5,
            order="ftiq_mobile_started_at desc, id desc",
        ) if in_progress_domain else request.env["project.task"]
        overdue_tasks = self._safe_search_count(
            "project.task",
            expression.AND([task_domain, [("date_deadline", "<", today)]]),
        )
        due_today = self._safe_search_count(
            "project.task",
            expression.AND([task_domain, [("date_deadline", "=", today)]]),
        )
        followups_today = 0
        Lead = request.env["crm.lead"]
        if "activity_date_deadline" in Lead._fields:
            followups_today = self._safe_search_count(
                "crm.lead",
                [("type", "=", "lead"), ("activity_date_deadline", "=", today)],
                active_test=False,
            )
        hot_leads_count = self._safe_search_count(
            "crm.lead",
            [("type", "=", "lead"), ("priority", "in", ("2", "3"))],
            active_test=False,
        )
        pipeline = self._pipeline_by_stage(all_opportunities)
        pipeline_value = sum(item["value"] for item in pipeline.values() if item)
        weighted_pipeline = sum(
            (self._field_value(lead, "expected_revenue", 0.0) or 0.0)
            * ((self._field_value(lead, "probability", 0.0) or 0.0) / 100.0)
            for lead in all_opportunities
            if self._deal_stage_value(lead) not in {"CLOSED_WON", "CLOSED_LOST"}
        )
        won_this_month = sum(
            self._field_value(lead, "expected_revenue", 0.0) or 0.0
            for lead in all_opportunities
            if self._deal_stage_value(lead) == "CLOSED_WON"
        )
        total_leads = self._safe_search_count(
            "crm.lead",
            [("type", "=", "lead")],
            active_test=False,
        )
        converted_count = self._safe_search_count(
            "crm.lead",
            [("type", "=", "opportunity")],
            active_test=False,
        )
        conversion_rate = (converted_count / total_leads * 100.0) if total_leads else 0.0
        hot_leads = self._safe_search(
            "crm.lead",
            [("type", "=", "lead"), ("priority", "in", ("2", "3"))],
            order="id desc",
            limit=10,
            active_test=False,
        )
        return self._json(
            {
                "accounts_count": self._safe_search_count("res.partner", [("parent_id", "=", False)]),
                "contacts_count": self._safe_search_count("res.partner", []),
                "leads_count": total_leads,
                "opportunities_count": converted_count,
                "accounts": [self._serialize_partner_account(partner) for partner in accounts],
                "contacts": [self._serialize_partner_contact(partner) for partner in contacts],
                "leads": [self._serialize_lead(lead) for lead in leads],
                "opportunities": [self._serialize_opportunity(lead) for lead in opportunities],
                "urgent_counts": {
                    "overdue_tasks": overdue_tasks,
                    "tasks_due_today": due_today,
                    "followups_today": followups_today,
                    "hot_leads": hot_leads_count,
                },
                "pipeline_by_stage": pipeline,
            "revenue_metrics": {
                "pipeline_value": pipeline_value,
                "weighted_pipeline": weighted_pipeline,
                "won_this_month": won_this_month,
                "conversion_rate": round(conversion_rate, 1),
                "currency": self._record_name(
                    self._field_value(request.env.company, "currency_id"),
                    "",
                ),
                "other_currency_count": 0,
            },
                "hot_leads": [self._dashboard_hot_lead(lead) for lead in hot_leads],
                "in_progress_tasks": [self._serialize_task(task) for task in in_progress_tasks],
                "tasks": [self._serialize_task(task) for task in tasks],
                "activities": [],
            }
        )

    def _mobile_task_visibility_domain(self):
        user_id = request.env.user.id
        return expression.OR([
            [("user_ids", "in", [user_id])],
            [("user_ids", "=", False), ("create_uid", "=", user_id)],
        ])

    def _mobile_open_task_domain(self):
        Task = request.env["project.task"]
        if "state" not in Task._fields:
            return []
        return [("state", "not in", ("1_done", "1_canceled"))]

    def _delete_message(self, message_id):
        message = request.env["mail.message"].browse(message_id).exists()
        if message:
            message.unlink()
        return self._ok_message(_("Comment Deleted Successfully"))

    def _lead_values(self, payload, existing=False, partial=False):
        values = {}
        if not partial or "title" in payload:
            title = payload.get("title") or payload.get("name")
            if not title:
                title = " ".join(
                    part for part in (payload.get("first_name"), payload.get("last_name")) if part
                )
            if not title:
                title = payload.get("company_name") or (existing.name if existing else _("New Lead"))
            values["name"] = title
        if not partial or "first_name" in payload or "last_name" in payload:
            contact_name = " ".join(
                part for part in (payload.get("first_name"), payload.get("last_name")) if part
            ).strip()
            if contact_name:
                values["contact_name"] = contact_name
        self._copy_if_present(values, payload, "email", "email_from", partial)
        self._copy_if_present(values, payload, "phone", "phone", partial)
        self._copy_if_present(values, payload, "website", "website", partial)
        self._copy_if_present(values, payload, "company_name", "partner_name", partial)
        self._copy_if_present(values, payload, "description", "description", partial)
        self._copy_if_present(values, payload, "address_line", "street", partial)
        self._copy_if_present(values, payload, "city", "city", partial)
        self._copy_if_present(values, payload, "postcode", "zip", partial)
        if not partial or "opportunity_amount" in payload:
            if payload.get("opportunity_amount") not in (None, ""):
                values["expected_revenue"] = payload.get("opportunity_amount") or 0.0
        if not partial or "probability" in payload:
            if payload.get("probability") not in (None, ""):
                values["probability"] = payload.get("probability") or 0
        if not partial or "close_date" in payload:
            if payload.get("close_date") not in (None, ""):
                values["date_deadline"] = payload.get("close_date")
        if not partial or "rating" in payload:
            values["priority"] = self._priority_from_rating(payload.get("rating"))
        if not partial or "source" in payload:
            source = self._source_from_value(payload.get("source"))
            if source:
                values["source_id"] = source.id
        if not partial or "assigned_to" in payload:
            user = self._first_user_from_payload(payload.get("assigned_to"))
            if user:
                values["user_id"] = user.id
        if not partial or "status" in payload:
            status_value = payload.get("status")
            if status_value == "closed":
                values["active"] = False
            elif status_value:
                values["active"] = True
        if not existing:
            values.setdefault("type", "lead")
        return values

    def _opportunity_values(self, payload, existing=False, partial=False):
        values = {}
        if not partial or "name" in payload:
            values["name"] = payload.get("name") or payload.get("title") or (existing.name if existing else _("New Opportunity"))
        if not partial or "account" in payload:
            partner = self._partner_from_id(payload.get("account"))
            if partner:
                values["partner_id"] = partner.id
                values["partner_name"] = partner.commercial_partner_id.name
        if not partial or "contacts" in payload:
            partner = self._first_partner_from_payload(payload.get("contacts"))
            if partner and not values.get("partner_id"):
                values["partner_id"] = partner.id
        self._copy_if_present(values, payload, "description", "description", partial)
        if not partial or "amount" in payload:
            if payload.get("amount") not in (None, ""):
                values["expected_revenue"] = payload.get("amount") or 0.0
        if not partial or "probability" in payload:
            if payload.get("probability") not in (None, ""):
                values["probability"] = payload.get("probability") or 0
        if not partial or "closed_on" in payload:
            if payload.get("closed_on") not in (None, ""):
                values["date_deadline"] = payload.get("closed_on")
        if not partial or "lead_source" in payload:
            source = self._source_from_value(payload.get("lead_source"))
            if source:
                values["source_id"] = source.id
        if not partial or "stage" in payload:
            stage_code = payload.get("stage")
            if stage_code == "CLOSED_LOST":
                values["active"] = False
                values["probability"] = 0
            elif stage_code:
                values["active"] = True
                stage = self._stage_from_deal_code(stage_code)
                if stage:
                    values["stage_id"] = stage.id
                if stage_code == "CLOSED_WON":
                    values["probability"] = 100
        if not partial or "assigned_to" in payload:
            user = self._first_user_from_payload(payload.get("assigned_to"))
            if user:
                values["user_id"] = user.id
        if not existing:
            values.setdefault("type", "opportunity")
        return values

    def _task_values(self, payload, existing=False, partial=False):
        values = {}
        if not partial or "title" in payload:
            values["name"] = payload.get("title") or payload.get("name") or (existing.name if existing else _("New Task"))
        self._copy_if_present(values, payload, "description", "description", partial)
        if not partial or "due_date" in payload:
            values["date_deadline"] = payload.get("due_date") or False
        if not partial or "priority" in payload:
            values["priority"] = self._priority_to_odoo(payload.get("priority"))
        if not partial or "status" in payload or "status_code" in payload or "state" in payload:
            state = self._task_state_from_status(
                payload.get("state") or payload.get("status_code") or payload.get("status")
            )
            if state:
                values["state"] = state
        if not partial or "assigned_to" in payload:
            users = self._users_from_payload(payload.get("assigned_to"))
            values["user_ids"] = [Command.set(users.ids)]
        if "tag_ids" in request.env["project.task"]._fields and (not partial or "tags" in payload):
            tags = self._project_task_tags_from_payload(payload.get("tags"))
            values["tag_ids"] = [Command.set(tags.ids)]
        if "ftiq_mobile_task_type" in request.env["project.task"]._fields and (
            not partial or "task_type" in payload or "ftiq_mobile_task_type" in payload
        ):
            task_type = (
                payload.get("task_type")
                or payload.get("ftiq_mobile_task_type")
                or ("" if existing else "field_visit")
            )
            allowed_types = {item["value"] for item in self._task_type_choices()}
            if task_type in allowed_types:
                values["ftiq_mobile_task_type"] = task_type
        partner = self._partner_from_id(payload.get("account"))
        if partner:
            values["partner_id"] = partner.id
        if not existing and "project_id" in request.env["project.task"]._fields:
            values.setdefault("project_id", self._default_project().id)
        return values

    def _partner_values(self, payload, is_company):
        first_name = payload.get("first_name") or ""
        last_name = payload.get("last_name") or ""
        name = payload.get("name") or " ".join(part for part in (first_name, last_name) if part)
        values = {
            "name": name or payload.get("email") or _("New Contact"),
            "is_company": is_company,
            "email": payload.get("email") or payload.get("primary_email") or "",
            "phone": payload.get("phone") or payload.get("mobile_number") or "",
            "mobile": payload.get("mobile_number") or "",
            "website": payload.get("website") or "",
            "street": payload.get("address_line") or "",
            "city": payload.get("city") or "",
            "zip": payload.get("postcode") or "",
            "comment": payload.get("description") or "",
        }
        account = self._partner_from_id(payload.get("account"))
        if account and not is_company:
            values["parent_id"] = account.commercial_partner_id.id
        return values

    def _copy_if_present(self, values, payload, source, target, partial):
        if not partial or source in payload:
            if payload.get(source) not in (None, ""):
                values[target] = payload.get(source)

    def _write_crm_relations(self, lead, payload):
        if "tags" in payload:
            tags = self._crm_tags_from_payload(payload.get("tags"))
            lead.write({"tag_ids": [Command.set(tags.ids)]})

    def _source_from_value(self, value, create=True):
        normalized = (value or "").strip()
        if not normalized or not self._has_model("utm.source"):
            return request.env["utm.source"]
        Source = request.env["utm.source"].sudo()
        source = Source.search([("name", "=ilike", normalized)], limit=1)
        if not source and create:
            source = Source.create({"name": normalized.title()})
        return source

    def _stage_from_deal_code(self, code, create=True):
        normalized = (code or "PROSPECTING").strip().upper()
        Stage = request.env["crm.stage"].sudo()
        if normalized == "CLOSED_WON":
            stage = Stage.search([("is_won", "=", True)], order="sequence, id", limit=1)
            if stage:
                return stage
        patterns = {
            "PROSPECTING": ["prospect", "new", "lead"],
            "QUALIFICATION": ["qual"],
            "PROPOSAL": ["propos", "quote"],
            "NEGOTIATION": ["negoti"],
            "CLOSED_LOST": ["lost"],
        }.get(normalized, [])
        for pattern in patterns:
            stage = Stage.search([("name", "ilike", pattern)], order="sequence, id", limit=1)
            if stage:
                return stage
        if not create:
            return Stage
        return Stage.create(
            {
                "name": self._stage_label(normalized),
                "sequence": {
                    "PROSPECTING": 10,
                    "QUALIFICATION": 20,
                    "PROPOSAL": 30,
                    "NEGOTIATION": 40,
                    "CLOSED_WON": 50,
                    "CLOSED_LOST": 60,
                }.get(normalized, 10),
                "is_won": normalized == "CLOSED_WON",
            }
        )

    def _task_state_from_status(self, status_value):
        raw_value = (status_value or "").strip()
        Task = request.env["project.task"]
        if "state" not in Task._fields:
            return ""
        selection = Task._fields["state"]._description_selection(request.env)
        if not raw_value:
            return "01_in_progress"
        normalized = raw_value.lower()
        for value, label in selection:
            if normalized in {value.lower(), (label or "").lower()}:
                return value
        legacy_map = {
            "new": "01_in_progress",
            "in progress": "01_in_progress",
            "completed": "1_done",
            "complete": "1_done",
            "done": "1_done",
            "cancelled": "1_canceled",
            "canceled": "1_canceled",
            "approved": "03_approved",
            "changes requested": "02_changes_requested",
            "waiting": "04_waiting_normal",
        }
        return legacy_map.get(normalized, "")

    def _priority_to_odoo(self, priority):
        normalized = (priority or "").strip().lower()
        if normalized == "urgent":
            return "3"
        if normalized == "high":
            return "2"
        if normalized == "medium":
            return "1"
        return "0"

    def _first_user_from_payload(self, value):
        users = self._users_from_payload(value)
        return users[:1]

    def _users_from_payload(self, value):
        ids = self._ids_from_payload(value)
        if not ids:
            return request.env["res.users"]
        return request.env["res.users"].browse(ids).exists()

    def _first_partner_from_payload(self, value):
        ids = self._ids_from_payload(value)
        if not ids:
            return request.env["res.partner"]
        return request.env["res.partner"].browse(ids[0]).exists()

    def _partner_from_id(self, value):
        if not value:
            return request.env["res.partner"]
        try:
            return request.env["res.partner"].browse(int(value)).exists()
        except Exception:
            return request.env["res.partner"]

    def _ids_from_payload(self, value):
        if value in (None, False, ""):
            return []
        if not isinstance(value, (list, tuple)):
            value = [value]
        ids = []
        for item in value:
            raw = item.get("id") if isinstance(item, dict) else item
            try:
                ids.append(int(raw))
            except Exception:
                continue
        return ids

    def _crm_tags_from_payload(self, value):
        ids = self._ids_from_payload(value)
        if ids:
            return request.env["crm.tag"].browse(ids).exists()
        names = []
        if isinstance(value, (list, tuple)):
            names = [item for item in value if isinstance(item, str)]
        tags = request.env["crm.tag"]
        for name in names:
            tag = request.env["crm.tag"].search([("name", "=ilike", name)], limit=1)
            if not tag:
                tag = request.env["crm.tag"].create({"name": name})
            tags |= tag
        return tags

    def _crm_tags(self):
        return self._safe_search("crm.tag", order="name")

    def _project_task_tags(self):
        if not self._has_model("project.tags"):
            return request.env["project.tags"]
        return self._safe_search("project.tags", order="name")

    def _project_task_tags_from_payload(self, value):
        if not self._has_model("project.tags"):
            return request.env["project.tags"]
        ids = self._ids_from_payload(value)
        Tag = request.env["project.tags"]
        if ids:
            return Tag.browse(ids).exists()
        names = []
        if isinstance(value, (list, tuple)):
            names = [item for item in value if isinstance(item, str)]
        tags = Tag
        for name in names:
            tag = Tag.search([("name", "=ilike", name)], limit=1)
            if not tag:
                tag = Tag.create({"name": name})
            tags |= tag
        return tags

    def _assignable_users(self):
        return self._safe_search(
            "res.users",
            [("active", "=", True), ("share", "=", False)],
            order="name",
        )

    def _account_records(self, limit=100):
        domain = [("parent_id", "=", False)]
        search = self._arg("search")
        if search:
            domain = expression.AND([domain, self._domain_for_search(["name", "email", "phone"], search)])
        return self._safe_search("res.partner", domain, order="name", limit=limit)

    def _contact_records(self, limit=100):
        domain = []
        search = self._arg("search")
        if search:
            domain = expression.AND([domain, self._domain_for_search(["name", "email", "phone"], search)])
        return self._safe_search("res.partner", domain, order="name", limit=limit)

    def _default_project(self):
        Project = request.env["project.project"].sudo()
        project = Project.search([("name", "=", "Mobile CRM Tasks")], limit=1)
        if not project:
            project = Project.create({"name": "Mobile CRM Tasks", "company_id": request.env.company.id})
        return project

    def _pipeline_by_stage(self, opportunities):
        result = {}
        for code in ("PROSPECTING", "QUALIFICATION", "PROPOSAL", "NEGOTIATION", "CLOSED_WON", "CLOSED_LOST"):
            records = opportunities.filtered(lambda lead, c=code: self._deal_stage_value(lead) == c)
            result[code] = {
                "label": self._stage_label(code),
                "count": len(records),
                "value": sum(
                    self._field_value(record, "expected_revenue", 0.0) or 0.0
                    for record in records
                ),
            }
        return result

    def _dashboard_hot_lead(self, lead):
        serialized = self._serialize_lead(lead)
        return {
            "id": serialized["id"],
            "first_name": serialized["first_name"],
            "last_name": serialized["last_name"],
            "company": serialized["company_name"],
            "rating": serialized["rating"],
            "next_follow_up": serialized["next_follow_up"],
            "last_contacted": serialized["last_contacted"],
        }

    def _serialize_invoice(self, move):
        partner = self._field_value(move, "partner_id")
        commercial_partner = (
            self._field_value(partner, "commercial_partner_id") if partner else False
        )
        currency = self._field_value(move, "currency_id")
        return {
            "id": str(move.id),
            "name": self._record_name(move),
            "number": self._field_value(move, "name", "") or "",
            "partner": self._serialize_partner_account(commercial_partner) if commercial_partner else None,
            "amount_total": self._field_value(move, "amount_total", 0.0) or 0.0,
            "amount_residual": self._field_value(move, "amount_residual", 0.0) or 0.0,
            "currency": self._record_name(currency),
            "state": self._field_value(move, "state", "") or "",
            "payment_state": self._field_value(move, "payment_state", "") or "",
            "invoice_date": self._date_string(self._field_value(move, "invoice_date")),
            "due_date": self._date_string(self._field_value(move, "invoice_date_due")),
            "created_at": self._date_string(self._field_value(move, "create_date")),
        }

    def _lead_status_choices(self):
        return [
            ("assigned", "Assigned"),
            ("in process", "In Process"),
            ("converted", "Converted"),
            ("recycled", "Recycled"),
            ("closed", "Closed"),
        ]

    def _lead_source_choices(self):
        return [
            ("", "None"),
            ("call", "Call"),
            ("email", "Email"),
            ("existing customer", "Existing Customer"),
            ("partner", "Partner"),
            ("public relations", "Public Relations"),
            ("compaign", "Campaign"),
            ("other", "Other"),
        ]

    def _deal_stage_choices(self):
        return [(code, self._stage_label(code)) for code in (
            "PROSPECTING",
            "QUALIFICATION",
            "PROPOSAL",
            "NEGOTIATION",
            "CLOSED_WON",
            "CLOSED_LOST",
        )]

    def _opportunity_source_choices(self):
        return [
            ("NONE", "None"),
            ("CALL", "Call"),
            ("EMAIL", "Email"),
            ("EXISTING CUSTOMER", "Existing Customer"),
            ("PARTNER", "Partner"),
            ("PUBLIC RELATIONS", "Public Relations"),
            ("CAMPAIGN", "Campaign"),
            ("WEBSITE", "Website"),
            ("OTHER", "Other"),
        ]

    def _task_status_choices(self):
        Task = request.env["project.task"]
        if "state" not in Task._fields:
            return [
                {"value": "New", "label": "New"},
                {"value": "In Progress", "label": "In Progress"},
                {"value": "Completed", "label": "Completed"},
            ]
        return [
            {
                "value": value,
                "label": label,
                "is_done": value == "1_done",
                "is_cancelled": value == "1_canceled",
                "sequence": index,
            }
            for index, (value, label) in enumerate(
                Task._fields["state"]._description_selection(request.env)
            )
        ]

    def _task_priority_choices(self):
        return [("Low", "Low"), ("Medium", "Medium"), ("High", "High"), ("Urgent", "Urgent")]

    def _currency_choices(self):
        return [
            (currency.name, currency.name)
            for currency in self._safe_search("res.currency", [("active", "=", True)])
        ]

    def _country_choices(self):
        return [
            (country.code or str(country.id), country.name)
            for country in self._safe_search("res.country", order="name")
        ]
