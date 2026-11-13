# Stop condition

Written before the loop was coded, and kept next to it in `autodocs/agent.py`:

> Stop when an ANSWER passes the done check (**done**), or after `max_steps` (**cap**). Nothing else ends the run.

Two rules learned in S1:

1. **The cap is not optional.** Without it, a goal the agent can't meet keeps spending. Every call re-sends the whole message list, so each step costs more than the last.
2. **A done check needs an honest exit.** If the only way to be "done" is to produce something the agent can't truly know (a ticket number that doesn't exist), it may invent one that passes the check. Let it say the information isn't there: `honest_ticket_check` accepts "No ticket is referenced", and rejects tickets that aren't in the source.
