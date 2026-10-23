"""The only V1 tool: validated, read-only, scoped by a server-side closure."""
import json
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


class SearchArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    query: StrictStr = Field(min_length=1, max_length=2000)
    top_k: StrictInt = Field(default=5, ge=1, le=5)


SEARCH_TOOL = {'type': 'function', 'function': {
    'name': 'search_knowledge_base',
    'description': 'Search accessible knowledge-base documents for evidence. Returns excerpts, not an answer. '
                   'Use a more specific query once more if evidence is insufficient. At most two searches.',
    'parameters': {'type': 'object', 'properties': {
        'query': {'type': 'string', 'description': 'Retrieval query; keep biomedical identifiers verbatim.'},
        'top_k': {'type': 'integer', 'minimum': 1, 'maximum': 5, 'default': 5}},
        'required': ['query'], 'additionalProperties': False}}}


class ToolRegistry:
    definitions = [SEARCH_TOOL]

    def __init__(self, search):
        self.search = search

    def validate(self, name, arguments):
        if name != 'search_knowledge_base' or not isinstance(arguments, str) or len(arguments) > 12000:
            raise ValueError('Invalid tool call')
        # model_validate_json forbids role/user_id/document scope and strict types.
        return SearchArguments.model_validate_json(arguments)

    def execute(self, args):
        return self.search(args.query, args.top_k)
