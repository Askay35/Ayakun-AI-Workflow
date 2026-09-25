from __future__ import annotations

from urllib.parse import quote

import httpx

from helper import apply_variable_assignments, render_template
from schemas.workflow import JiraNode
from services.execution.actions.base import NodeAction
from services.execution.actions.integration_http import call_api, require_https, response_json
from services.execution.context import incoming_payload

JIRA_SEARCH_LIMIT = 50
JIRA_SEARCH_FIELDS = ["summary", "status", "assignee", "priority", "issuetype", "created", "updated"]


def _name(value: object) -> str | None:
    if isinstance(value, dict):
        return value.get("displayName") or value.get("name")
    return None


def _issue(item: object, base_url: str) -> dict:
    if not isinstance(item, dict):
        return {}
    fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
    key = item.get("key")
    return {
        "key": key,
        "summary": fields.get("summary"),
        "status": _name(fields.get("status")),
        "assignee": _name(fields.get("assignee")),
        "priority": _name(fields.get("priority")),
        "type": _name(fields.get("issuetype")),
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "url": f"{base_url}/browse/{key}" if key else None,
    }


class JiraAction(NodeAction):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def execute(self, node: JiraNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})

        def text(value: str) -> str:
            return render_template(value or "", payload, variables).strip()

        base_url = require_https(text(node.base_url), "Jira")
        email, api_token = text(node.email), text(node.api_token)
        if not email or not api_token:
            raise ValueError("Jira: укажите email и API-токен")
        auth = httpx.BasicAuth(email, api_token)
        headers = {"Accept": "application/json"}
        if node.operation == "create_issue":
            project, summary = text(node.project_key), text(node.summary)
            if not project or not summary:
                raise ValueError("Jira: укажите проект и заголовок задачи")
            fields = {
                "project": {"key": project},
                "summary": summary[:255],
                "issuetype": {"name": text(node.issue_type) or "Task"},
            }
            description = text(node.description)
            if description:
                fields["description"] = description
            response = await call_api(
                self.client, "Jira", "POST", f"{base_url}/rest/api/2/issue",
                auth=auth, headers=headers, json={"fields": fields},
            )
            body = response_json(response, "Jira")
            key = body.get("key") if isinstance(body, dict) else None
            output: dict = {
                "operation": node.operation,
                "key": key,
                "id": body.get("id") if isinstance(body, dict) else None,
                "summary": summary,
                "url": f"{base_url}/browse/{key}" if key else None,
            }
        elif node.operation == "search":
            jql = text(node.jql)
            if not jql:
                raise ValueError("Jira: укажите JQL-запрос")
            response = await call_api(
                self.client, "Jira", "POST", f"{base_url}/rest/api/3/search/jql",
                auth=auth, headers=headers,
                json={"jql": jql, "maxResults": JIRA_SEARCH_LIMIT, "fields": JIRA_SEARCH_FIELDS},
            )
            body = response_json(response, "Jira")
            raw = body.get("issues") if isinstance(body, dict) else None
            issues = [_issue(item, base_url) for item in raw] if isinstance(raw, list) else []
            output = {"operation": node.operation, "issues": issues, "count": len(issues)}
        else:
            issue_key, comment = text(node.issue_key), text(node.comment)
            if not issue_key or not comment:
                raise ValueError("Jira: укажите ключ задачи и текст комментария")
            response = await call_api(
                self.client, "Jira", "POST", f"{base_url}/rest/api/2/issue/{quote(issue_key, safe='')}/comment",
                auth=auth, headers=headers, json={"body": comment},
            )
            body = response_json(response, "Jira")
            output = {
                "operation": node.operation,
                "key": issue_key,
                "comment_id": body.get("id") if isinstance(body, dict) else None,
                "url": f"{base_url}/browse/{issue_key}",
            }
        apply_variable_assignments(node.assignments, output, context)
        return output
