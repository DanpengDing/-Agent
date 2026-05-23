import json
from typing import Any

from pydantic import BaseModel

from schemas.agent_output import StructuredAgentOutput
from schemas.answer_review import CandidateAnswer


class StructuredOutputService:
    @staticmethod
    def _coerce_payload(raw_output: Any):
        if raw_output is None:
            return None
        if isinstance(raw_output, BaseModel):
            return raw_output.model_dump()
        if isinstance(raw_output, dict):
            return raw_output
        if isinstance(raw_output, str):
            cleaned_output = raw_output.strip()
            if not cleaned_output:
                return None
            try:
                return json.loads(cleaned_output)
            except Exception:
                return cleaned_output
        return raw_output

    def parse_candidate_output(self, raw_output: Any) -> CandidateAnswer:
        payload = self._coerce_payload(raw_output)
        if payload is None:
            return CandidateAnswer(answer="")
        if isinstance(payload, dict):
            try:
                return CandidateAnswer.model_validate(payload)
            except Exception:
                pass
        return CandidateAnswer(answer=str(payload).strip())

    @staticmethod
    def parse_final_output(raw_output: Any) -> StructuredAgentOutput:
        payload = StructuredOutputService._coerce_payload(raw_output)
        if payload is None:
            return StructuredAgentOutput(answer="")

        if isinstance(payload, dict):
            try:
                return StructuredAgentOutput.model_validate(payload)
            except Exception:
                pass

        return StructuredAgentOutput(answer=str(payload).strip())


structured_output_service = StructuredOutputService()
