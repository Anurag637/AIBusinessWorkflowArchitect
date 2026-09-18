"""
RAG Tool providing policy retrieval and knowledge search capabilities.
"""

from typing import Dict, Any, Optional
from app.tools.base import BaseTool, ToolActionSpec, ToolParameter, ToolExecutionResult
from app.services.rag import get_rag_service


class RAGTool(BaseTool):
    name = "rag"
    description = "Retrieves authoritative corporate policies and compliance guidelines"
    category = "knowledge"

    def get_supported_actions(self) -> Dict[str, ToolActionSpec]:
        return {
            "search_knowledge": ToolActionSpec(
                name="search_knowledge",
                description="Query corporate knowledge base for policies, limits, and rules",
                parameters={
                    "query": ToolParameter(name="query", type="string", required=True, description="Search query string"),
                    "top_k": ToolParameter(name="top_k", type="integer", required=False, default=3, description="Number of results"),
                    "category": ToolParameter(name="category", type="string", required=False, description="Filter category"),
                },
                required_permissions=["read:knowledge"],
            )
        }

    def execute(
        self,
        action: str,
        inputs: Dict[str, Any],
        is_simulation: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        valid, err = self.validate_action(action, inputs)
        if not valid:
            return ToolExecutionResult(success=False, error=err, simulated=is_simulation)

        query = inputs.get("query", "")
        top_k = inputs.get("top_k", 3)
        category = inputs.get("category")

        rag = get_rag_service()
        results = rag.search(query=query, top_k=top_k, category=category)

        policy_info = {
            "query": query,
            "matched_policies": [
                {
                    "source": r.source,
                    "score": r.score,
                    "content": r.content,
                }
                for r in results
            ],
            "source": results[0].source if results else "company_handbook.md",
            "summary": results[0].content[:200] if results else "Standard procurement policy applies.",
        }

        return ToolExecutionResult(
            success=True,
            data={"policy_info": policy_info},
            simulated=is_simulation,
            metadata={"match_count": len(results)},
        )
