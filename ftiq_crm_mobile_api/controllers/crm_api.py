from datetime import date

from odoo import _, fields, http
from odoo.fields import Command
from odoo.http import request
from odoo.osv import expression

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
        Lead = request.env["crm.lead"].with_context(active_test=False)
        open_domain = expression.AND([domain, [("active", "=", True)]])
        close_domain = expression.AND([domain, [("active", "=", False)]])
        open_count = Lead.search_count(open_domain)
        close_count = Lead.search_count(close_domain)
        open_records = Lead.search(open_domain, order="id desc", limit=limit, offset=offset)
        close_records = Lead.search(close_domain, order="id desc", limit=limit, offset=offset)
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
                    {"id": str(partner.id), "first_name": self._split_name(partner.name)[0]}
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
        return {
            "lead_obj": self._serialize_lead(lead),
            "attachments": [],
            "comments": self._serialize_messages(lead),
            "users_mention": [{"user__email": user.login or user.email or ""} for user in users],
            "assigned_data": self._assigned_users(lead.user_id) if lead.user_id else [],
            "users": [self._serialize_profile(user) for user in users],
            "users_excluding_team": [self._serialize_profile(user) for user in users],
            "source": self._lead_source_choices(),
            "status": self._lead_status_choices(),
            "teams": [self._serialize_team(team) for team in request.env["crm.team"].search([])],
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
        Lead = request.env["crm.lead"].with_context(active_test=False)
        count = Lead.search_count(domain)
        records = Lead.search(domain, order="id desc", limit=limit, offset=offset)
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
        return {
            "opportunity_obj": self._serialize_opportunity(opportunity),
            "comments": self._serialize_messages(opportunity),
            "attachments": [],
            "contacts": [self._serialize_partner_contact(opportunity.partner_id)] if opportunity.partner_id else [],
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
        domain = []
        search = self._arg("search") or self._arg("title")
        if search:
            domain = expression.AND([domain, self._domain_for_search(["name"], search)])
        priority = self._arg("priority")
        if priority:
            domain.append(("priority", "=", self._priority_to_odoo(priority)))
        status_value = self._arg("status")
        if status_value:
            stage = self._task_stage_from_status(status_value, create=False)
            if stage:
                domain.append(("stage_id", "=", stage.id))
        Task = request.env["project.task"]
        count = Task.search_count(domain)
        records = Task.search(domain, order="id desc", limit=limit, offset=offset)
        return self._json(
            {
                "tasks_count": count,
                "offset": offset + len(records) if offset + len(records) < count else None,
                "tasks": [self._serialize_task(task) for task in records],
                "status": self._task_status_choices(),
                "priority": self._task_priority_choices(),
                "accounts_list": [self._serialize_partner_account(partner) for partner in self._account_records(limit=100)],
                "contacts_list": [self._serialize_partner_contact(partner) for partner in self._contact_records(limit=100)],
            }
        )

    def _task_detail(self, task_id):
        task = request.env["project.task"].browse(task_id).exists()
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
        return {
            "task_obj": self._serialize_task(task),
            "attachments": [],
            "comments": self._serialize_messages(task),
            "users_mention": [{"user__email": user.login or user.email or ""} for user in users],
            "assigned_data": self._assigned_users(task.user_ids),
            "users": [self._serialize_profile(user) for user in users],
            "users_excluding_team": [self._serialize_profile(user) for user in users],
            "teams": [self._serialize_team(team) for team in request.env["crm.team"].search([])],
        }

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
        teams = request.env["crm.team"].search([], order="sequence, id")
        return self._json(
            {
                "profiles": [self._serialize_profile(user) for user in users],
                "teams": [self._serialize_team(team) for team in teams],
            }
        )

    def _tags(self):
        return self._json({"tags": [self._serialize_tag(tag) for tag in self._crm_tags()]})

    def _cases(self):
        return self._json({"cases": [], "cases_count": 0, "results": [], "count": 0})

    def _invoices(self):
        if not self._has_model("account.move"):
            return self._json({"invoices": [], "invoices_count": 0})
        limit, offset = self._limit_offset()
        domain = [("move_type", "in", ("out_invoice", "out_refund"))]
        Move = request.env["account.move"]
        count = Move.search_count(domain)
        records = Move.search(domain, order="invoice_date desc, id desc", limit=limit, offset=offset)
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
        Lead = request.env["crm.lead"]
        leads = Lead.search([("type", "=", "lead")], limit=20, order="id desc")
        opportunities = Lead.search([("type", "=", "opportunity")], limit=20, order="id desc")
        all_opportunities = Lead.search([("type", "=", "opportunity")])
        Task = request.env["project.task"]
        task_domain = []
        tasks = Task.search(task_domain, limit=10, order="date_deadline asc, id desc")
        overdue_tasks = Task.search_count([("date_deadline", "<", today)])
        due_today = Task.search_count([("date_deadline", "=", today)])
        followups_today = 0
        if "activity_date_deadline" in Lead._fields:
            followups_today = Lead.search_count([("type", "=", "lead"), ("activity_date_deadline", "=", today)])
        hot_leads_count = Lead.search_count([("type", "=", "lead"), ("priority", "in", ("2", "3"))])
        pipeline = self._pipeline_by_stage(all_opportunities)
        pipeline_value = sum(item["value"] for item in pipeline.values() if item)
        weighted_pipeline = sum(
            (lead.expected_revenue or 0.0) * ((lead.probability or 0.0) / 100.0)
            for lead in all_opportunities
            if self._deal_stage_value(lead) not in {"CLOSED_WON", "CLOSED_LOST"}
        )
        won_this_month = sum(
            lead.expected_revenue or 0.0
            for lead in all_opportunities
            if self._deal_stage_value(lead) == "CLOSED_WON"
        )
        total_leads = Lead.search_count([("type", "=", "lead")])
        converted_count = Lead.search_count([("type", "=", "opportunity")])
        conversion_rate = (converted_count / total_leads * 100.0) if total_leads else 0.0
        hot_leads = Lead.search(
            [("type", "=", "lead"), ("priority", "in", ("2", "3"))],
            order="id desc",
            limit=10,
        )
        return self._json(
            {
                "accounts_count": request.env["res.partner"].search_count([("parent_id", "=", False)]),
                "contacts_count": request.env["res.partner"].search_count([]),
                "leads_count": total_leads,
                "opportunities_count": Lead.search_count([("type", "=", "opportunity")]),
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
                    "currency": request.env.company.currency_id.name,
                    "other_currency_count": 0,
                },
                "hot_leads": [self._dashboard_hot_lead(lead) for lead in hot_leads],
                "tasks": [self._serialize_task(task) for task in tasks],
                "activities": [],
            }
        )

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
        if not partial or "status" in payload:
            stage = self._task_stage_from_status(payload.get("status"))
            if stage:
                values["stage_id"] = stage.id
        if not partial or "assigned_to" in payload:
            users = self._users_from_payload(payload.get("assigned_to"))
            values["user_ids"] = [Command.set(users.ids)]
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

    def _task_stage_from_status(self, status_value, create=True):
        normalized = (status_value or "New").strip().lower()
        Stage = request.env["project.task.type"].sudo()
        if normalized == "completed":
            stage = Stage.search([("fold", "=", True)], order="sequence, id", limit=1)
            if stage:
                return stage
        patterns = {
            "new": ["new", "todo", "backlog"],
            "in progress": ["progress", "doing"],
            "completed": ["done", "complete"],
        }.get(normalized, ["new"])
        for pattern in patterns:
            stage = Stage.search([("name", "ilike", pattern)], order="sequence, id", limit=1)
            if stage:
                return stage
        if not create:
            return Stage
        return Stage.create(
            {
                "name": {
                    "new": "New",
                    "in progress": "In Progress",
                    "completed": "Completed",
                }.get(normalized, "New"),
                "sequence": {"new": 10, "in progress": 20, "completed": 30}.get(normalized, 10),
                "fold": normalized == "completed",
            }
        )

    def _priority_to_odoo(self, priority):
        normalized = (priority or "").strip().lower()
        if normalized in {"high", "urgent"}:
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
        return request.env["crm.tag"].search([], order="name")

    def _assignable_users(self):
        return request.env["res.users"].search(
            [("active", "=", True), ("share", "=", False)],
            order="name",
        )

    def _account_records(self, limit=100):
        domain = [("parent_id", "=", False)]
        search = self._arg("search")
        if search:
            domain = expression.AND([domain, self._domain_for_search(["name", "email", "phone"], search)])
        return request.env["res.partner"].search(domain, order="name", limit=limit)

    def _contact_records(self, limit=100):
        domain = []
        search = self._arg("search")
        if search:
            domain = expression.AND([domain, self._domain_for_search(["name", "email", "phone"], search)])
        return request.env["res.partner"].search(domain, order="name", limit=limit)

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
                "value": sum(records.mapped("expected_revenue")),
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
        return {
            "id": str(move.id),
            "name": move.name or move.display_name,
            "number": move.name or "",
            "partner": self._serialize_partner_account(move.partner_id.commercial_partner_id) if move.partner_id else None,
            "amount_total": move.amount_total,
            "amount_residual": move.amount_residual,
            "currency": move.currency_id.name,
            "state": move.state,
            "payment_state": move.payment_state,
            "invoice_date": self._date_string(move.invoice_date),
            "due_date": self._date_string(move.invoice_date_due),
            "created_at": self._date_string(move.create_date),
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
        return [("New", "New"), ("In Progress", "In Progress"), ("Completed", "Completed")]

    def _task_priority_choices(self):
        return [("Low", "Low"), ("Medium", "Medium"), ("High", "High"), ("Urgent", "Urgent")]

    def _currency_choices(self):
        return [(currency.name, currency.name) for currency in request.env["res.currency"].search([("active", "=", True)])]

    def _country_choices(self):
        return [(country.code or str(country.id), country.name) for country in request.env["res.country"].search([], order="name")]
