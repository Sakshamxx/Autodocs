"""The output contract: the fields AutoDocs must return, checked by pydantic."""

from typing import Literal

from pydantic import BaseModel, Field


class FunctionNote(BaseModel):
    """What one changed function does, as read from its code."""

    path: str = Field(description="File path from the repo root.")
    function: str = Field(description="Function name, or Class.method.")
    body: Literal["implemented", "empty", "not read", "file does not parse"] = Field(
        description="'empty' if the body is only ..., pass or a TODO; 'not read' if you did not "
                    "open it; 'file does not parse' if its file has a syntax error. "
                    "Describe behaviour only when 'implemented'.")
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


def correct_against_facts(writeup: Writeup, unparseable: list[str]) -> list[str]:
    """Fix what code knows for certain (files that don't parse); return each correction made."""
    corrections = []
    for note in writeup.functions:
        if note.path in unparseable and note.body != "file does not parse":
            corrections.append(f"{note.path}::{note.function}: body '{note.body}' → "
                               "'file does not parse'")
            note.body = "file does not parse"
    for path in unparseable:
        reason = f"{path} does not parse, so its functions could not be read"
        if not any(path in item and "parse" in item for item in writeup.could_not_determine):
            writeup.could_not_determine.append(reason)
            corrections.append(f"added to could_not_determine: {reason}")
    return corrections
