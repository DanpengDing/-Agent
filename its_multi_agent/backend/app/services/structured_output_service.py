from schemas.agent_output import StructuredAgentOutput


class StructuredOutputService:
    @staticmethod
    def parse_final_output(raw_output: str) -> StructuredAgentOutput:
        cleaned_output = (raw_output or "").strip()
        if not cleaned_output:
            return StructuredAgentOutput(answer="")

        try:
            return StructuredAgentOutput.model_validate_json(cleaned_output)
        except Exception:
            return StructuredAgentOutput(answer=cleaned_output)


structured_output_service = StructuredOutputService()
