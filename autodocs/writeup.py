"""The output contract: the fields AutoDocs must return, checked by pydantic."""

from typing import Literal

from pydantic import BaseModel, Field


class FunctionNote(BaseModel):
    """What one changed function does, as read from its code."""

    path: str = Field(description="File path from the repo root.")
    function: str = Field(description="Function name, or Class.method.")
    body: Literal["implemented", "empty", "not read"] = Field(
        description="'empty' if the body is only ..., pass or a TODO; 'not read' if you did not "
                    "open it. Describe behaviour only when 'implemented'.")
    what_it_does: str = Field(description="One sentence, only from code you read.")
    docstring_updated: bool = Field(description="True if you called write_docstring for it.")


class Writeup(BaseModel):
    """The pull request write-up for one branch."""

    title: str = Field(description="PR title in conventional-commit form, e.g. 'feat(x): ...'.")
    summary: str = Field(description="Two to four sentences for a reviewer.")
    changes: list[str] = Field(description="One bullet per behaviour change.")
    functions: list[FunctionNote] = Field(
        description="Every application function (not tests or migrations) the branch changes.")
    release_note: str = Field(description="One Keep a Changelog line for users; '' if none.")
    could_not_determine: list[str] = Field(
        description="Required. What you could not establish from code you read: empty bodies, "
                    "files that do not parse, helpers you did not open. [] only if nothing.")
