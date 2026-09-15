from core.config import settings
from helper import apply_variable_assignments, expression_root, render_template
from schemas.workflow import PromptNode
from services.execution.actions.base import NodeAction
from services.execution.context import parent_output_texts, parent_records
from services.pricing import PricingService, billed_credits, maximum_output_tokens, padded_input_tokens
from services.providers import ModelRouter, llm_instructions
from utils.deepseek_tokenizer import count_prompt_tokens


class PromptAction(NodeAction):
    def __init__(
        self,
        model_router: ModelRouter,
        pricing: PricingService,
        available_budget,
    ):
        self.model_router = model_router
        self.pricing = pricing
        self.available_budget = available_budget

    async def execute(self, node: PromptNode, context: dict) -> dict:
        provider, default_model = self.model_router.select(
            node.provider,
            operation=node.complexity,
        )
        setting_key = "complex_llm_model" if node.complexity == "complex_text" else "simple_llm_model"
        model = node.model or await self.pricing.setting(setting_key, default_model)
        records = parent_records(node, context)
        parent_output = records[0].get("output") if records else None
        root = expression_root(parent_output) if parent_output is not None else {}
        variables = context.setdefault("variables", {})
        prompt = render_template(node.prompt, root, variables) if "{{" in (node.prompt or "") else node.prompt
        instructions = node.instructions or ""
        output_format = node.output_format or ""
        if "{{" in instructions:
            instructions = render_template(instructions, root, variables)
        if "{{" in output_format:
            output_format = render_template(output_format, root, variables)
        composed_instructions = llm_instructions(instructions or None, output_format or None)
        input_data = parent_output_texts(node, context) or None
        input_tokens = padded_input_tokens(count_prompt_tokens(
            prompt,
            instructions=composed_instructions,
            input_data=input_data,
        ))
        price = await self.pricing.get("deepseek", model)
        configured_max = int(await self.pricing.setting(
            "llm_max_output_tokens", settings.llm_max_output_tokens
        ))
        remaining = await self.available_budget()
        if billed_credits(price, 0, input_tokens, 0) >= remaining:
            raise ValueError("Недостаточно credits даже для входных токенов LLM-запроса")
        node_max = max(1, int(getattr(node, "max_output_tokens", None) or settings.llm_max_output_tokens))
        max_tokens = min(
            maximum_output_tokens(price, remaining, input_tokens),
            node_max,
            configured_max,
        )
        if max_tokens < 1:
            raise ValueError("Недостаточно credits даже для входных токенов LLM-запроса")
        result = await provider.prompt(
            prompt,
            instructions=instructions or None,
            output_format=output_format or None,
            input_data=input_data,
            model=model,
            max_tokens=max_tokens,
        )
        payload = result.model_dump(mode="json")
        apply_variable_assignments(node.assignments, payload, context)
        return payload
