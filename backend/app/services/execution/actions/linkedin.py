from __future__ import annotations

import httpx

from helper import render_template
from schemas.workflow import LinkedInNode
from services.execution.actions.base import NodeAction
from services.execution.actions.integration_http import call_api, response_json
from services.execution.context import incoming_payload, parent_output_texts

LINKEDIN_TEXT_LIMIT = 3000
LINKEDIN_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"


def author_urn(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    return value if value.startswith("urn:li:") else f"urn:li:person:{value}"


class LinkedInAction(NodeAction):
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def execute(self, node: LinkedInNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        token = render_template(node.access_token or "", payload, variables).strip()
        author = author_urn(render_template(node.author or "", payload, variables))
        if not token or not author:
            raise ValueError("LinkedIn: укажите токен и автора публикации")
        if (node.text or "").strip():
            text = render_template(node.text, payload, variables)
        else:
            texts = parent_output_texts(node, context)
            text = texts[0] if texts else ""
        text = text.strip()
        if not text:
            raise ValueError("LinkedIn: пустой текст публикации")
        if len(text) > LINKEDIN_TEXT_LIMIT:
            text = text[: LINKEDIN_TEXT_LIMIT - 1] + "…"
        body = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": node.visibility},
        }
        response = await call_api(
            self.client,
            "LinkedIn",
            "POST",
            LINKEDIN_POSTS_URL,
            headers={"Authorization": f"Bearer {token}", "X-Restli-Protocol-Version": "2.0.0"},
            json=body,
        )
        result = response_json(response, "LinkedIn")
        post_id = response.headers.get("x-restli-id") or (result.get("id") if isinstance(result, dict) else None)
        return {"published": True, "id": post_id, "author": author, "text": text}
