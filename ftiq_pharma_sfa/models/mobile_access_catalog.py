from collections import defaultdict


MOBILE_ROLE_SELECTION = [
    ("representative", "Representative"),
    ("supervisor", "Supervisor"),
    ("manager", "Manager"),
]

MOBILE_SCOPE_SELECTION = [
    ("navigation", "Navigation"),
    ("workspace", "Workspace"),
    ("section", "Section"),
    ("action", "Action"),
    ("global_feature", "Global feature"),
]

MOBILE_SCOPE_PAYLOAD_BUCKETS = {
    "navigation": "navigation",
    "workspace": "workspaces",
    "section": "sections",
    "action": "actions",
    "global_feature": "global_features",
}

MOBILE_PERMISSION_CATALOG = (
    {"scope": "navigation", "key": "dashboard", "label": "Dashboard tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 10},
    {"scope": "navigation", "key": "clients", "label": "Clients tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 20},
    {"scope": "navigation", "key": "visits", "label": "Visits tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 30},
    {"scope": "navigation", "key": "work", "label": "Work tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 40},
    {"scope": "navigation", "key": "more", "label": "More tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 50},
    {"scope": "workspace", "key": "attendance", "label": "Attendance workspace", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 110},
    {"scope": "workspace", "key": "finance", "label": "Finance workspace", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 120},
    {"scope": "workspace", "key": "team_hub", "label": "Team hub", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 130},
    {"scope": "workspace", "key": "operations_hub", "label": "Operations hub", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 140},
    {"scope": "workspace", "key": "notifications", "label": "Notifications center", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 150},
    {"scope": "workspace", "key": "device_sessions", "label": "Device sessions", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 160},
    {"scope": "section", "key": "dashboard.team", "label": "Dashboard team section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 210},
    {"scope": "section", "key": "dashboard.area", "label": "Dashboard area section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 220},
    {"scope": "section", "key": "dashboard.targets", "label": "Dashboard targets section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 230},
    {"scope": "section", "key": "client.profile", "label": "Client profile section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 240},
    {"scope": "section", "key": "client.finance", "label": "Client finance section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 250},
    {"scope": "section", "key": "visit.evidence", "label": "Visit evidence section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 260},
    {"scope": "section", "key": "visit.related_records", "label": "Visit related records section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 270},
    {"scope": "section", "key": "visit.thread", "label": "Visit thread section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 280},
    {"scope": "section", "key": "visit.activities", "label": "Visit activities section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 290},
    {"scope": "section", "key": "task.evidence", "label": "Task evidence section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 300},
    {"scope": "section", "key": "task.thread", "label": "Task thread section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 310},
    {"scope": "section", "key": "task.activities", "label": "Task activities section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 320},
    {"scope": "section", "key": "finance.notifications", "label": "Finance notifications section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 330},
    {"scope": "section", "key": "finance.schedules", "label": "Finance schedules section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 340},
    {"scope": "section", "key": "team.members", "label": "Team members section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 350},
    {"scope": "section", "key": "team.messages", "label": "Team messages section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 360},
    {"scope": "section", "key": "team.tasks", "label": "Team tasks section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 370},
    {"scope": "section", "key": "thread.messages", "label": "Thread messages section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 380},
    {"scope": "section", "key": "thread.attachments", "label": "Thread attachments section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 390},
    {"scope": "section", "key": "thread.followers", "label": "Thread followers section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 400},
    {"scope": "section", "key": "order.details", "label": "Order details section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 410},
    {"scope": "section", "key": "order.lines", "label": "Order lines section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 420},
    {"scope": "section", "key": "order.thread", "label": "Order thread section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 430},
    {"scope": "section", "key": "collection.details", "label": "Collection details section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 440},
    {"scope": "section", "key": "collection.receipt", "label": "Collection receipt section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 450},
    {"scope": "section", "key": "collection.allocations", "label": "Collection allocations section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 460},
    {"scope": "section", "key": "collection.thread", "label": "Collection thread section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 470},
    {"scope": "section", "key": "stock_check.details", "label": "Stock check details section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 480},
    {"scope": "section", "key": "stock_check.lines", "label": "Stock check lines section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 490},
    {"scope": "section", "key": "stock_check.thread", "label": "Stock check thread section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 500},
    {"scope": "section", "key": "expense.details", "label": "Expense details section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 505},
    {"scope": "section", "key": "expense.receipt", "label": "Expense receipt section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 506},
    {"scope": "section", "key": "expense.thread", "label": "Expense thread section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 507},
    {"scope": "section", "key": "invoice.summary", "label": "Invoice summary section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 508},
    {"scope": "section", "key": "invoice.lines", "label": "Invoice lines section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 509},
    {"scope": "section", "key": "invoice.activities", "label": "Invoice activities section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 510},
    {"scope": "section", "key": "invoice.thread", "label": "Invoice thread section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 511},
    {"scope": "section", "key": "invoice.payment_history", "label": "Invoice payment history section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 512},
    {"scope": "section", "key": "invoice.linked_operations", "label": "Invoice linked operations section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 513},
    {"scope": "section", "key": "purchase.summary", "label": "Purchase summary section", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 514},
    {"scope": "section", "key": "purchase.actions", "label": "Purchase actions section", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 515},
    {"scope": "section", "key": "purchase.lines", "label": "Purchase lines section", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 516},
    {"scope": "section", "key": "purchase.activities", "label": "Purchase activities section", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 517},
    {"scope": "section", "key": "purchase.thread", "label": "Purchase thread section", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 518},
    {"scope": "action", "key": "visit.edit", "label": "Edit visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 510},
    {"scope": "action", "key": "visit.start", "label": "Start visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 520},
    {"scope": "action", "key": "visit.end", "label": "End visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 530},
    {"scope": "action", "key": "visit.submit", "label": "Submit visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 540},
    {"scope": "action", "key": "visit.approve", "label": "Approve visit", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 550},
    {"scope": "action", "key": "visit.return", "label": "Return visit", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 560},
    {"scope": "action", "key": "visit.create_order", "label": "Create order from visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 570},
    {"scope": "action", "key": "visit.create_collection", "label": "Create collection from visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 580},
    {"scope": "action", "key": "visit.create_stock_check", "label": "Create stock check from visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 590},
    {"scope": "action", "key": "task.edit", "label": "Edit task", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 610},
    {"scope": "action", "key": "task.start", "label": "Start task", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 620},
    {"scope": "action", "key": "task.complete", "label": "Complete task", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 630},
    {"scope": "action", "key": "task.submit", "label": "Submit task", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 640},
    {"scope": "action", "key": "task.confirm", "label": "Confirm task", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 650},
    {"scope": "action", "key": "task.return", "label": "Return task", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 660},
    {"scope": "action", "key": "order.edit", "label": "Edit order", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 710},
    {"scope": "action", "key": "order.confirm", "label": "Confirm order", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 720},
    {"scope": "action", "key": "collection.edit", "label": "Edit collection", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 730},
    {"scope": "action", "key": "collection.collect", "label": "Collect payment", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 740},
    {"scope": "action", "key": "collection.deposit", "label": "Deposit collection", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 750},
    {"scope": "action", "key": "collection.verify", "label": "Verify collection", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 760},
    {"scope": "action", "key": "stock_check.edit", "label": "Edit stock check", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 770},
    {"scope": "action", "key": "stock_check.submit", "label": "Submit stock check", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 780},
    {"scope": "action", "key": "stock_check.review", "label": "Review stock check", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 790},
    {"scope": "action", "key": "stock_check.reset", "label": "Reset stock check", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 800},
    {"scope": "action", "key": "expense.edit", "label": "Edit expense", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 810},
    {"scope": "action", "key": "expense.submit", "label": "Submit expense", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 820},
    {"scope": "action", "key": "purchase.confirm", "label": "Confirm purchase", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 830},
    {"scope": "action", "key": "purchase.approve", "label": "Approve purchase", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 840},
    {"scope": "action", "key": "purchase.reject", "label": "Reject purchase", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 850},
    {"scope": "action", "key": "invoice.create_collection", "label": "Create collection from invoice", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 855},
    {"scope": "action", "key": "team.publish_note", "label": "Publish team note", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 860},
    {"scope": "action", "key": "team.publish_alert", "label": "Publish team alert", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 870},
    {"scope": "action", "key": "thread.post_message", "label": "Post thread message", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 880},
    {"scope": "action", "key": "thread.upload_attachment", "label": "Upload thread attachment", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 890},
    {"scope": "action", "key": "activity.mark_done", "label": "Complete activity", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 900},
    {"scope": "action", "key": "attendance.check_out", "label": "Check out attendance", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 910},
    {"scope": "global_feature", "key": "location.attendance", "label": "Require location for attendance", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 1010},
    {"scope": "global_feature", "key": "location.visit_start", "label": "Require location for visit start", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 1020},
    {"scope": "global_feature", "key": "location.task_start", "label": "Require location for task start", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 1030},
    {"scope": "global_feature", "key": "location.collection", "label": "Require location for collections", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": False, "ui_order": 1040},
    {"scope": "global_feature", "key": "location.order", "label": "Require location for orders", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": False, "ui_order": 1050},
    {"scope": "global_feature", "key": "location.stock_check", "label": "Require location for stock checks", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": False, "ui_order": 1060},
)


def mobile_full_key(scope_name, key_name):
    return "%s.%s" % (scope_name, key_name)


MOBILE_CATALOG_BY_FULL_KEY = {
    mobile_full_key(entry["scope"], entry["key"]): entry
    for entry in MOBILE_PERMISSION_CATALOG
}


def group_mobile_catalog_entries():
    grouped = defaultdict(list)
    for entry in MOBILE_PERMISSION_CATALOG:
        grouped[entry["scope"]].append(entry)
    return grouped


MOBILE_CATALOG_GROUPED = group_mobile_catalog_entries()


def empty_mobile_access_payload(role=""):
    return {
        "contract_version": "2026-04-09",
        "policy_mode": "deny_by_default",
        "enabled": False,
        "role": role,
        "profile": {},
        "navigation": {
            entry["key"]: False
            for entry in MOBILE_CATALOG_GROUPED.get("navigation", [])
        },
        "workspaces": {
            entry["key"]: False
            for entry in MOBILE_CATALOG_GROUPED.get("workspace", [])
        },
        "sections": {
            entry["key"]: False
            for entry in MOBILE_CATALOG_GROUPED.get("section", [])
        },
        "actions": {
            entry["key"]: False
            for entry in MOBILE_CATALOG_GROUPED.get("action", [])
        },
        "global_features": {
            entry["key"]: False
            for entry in MOBILE_CATALOG_GROUPED.get("global_feature", [])
        },
        "reason": "",
    }
