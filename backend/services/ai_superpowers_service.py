"""
AI Superpowers — Enhances AI responses with intelligence layers.
Includes: Prompt Optimiser, Self-Critique, Confidence Score,
Hallucination Detector, Reflection Mode, and Multi-Agent Debate.
"""
import json
import logging
import re
from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)

ollama = OllamaService()


class AISuperpowers:

    async def optimise_prompt(self, user_message: str, model: str = "qwen3:8b") -> str:
        """Rewrite a vague or poorly structured prompt into a clear, effective one."""
        system = (
            "You are a prompt engineer. Rewrite the user's prompt to be clearer, "
            "more specific, and more effective for an AI tutor.\n"
            "Rules:\n"
            "- Keep the original intent\n"
            "- Add specificity where vague\n"
            "- Use clear structure\n"
            "- Return ONLY the improved prompt, no explanation\n"
            "- If the prompt is already good, return it unchanged"
        )
        try:
            result = await ollama.complete(model, user_message, system=system, max_tokens=300)
            return result.strip() if result.strip() else user_message
        except Exception:
            return user_message

    async def self_critique(self, response: str, question: str, model: str = "qwen3:8b") -> dict:
        """Review its own answer for accuracy, completeness, and clarity."""
        system = (
            "You are a quality reviewer for educational AI responses.\n"
            "Analyse the AI's answer to the student's question.\n"
            "Rate each dimension 1-10 and provide specific feedback.\n"
            "Return JSON only:\n"
            '{"accuracy": {"score": N, "issue": "..."}, '
            '"completeness": {"score": N, "issue": "..."}, '
            '"clarity": {"score": N, "issue": "..."}, '
            '"overall_score": N, '
            '"improvement_suggestions": ["suggestion1", "suggestion2"]}'
        )
        prompt = f"Question: {question}\n\nAI Answer: {response[:2000]}"
        try:
            result = await ollama.complete(model, prompt, system=system, max_tokens=600)
            # Parse JSON
            m = re.search(r'\{.*\}', result, re.DOTALL)
            if m:
                return json.loads(m.group())
            return {"overall_score": 5, "note": "Could not parse critique"}
        except Exception as e:
            return {"error": str(e)}

    async def confidence_score(self, response: str, question: str, model: str = "qwen3:8b") -> dict:
        """Ask the AI to rate its own confidence in the answer."""
        system = (
            "You are a confidence calibrator for an educational AI.\n"
            "Given the AI's answer to a question, rate your confidence that the answer is correct.\n"
            "Consider: factual accuracy, potential for hallucination, complexity of topic.\n"
            "Return JSON only:\n"
            '{"confidence": N (0-100), "reasoning": "...", "needs_verification": true/false}'
        )
        prompt = f"Question: {question}\n\nAnswer: {response[:1500]}"
        try:
            result = await ollama.complete(model, prompt, system=system, max_tokens=200)
            m = re.search(r'\{.*\}', result, re.DOTALL)
            if m:
                return json.loads(m.group())
            return {"confidence": 50, "reasoning": "Could not parse"}
        except Exception as e:
            return {"error": str(e)}

    async def hallucination_detector(self, response: str, context: str, model: str = "qwen3:8b") -> dict:
        """Flag statements that need verification or may be hallucinated."""
        system = (
            "You are a fact-checker for educational content.\n"
            "Analyse the AI response and flag any claims that:\n"
            "1. Might be hallucinated (not commonly known facts)\n"
            "2. Need source verification\n"
            "3. Could be outdated information\n"
            "4. Are subjective opinions presented as facts\n"
            "Return JSON only:\n"
            '{"flagged_claims": [{"claim": "...", "reason": "...", "severity": "high/medium/low"}], '
            '"verification_needed": true/false, '
            '"trusted_percentage": N (0-100)}'
        )
        prompt = f"Context: {context[:1000]}\n\nResponse: {response[:2000]}"
        try:
            result = await ollama.complete(model, prompt, system=system, max_tokens=500)
            m = re.search(r'\{.*\}', result, re.DOTALL)
            if m:
                return json.loads(m.group())
            return {"trusted_percentage": 70, "flagged_claims": []}
        except Exception as e:
            return {"error": str(e)}

    async def reflection_mode(self, response: str, question: str, model: str = "qwen3:8b") -> str:
        """Review the response and provide an improved version."""
        system = (
            "You are a reflective AI tutor.\n"
            "Review the given answer and provide an improved version.\n"
            "Focus on:\n"
            "- Correcting any errors\n"
            "- Adding missing important information\n"
            "- Improving clarity and explanations\n"
            "- Making it more engaging for a student\n"
            "Return ONLY the improved answer."
        )
        prompt = f"Original Question: {question}\n\nCurrent Answer:\n{response[:2000]}\n\nProvide an improved version:"
        try:
            result = await ollama.complete(model, prompt, system=system, max_tokens=2000)
            return result.strip() if result.strip() else response
        except Exception:
            return response

    async def multi_agent_debate(self, question: str, models: list[str] | None = None) -> dict:
        """Multiple models answer the same question, then compare."""
        if models is None:
            models = ["qwen3:8b", "qwen2.5:3b"]

        answers = {}
        for model in models:
            try:
                system = "You are a helpful, accurate AI tutor. Give a thorough answer."
                result = await ollama.complete(model, question, system=system, max_tokens=800)
                answers[model] = result.strip()
            except Exception as e:
                answers[model] = f"Error: {e}"

        # Compare answers
        if len(answers) < 2:
            return {"answers": answers, "comparison": "Only one model available"}

        comparison_system = (
            "You are comparing two AI answers to the same question.\n"
            "Identify agreements, disagreements, and which answer is more accurate.\n"
            "Return JSON:\n"
            '{"agreements": [...], "disagreements": [...], "better_answer": "model_name", '
            '"combined_answer": "best parts of both"}'
        )
        comparison_prompt = (
            f"Question: {question}\n\n"
            f"Answer 1 ({models[0]}):\n{answers.get(models[0], 'N/A')[:1000]}\n\n"
            f"Answer 2 ({models[1]}):\n{answers.get(models[1], 'N/A')[:1000]}"
        )
        try:
            result = await ollama.complete(models[0], comparison_prompt, system=comparison_system, max_tokens=800)
            m = re.search(r'\{.*\}', result, re.DOTALL)
            comparison = json.loads(m.group()) if m else {"raw": result}
        except Exception:
            comparison = {"raw": "Comparison unavailable"}

        return {"answers": answers, "comparison": comparison}
