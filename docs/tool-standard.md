# The tool standard

Every AutoDocs tool meets these rules before it is offered to the model. Session 3's three real tools (`read_diff`, `open_file`, `write_docstring`) are checked against this list.

1. **One typed function.** Every argument has a type hint; the schema the model sees is generated from them (`Tool.from_function`), never written by hand.
2. **The docstring is the description.** It is the only thing the model reads about the tool, so it says what the tool returns and the meaning and units of every argument (for example "line_number starts at 1"). A wrong description is not caught by any check: in rehearsal, "starts at 0" made the model ask for line 0 and report the first line as empty, 2 runs out of 2.
3. **Strict arguments.** `StrictArgs`: no extra fields, no silent type conversion. Invalid arguments are never run; the validation error goes back to the model as the tool's result.
4. **Stay inside the workspace.** A path argument is resolved and refused if it points outside the folder the tool may read.
5. **Every call gets its result, all in one message, with its call's id.** When the model asks for several tools in one turn, every result goes back, together, in the next message, each carrying the `id` of the call it answers (Gemini 3 matches results to calls by id). In rehearsal, dropping one result raised no error: the model asked for the same tool again, adding a step (3 runs out of 3). For a tool that changes something, that means doing it twice.
6. **Failures are data, not crashes.** An expected failure (a missing file, a file outside the repo, code that doesn't parse) raises `ToolError` with a short message; any other exception is caught too. Either way the model receives `{"error": …}` and decides what to do, and the run is never lost. (S2's practice tools returned `-1`; S4 replaced that.)
