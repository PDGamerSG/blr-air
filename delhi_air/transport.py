"""Compatibility fix for uAgents 0.26.1 receiving Pydantic v1 wire models.

The SDK catches Pydantic v2 ValidationError while uagents.Model inherits v1.
Handle only that missed exception; retain the SDK's signatures, schemas and routing.
"""

from pydantic.v1 import ValidationError
from uagents import Agent
from uagents_core.models import ErrorMessage, Model


class ResilientAgent(Agent):
    async def _process_single_message(self, schema_digest, sender, message, session):
        try:
            await super()._process_single_message(schema_digest, sender, message, session)
        except ValidationError:
            self._logger.warning("Rejected message that does not conform to its schema")
            context = self._build_context()
            context._session = session
            error = ErrorMessage(
                error="Message does not conform to expected schema. "
                "Check coordinates, duration and request fields."
            )
            try:
                await context.send_raw(
                    destination=sender,
                    message_schema_digest=Model.build_schema_digest(error),
                    message_body=error.model_dump_json(),
                    queries=self._queries,
                )
            except Exception:
                self._logger.warning(
                    "Could not deliver schema error; continuing message processing"
                )
